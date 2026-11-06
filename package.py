# -*- coding: utf-8 -*-
"""Zip dist/PDF2Pic into a release archive with a Chinese readme inside."""
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "dist", "PDF2Pic")
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


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("dist/PDF2Pic not found, run build.bat first")
    os.makedirs(OUT_DIR, exist_ok=True)
    ver = version()
    out = os.path.join(OUT_DIR, f"PDF2Pic-v{ver}-win64.zip")
    if os.path.exists(out):
        os.remove(out)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for base, _dirs, files in os.walk(SRC):
            for name in files:
                full = os.path.join(base, name)
                rel = os.path.relpath(full, SRC)
                z.write(full, os.path.join("PDF2Pic", rel))
        z.writestr("PDF2Pic/使用说明.txt", GUIDE.format(ver=ver))

    size = os.path.getsize(out) / 1024 / 1024
    print(f"{out}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
