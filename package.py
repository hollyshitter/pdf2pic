# -*- coding: utf-8 -*-
"""Build release artifacts.

Outputs into release/:
  PDF2Pic-v<ver>-win64.zip     portable build (exe + _internal), for people who trust it
  PDF2Pic-v<ver>-source.zip    pure source, runs on the user's own Python, zero binaries
  SHA256SUMS.txt               checksums for every file above
"""
import hashlib
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist", "PDF2Pic")
OUT_DIR = os.path.join(ROOT, "release")


def version() -> str:
    with open(os.path.join(ROOT, "pdf2pic.py"), encoding="utf-8") as f:
        m = re.search(r'VERSION\s*=\s*"([^"]+)"', f.read())
    return m.group(1) if m else "0.0.0"


GUIDE = """PDF2Pic {ver} 使用说明

一、装
  1. 把整个 PDF2Pic 文件夹放到一个不会被清理的位置，例如 D:\\Tools\\PDF2Pic
  2. 双击 PDF2Pic.exe
  3. 点「安装右键菜单」

二、用
  在任意 PDF 上右键 -> 转图片 -> 选一个格式和清晰度。
  图片会输出到 PDF 所在目录下、与 PDF 同名的文件夹里，按 page_001 顺序编号。
  想批量转换就一次选中多个 PDF，再右键。

三、卸载
  双击 PDF2Pic.exe，点「卸载」。只改动当前用户的注册表，不需要管理员权限。

四、注意
  - 整个文件夹要一起移动，_internal 里是运行库，只拷 exe 跑不起来
  - 想改成别的清晰度，可以在命令行里自己加参数，例如：
      PDF2Pic.exe --format jpeg --dpi 300 --jpeg-quality 90 某某.pdf
  - 运行日志在 %LOCALAPPDATA%\\PDF2Pic\\pdf2pic.log
"""

SOURCE_GUIDE = """PDF2Pic {ver} 源码版使用说明

这一包不含任何 exe，只有 python 脚本。代码全部可读，依赖只有两个开源库：
pymupdf（渲染 PDF）和 pillow（PNG 编码）。

一、准备
  1. 装 Python 3.10 或更新版本，从 python.org 下官方安装包
     安装时勾上 "Add python.exe to PATH"
  2. 解压本压缩包到任意目录

二、装
  双击 install-source.bat
  它会依次检查 Python、检查 tkinter、装依赖、注册右键菜单。

三、用
  和 exe 版一样：右键 PDF -> 转图片 -> 选清晰度。

四、卸载
  在本目录打开命令行，执行：
      python pdf2pic.py --uninstall

五、不想注册右键菜单，只用命令行
      python pdf2pic.py --format jpeg --dpi 200 某某.pdf
      python pdf2pic.py --help

六、为什么这样更安全
  没有任何二进制文件，不会被杀软误报，也不存在“打包时夹带东西”的可能。
  你随时可以打开 pdf2pic.py 看每一行在干什么，全文约 600 行。
  读代码嫌麻烦，就核对 SHA256SUMS.txt 里的校验值，确认下载的文件没被改过。
"""

SOURCE_FILES = [
    "pdf2pic.py",
    "requirements.txt",
    "install-source.bat",
    "README.md",
    "LICENSE",
    "app.ico",
]


def build_portable(ver: str) -> str:
    if not os.path.isdir(DIST):
        print("skip portable zip: dist/PDF2Pic not found (run build.bat first)")
        return ""
    out = os.path.join(OUT_DIR, f"PDF2Pic-v{ver}-win64.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for base, _dirs, files in os.walk(DIST):
            for name in files:
                full = os.path.join(base, name)
                rel = os.path.relpath(full, DIST)
                z.write(full, os.path.join("PDF2Pic", rel))
        z.writestr("PDF2Pic/使用说明.txt", GUIDE.format(ver=ver))
    print(f"portable  {os.path.basename(out)}  {os.path.getsize(out)/1024/1024:.1f} MB")
    return out


def build_source(ver: str) -> str:
    out = os.path.join(OUT_DIR, f"PDF2Pic-v{ver}-source.zip")
    if os.path.exists(out):
        os.remove(out)
    root = f"PDF2Pic-{ver}-source"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in SOURCE_FILES:
            full = os.path.join(ROOT, name)
            if not os.path.isfile(full):
                raise SystemExit(f"missing source file: {name}")
            z.write(full, f"{root}/{name}")
        z.writestr(f"{root}/使用说明-源码版.txt", SOURCE_GUIDE.format(ver=ver))
    print(f"source    {os.path.basename(out)}  {os.path.getsize(out)/1024:.0f} KB")
    return out


def write_sums() -> str:
    out = os.path.join(OUT_DIR, "SHA256SUMS.txt")
    lines = []
    for name in sorted(os.listdir(OUT_DIR)):
        path = os.path.join(OUT_DIR, name)
        if not os.path.isfile(path) or name == "SHA256SUMS.txt":
            continue
        if not name.lower().endswith((".zip", ".whl", ".tar.gz")):
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {name}")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"checksums {os.path.basename(out)}  ({len(lines)} files)")
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ver = version()
    build_portable(ver)
    build_source(ver)
    write_sums()
    print(f"\nversion {ver} -> {OUT_DIR}")


if __name__ == "__main__":
    main()
