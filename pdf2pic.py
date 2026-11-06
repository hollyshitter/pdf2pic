# -*- coding: utf-8 -*-
"""
PDF2Pic - right-click any PDF and turn it into a folder of images.

  Right-click a PDF -> 转图片 -> pick a format/quality preset.
  Images land in a folder next to the PDF, named after it (page_001.png ...).

  Double-click the exe (no arguments) to install or remove the context menu.

Usage:
  PDF2Pic.exe [--format png|jpeg] [--dpi N] [--jpeg-quality N] [--jobs N] <pdf> ...
  PDF2Pic.exe --install | --uninstall | --version
"""
import sys
import os
import time
import argparse
import traceback
import multiprocessing

APP_NAME = "PDF2Pic"
VERSION = "1.0.0"

AUTOCLOSE_SEC = 5   # auto-close the window N seconds after a successful run
AUTO_OPEN = True    # open the output folder when conversion succeeds
PNG_COMPRESS = 3    # Pillow zlib level: 3 keeps the size, ~3x faster than PyMuPDF
PARALLEL_MIN_PAGES = 8
PARALLEL_MIN_AVG_KB = 80
MAX_JOBS = min(4, os.cpu_count() or 1)


def _data_dir() -> str:
    """Writable place for the log, even when the exe sits in a read-only folder."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


LOG_FILE = os.path.join(_data_dir(), "pdf2pic.log")


def _log(line: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except Exception:
        pass


import pymupdf  # PyMuPDF

try:  # Pillow ships a much faster PNG encoder than PyMuPDF's built-in one
    from PIL import Image as _PILImage
except Exception:
    _PILImage = None

_PIL_MODE = {1: "L", 2: "LA", 3: "RGB", 4: "RGBA"}


def _write_image(pix, path: str, out_format: str, quality: int):
    if out_format == "jpeg":
        with open(path, "wb") as f:
            f.write(pix.tobytes("jpeg", jpg_quality=quality))
        return
    if _PILImage is not None:
        try:
            mode = _PIL_MODE.get(pix.n)
            if mode:
                _PILImage.frombytes(mode, (pix.width, pix.height), pix.samples).save(
                    path, format="PNG", compress_level=PNG_COMPRESS)
                return
        except Exception:
            pass
    pix.save(path)


# ---------------------------------------------------------------- rendering --

_WORKER_DOC = {}


def _render_one(task):
    """Render one page inside a worker process (module-level so it can be pickled)."""
    pdf_path, idx, out_format, dpi, quality, out_dir, pad = task
    try:
        doc = _WORKER_DOC.get(pdf_path)
        if doc is None:
            doc = pymupdf.open(pdf_path)
            _WORKER_DOC[pdf_path] = doc
        zoom = dpi / 72.0
        pix = doc[idx].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        path = os.path.join(out_dir, f"page_{idx + 1:0{pad}d}.{out_format}")
        _write_image(pix, path, out_format, quality)
        return idx, ""
    except Exception as e:
        return idx, f"{type(e).__name__}: {e}"


def convert(pdf_path: str, out_format: str = "png", dpi: int = 144,
            jpeg_quality: int = 85, ui=None, jobs: int = 0) -> str:
    """Convert one PDF into images. ui is an optional progress window."""
    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        return f"[skip] not found: {pdf_path}"
    if not pdf_path.lower().endswith(".pdf"):
        return f"[skip] not a pdf: {pdf_path}"

    out_dir = os.path.splitext(pdf_path)[0]
    os.makedirs(out_dir, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total = doc.page_count
    mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pad = max(3, len(str(total)))
    errors = 0
    t0 = time.time()

    if ui:
        ui.set_total(total)

    workers = min(jobs if jobs > 0 else MAX_JOBS, total)

    def _use_parallel() -> bool:
        """Parallel only pays off for heavy documents.

        A 20-page text-only PDF renders in ~1.7s serially, while starting four
        worker processes alone costs ~2s -- so judge by page count AND page size.
        """
        if total < PARALLEL_MIN_PAGES:
            return False
        if total >= 40:
            return True
        try:
            avg_kb = os.path.getsize(pdf_path) / 1024 / max(total, 1)
        except OSError:
            avg_kb = 0
        return avg_kb >= PARALLEL_MIN_AVG_KB

    # ---- parallel path (an explicit --jobs N > 1 overrides the heuristic) ----
    if workers > 1 and (jobs > 1 or _use_parallel()):
        from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
        doc.close()
        doc = None
        tasks = [(pdf_path, i, out_format, dpi, jpeg_quality, out_dir, pad)
                 for i in range(total)]
        done = 0
        errs = []
        cancelled = False
        ex = ProcessPoolExecutor(max_workers=workers)
        try:
            pending = {ex.submit(_render_one, t) for t in tasks}
            while pending:
                finished, pending = wait(pending, timeout=0.15,
                                         return_when=FIRST_COMPLETED)
                for fut in finished:
                    idx, err = fut.result()
                    if err:
                        errs.append(f"page {idx + 1}: {err}")
                    done += 1
                if ui:
                    ui.progress(done, total, time.time() - t0)
                if ui and ui.cancelled:
                    cancelled = True
                    for f in pending:
                        f.cancel()
                    break
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

        if errs:
            try:
                with open(os.path.join(out_dir, "_errors.log"), "a", encoding="utf-8") as f:
                    f.write("\n".join(errs) + "\n")
            except Exception:
                pass
        if cancelled:
            return f"[cancel] {pdf_path} (stopped at page {done}/{total})"
        secs = time.time() - t0
        return f"[ok] {pdf_path} -> {out_dir} ({total} pages, {len(errs)} errors, {secs:.1f}s)"

    # ---- serial path: small or light documents ----
    for i, page in enumerate(doc):
        if ui and ui.cancelled:
            doc.close()
            return f"[cancel] {pdf_path} (stopped at page {i + 1}/{total})"
        try:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            path = os.path.join(out_dir, f"page_{i + 1:0{pad}d}.{out_format}")
            _write_image(pix, path, out_format, jpeg_quality)
        except Exception as e:
            errors += 1
            try:
                with open(os.path.join(out_dir, "_errors.log"), "a", encoding="utf-8") as f:
                    f.write(f"page {i + 1}: {e}\n")
            except Exception:
                pass
        if ui:
            ui.progress(i + 1, total, time.time() - t0)
    doc.close()
    secs = time.time() - t0
    return f"[ok] {pdf_path} -> {out_dir} ({total} pages, {errors} errors, {secs:.1f}s)"


# ------------------------------------------------------------ progress window --

class ProgressWindow:
    """Topmost tkinter window with progress, speed and cancel support."""

    def __init__(self, title: str):
        self.cancelled = False
        self._closed = False
        self._running = True
        self._out_dir = ""
        try:
            import tkinter as tk
            from tkinter import ttk
            self._tk = tk
            self._ttk = ttk
        except Exception:
            self._tk = None
            return

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} - {title}")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.geometry("+120+120")

        pad = {"padx": 14, "pady": 6}
        self.label = tk.Label(self.root, text="准备中…", font=("Microsoft YaHei UI", 10),
                              anchor="w", justify="left", wraplength=360)
        self.label.pack(fill="x", **pad)
        self.bar = ttk.Progressbar(self.root, length=340, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=14, pady=(0, 8))

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=(0, 10))
        self.open_btn = tk.Button(btn_frame, text="打开文件夹", width=12, state="disabled",
                                  command=self._open)
        self.open_btn.pack(side="left", padx=6)
        self.close_btn = tk.Button(btn_frame, text="取消", width=10, command=self._on_action)
        self.close_btn.pack(side="left", padx=6)

        self.root.protocol("WM_DELETE_WINDOW", self._on_wm_close)
        self._pump_once()

    def _alive(self) -> bool:
        return self._tk is not None and not self._closed

    def _pump_once(self):
        if not self._alive():
            return
        try:
            self.root.update()
        except Exception:
            self._closed = True

    def set_total(self, total: int):
        if not self._alive():
            return
        try:
            self.label.config(text=f"共 {total} 页，转换中…")
            self._pump_once()
        except Exception:
            self._closed = True

    def progress(self, done: int, total: int, elapsed: float = 0.0):
        if not self._alive():
            return
        try:
            pct = int(done * 100 / max(total, 1))
            speed = done / elapsed if elapsed > 0.2 else 0
            if speed > 0:
                self.label.config(text=f"转换中… {done}/{total} 页（{pct}%）· "
                                       f"{speed:.1f} 页/秒 · 已用 {elapsed:.0f} 秒")
            else:
                self.label.config(text=f"转换中… {done}/{total} 页（{pct}%）")
            self.bar.config(value=pct)
            self._pump_once()
        except Exception:
            self._closed = True

    def finish(self, text: str, out_dir: str = "", ok: bool = True, auto_open: bool = False):
        self._running = False
        if not self._alive():
            return
        try:
            if ok:
                self.bar.config(value=100)
            self.label.config(text=text)
            self.open_btn.config(state="normal")
            self.close_btn.config(text="关闭", state="normal", command=self._close)
            self._out_dir = out_dir
            self._pump_once()
            if ok and auto_open and out_dir and os.path.isdir(out_dir):
                self._open()
            if ok and AUTOCLOSE_SEC > 0:
                self.root.after(AUTOCLOSE_SEC * 1000, self._close)
        except Exception:
            self._closed = True

    def _open(self):
        if self._out_dir and os.path.isdir(self._out_dir):
            try:
                os.startfile(self._out_dir)
            except Exception:
                pass

    def _on_action(self):
        """Cancel while converting; close the window once finished."""
        if self._running:
            self.cancelled = True
            if not self._alive():
                return
            try:
                self.close_btn.config(state="disabled", text="停止中…")
                self._pump_once()
            except Exception:
                self._closed = True
        else:
            self._close()

    def _on_wm_close(self):
        if self._running:
            self.cancelled = True
        self._close()

    def _close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def wait_close(self, timeout: float = 3600):
        t0 = time.time()
        while not self._closed and time.time() - t0 < timeout:
            self._pump_once()
            time.sleep(0.05)


# --------------------------------------------------------- context menu setup --

SHELL = r"Software\Classes\SystemFileAssociations\.pdf\shell"
PARENT = "PdfToImage"
PARENT_KEY = SHELL + "\\" + PARENT
EXT_PATH = r"SystemFileAssociations\.pdf\shell\PdfToImage"

ITEMS = [
    ("1_default", "一键默认 · PNG 标清（144 DPI）", "--format png --dpi 144", 0x40),
    ("2_pngHi",   "PNG · 高清（216 DPI）",          "--format png --dpi 216", 0),
    ("3_pngMid",  "PNG · 标清（144 DPI）",          "--format png --dpi 144", 0),
    ("4_pngLow",  "PNG · 低清（96 DPI）",           "--format png --dpi 96", 0),
    ("5_jpgHi",   "JPEG · 高清（216 DPI）",         "--format jpeg --dpi 216 --jpeg-quality 92", 0x20),
    ("6_jpgMid",  "JPEG · 标清（144 DPI）",         "--format jpeg --dpi 144 --jpeg-quality 85", 0),
    ("7_jpgLow",  "JPEG · 低清（96 DPI）",          "--format jpeg --dpi 96 --jpeg-quality 75", 0),
]
LEGACY_SUFFIXES = ["_pngHi", "_pngMid", "_pngLow", "_jpgHi", "_jpgMid", "_jpgLow"]


def _launcher() -> str:
    """The command that runs a conversion, quoted and ready to append args."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    return f'"{pyw}" "{os.path.abspath(__file__)}"'


def _icon_ref() -> str:
    return sys.executable if getattr(sys, "frozen", False) else os.path.join(
        os.path.dirname(sys.executable), "pythonw.exe")


def _delete_tree(root, path):
    import winreg
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, path + "\\" + sub)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def install_menu() -> str:
    import winreg
    # clean leftovers from older layouts (flat verbs, stale SubCommands)
    for sfx in LEGACY_SUFFIXES:
        _delete_tree(winreg.HKEY_CURRENT_USER, SHELL + "\\" + PARENT + sfx)
    _delete_tree(winreg.HKEY_CURRENT_USER, PARENT_KEY + r"\shell")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PARENT_KEY, 0, winreg.KEY_WRITE) as k:
            for name in ("SubCommands", "CommandFlags"):
                try:
                    winreg.DeleteValue(k, name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PARENT_KEY) as k:
        winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, "转图片")
        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, _icon_ref())
        winreg.SetValueEx(k, "ExtendedSubCommandsKey", 0, winreg.REG_SZ, EXT_PATH)
        winreg.SetValueEx(k, "CommandFlags", 0, winreg.REG_DWORD, 0x20)

    launcher = _launcher()
    for verb, label, args, flags in ITEMS:
        key = PARENT_KEY + rf"\shell\{verb}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, label)
            if flags:
                winreg.SetValueEx(k, "CommandFlags", 0, winreg.REG_DWORD, flags)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{launcher} {args} "%1"')

    _notify_shell()
    return launcher


def uninstall_menu():
    import winreg
    _delete_tree(winreg.HKEY_CURRENT_USER, PARENT_KEY)
    for sfx in LEGACY_SUFFIXES:
        _delete_tree(winreg.HKEY_CURRENT_USER, SHELL + "\\" + PARENT + sfx)
    _notify_shell()


def _notify_shell():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


# ------------------------------------------------------------- setup window --

def show_setup_window():
    """Shown when the exe is double-clicked: install / remove the menu."""
    try:
        import tkinter as tk
    except Exception:
        print(f"{APP_NAME} {VERSION}")
        print("Usage: PDF2Pic.exe --install | --uninstall")
        return

    root = tk.Tk()
    root.title(f"{APP_NAME} {VERSION}")
    root.resizable(False, False)
    root.geometry("+180+160")

    tk.Label(root, text=APP_NAME, font=("Microsoft YaHei UI", 18, "bold")).pack(pady=(18, 2))
    tk.Label(root, text="右键任意 PDF，一键转成图片", font=("Microsoft YaHei UI", 9),
             fg="#555").pack()
    status = tk.Label(root, text="", font=("Microsoft YaHei UI", 9), fg="#0a7a2f",
                      wraplength=320)
    status.pack(pady=(10, 0))

    def do_install():
        try:
            install_menu()
            status.config(text="✔ 已安装。右键任意 PDF 试试「转图片」", fg="#0a7a2f")
        except Exception as e:
            status.config(text=f"✖ 安装失败：{e}", fg="#b00020")

    def do_uninstall():
        try:
            uninstall_menu()
            status.config(text="已卸载右键菜单", fg="#555")
        except Exception as e:
            status.config(text=f"✖ 卸载失败：{e}", fg="#b00020")

    box = tk.Frame(root)
    box.pack(pady=12)
    tk.Button(box, text="安装右键菜单", width=14, command=do_install).pack(side="left", padx=6)
    tk.Button(box, text="卸载", width=8, command=do_uninstall).pack(side="left", padx=6)
    tk.Button(box, text="关闭", width=8, command=root.destroy).pack(side="left", padx=6)

    tk.Label(root, text=f"多选 PDF 可批量转换 · 输出到同名文件夹 · 日志：{LOG_FILE}",
             font=("Microsoft YaHei UI", 8), fg="#888", wraplength=340).pack(pady=(0, 14))
    root.mainloop()


# -------------------------------------------------------------------- main --

def main():
    ap = argparse.ArgumentParser(prog=APP_NAME, add_help=True)
    ap.add_argument("pdfs", nargs="*", help="PDF files to convert")
    ap.add_argument("--format", choices=["png", "jpeg"], default="png")
    ap.add_argument("--dpi", type=int, default=144)
    ap.add_argument("--jpeg-quality", type=int, default=85)
    ap.add_argument("--jobs", type=int, default=0,
                    help="worker processes (0 = auto, 1 = single-threaded)")
    ap.add_argument("--install", action="store_true", help="install the right-click menu")
    ap.add_argument("--uninstall", action="store_true", help="remove the right-click menu")
    ap.add_argument("--version", action="store_true")
    args, _unknown = ap.parse_known_args()

    if args.version:
        print(f"{APP_NAME} {VERSION}")
        return
    if args.install:
        launcher = install_menu()
        _log(f"[install] {launcher}")
        print(f"{APP_NAME} {VERSION}: 右键菜单已安装\n{launcher}")
        return
    if args.uninstall:
        uninstall_menu()
        _log("[uninstall]")
        print(f"{APP_NAME} {VERSION}: 右键菜单已卸载")
        return

    pdfs = args.pdfs
    if not pdfs:
        show_setup_window()
        return

    _log(f"[run] fmt={args.format} dpi={args.dpi} jobs={args.jobs} files={pdfs}")
    ui = ProgressWindow(os.path.basename(pdfs[0]) + (" 等" if len(pdfs) > 1 else ""))
    results = []
    try:
        for p in pdfs:
            if ui.cancelled:
                break
            results.append(convert(p, args.format, args.dpi, args.jpeg_quality, ui, args.jobs))
    except Exception as e:
        results.append(f"[error] {e} {traceback.format_exc()}")

    ok_all = bool(results) and all(r.startswith("[ok]") for r in results)
    summary = "\n".join(results)
    if ui._tk:
        last_ok_dir = ""
        for line in results:
            if " -> " in line:
                last_ok_dir = line.split(" -> ")[1].rsplit(" (", 1)[0]
        if ui.cancelled:
            ui.finish("已取消（已转换的页面保留）", ok=False)
        elif ok_all:
            n = sum(int(line.split("(")[1].split()[0]) for line in results if line.startswith("[ok]"))
            err = sum(int(line.split("(")[1].split(",")[1].split()[0]) for line in results if line.startswith("[ok]"))
            secs = sum(float(line.rsplit(", ", 1)[1].rstrip("s)")) for line in results if line.startswith("[ok]"))
            fmt = f"{args.format.upper()} · {args.dpi} DPI"
            head = "✔ 完成" if err == 0 else f"⚠ 完成但有 {err} 页失败"
            ui.finish(f"{head}：共 {n} 页 · {fmt} · 用时 {secs:.1f} 秒",
                      out_dir=last_ok_dir, ok=True, auto_open=AUTO_OPEN)
        else:
            first = results[0] if results else "[error] unknown"
            short = first.split("\n")[0]
            for tag, label in (("[skip] not found: ", "文件不存在："),
                               ("[skip] not a pdf: ", "不是 PDF：")):
                if tag in short:
                    short = label + os.path.basename(short.split(tag, 1)[1])
                    break
            if "[error]" in short:
                short = "✖ 转换失败：" + short.split("[error]", 1)[1].strip()
            if len(short) > 90:
                short = short[:90] + "…"
            ui.finish(short + "\n（详情见 pdf2pic.log）", ok=False)
        ui.wait_close()

    _log("[end] " + " | ".join(results))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
