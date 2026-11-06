# PDF2Pic

右键任意 PDF，一键转成图片。输出放在 PDF 同目录的同名文件夹里，`page_001.png` 这样编号。

Windows 10/11 专用，绿色免安装，不用装 Python。

## 能干什么

- 右键 PDF → 「转图片」→ 7 个预设（PNG / JPEG × 高清 / 标清 / 低清）
- 一次选中多个 PDF 一起右键，每个各自转，互不干扰
- 转的时候有置顶进度窗：第几页、多少页每秒、已经用了多久，随时能取消
- 大文件自动多进程并行，65 页扫描版合同 8~10 秒转完
- 全程本地处理，不联网、不上传

## 下载安装

1. 去 [Releases](../../releases) 下最新的 `PDF2Pic-v1.0.0-win64.zip`
2. 解压到一个不会被清理的目录，比如 `D:\Tools\PDF2Pic`
3. 双击 `PDF2Pic.exe`，点「安装右键菜单」
4. 随便找个 PDF 右键试一下

卸载：双击 exe，点「卸载」。只写 `HKCU` 注册表，不需要管理员权限。

> 整个文件夹必须一起移动。`_internal` 里是运行库，单独拷 `PDF2Pic.exe` 出去跑不起来。

## 菜单项

| 菜单项 | 分辨率 | 什么时候用 |
| --- | --- | --- |
| 一键默认 · PNG 标清 | 144 DPI | 日常够用，不纠结就选这个 |
| PNG · 高清 | 216 DPI | 要打印、要放大看细节 |
| PNG · 标清 | 144 DPI | 文字、表格、截图类 |
| PNG · 低清 | 96 DPI | 只在屏幕上翻，图多要省空间 |
| JPEG · 高清 | 216 DPI · q92 | 扫描件、图纸 |
| JPEG · 标清 | 144 DPI · q85 | 扫描件推荐，体积约 PNG 的 1/8 |
| JPEG · 低清 | 96 DPI · q75 | 页数特别多、只求看得清 |

纯文字或表格建议 PNG（无损，边缘干净）；扫描件建议 JPEG（体积差一个数量级）。

## 从源码跑

需要 Python 3.10+，且必须是带 tkinter 的完整版（python.org 的安装包就行，微软商店版也没有问题，某些精简发行版没有）。

```bash
pip install pymupdf pillow
python pdf2pic.py --install          # 注册右键菜单，指向当前脚本
python pdf2pic.py 某某.pdf            # 也可以直接命令行转
python pdf2pic.py --uninstall        # 取消
```

## 命令行

```
PDF2Pic.exe [--format png|jpeg] [--dpi N] [--jpeg-quality N] [--jobs N] <pdf> ...

PDF2Pic.exe --install      注册右键菜单（指向当前 exe 的路径）
PDF2Pic.exe --uninstall    删除右键菜单
PDF2Pic.exe --version
```

`--jobs 0`（默认）自动判断，`--jobs 1` 强制单线程，`--jobs 4` 强制开 4 个进程。

## 打包

```bat
pip install pyinstaller
build.bat
```

产物在 `dist\PDF2Pic\`，整个目录压缩后即可分发。

用的是 onedir 而不是 onefile：单文件模式下，多进程的每个子进程都要重新解压一遍自身，启动开销能吃掉并行省下的全部时间。

## 几个实现上的选择

- 渲染用 PyMuPDF。PNG 编码没走 PyMuPDF 自带的那套，改用 Pillow 的 `compress_level=3`——同一张图实测 568ms vs 1649ms，体积只差 2%。
- 并行只在文档真的重的时候开：纯文字 20 页 PDF 串行 1.7 秒，开 4 个进程反而要 3.7 秒，因为建进程本身就要 2 秒。所以按「页数 ≥ 40，或页数 ≥ 8 且平均每页 ≥ 80KB」来判断。
- 进度窗口是 tkinter 手写的，主线程被渲染占住，所以每次改完控件都强制 `update()` 一次，不然窗口会一直停在第一帧。

## 已知限制

- 只支持 Windows，右键菜单挂在 `HKCU\Software\Classes\SystemFileAssociations\.pdf\shell`
- 加密的 PDF 需要先解密，否则打不开
- 输出目录与 PDF 同名；如果该位置已有同名文件夹，图片会写进去，不会清空里面原有的东西
- 在 Win11 新版右键菜单里，级联子菜单靠 `ExtendedSubCommandsKey` 实现；个别 21H2 早期版本如果展不开，按住 Shift 右键用经典菜单即可

## License

MIT
