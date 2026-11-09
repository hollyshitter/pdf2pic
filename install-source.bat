@echo off
rem PDF2Pic - run from source, no exe at all.
rem Needs Python 3.10+ with tkinter (the official python.org installer has it).
setlocal
cd /d "%~dp0"

echo === PDF2Pic from source ===
echo.

where python >nul 2>nul
if errorlevel 1 goto nopython

python -c "import sys" >nul 2>nul
if errorlevel 1 goto nopython

python -c "import tkinter" >nul 2>nul
if errorlevel 1 goto notk

python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto oldpython

echo [1/2] Installing dependencies (pymupdf, pillow) ...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pipfail

echo [2/2] Registering right-click menu ...
python pdf2pic.py --install
if errorlevel 1 goto installfail

echo.
echo Done. Right-click any PDF and pick the Zhuan Tu Pian submenu.
echo To remove it later:  python pdf2pic.py --uninstall
echo.
pause
exit /b 0

:nopython
echo Python not found.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo During setup tick "Add python.exe to PATH".
echo.
pause
exit /b 1

:oldpython
echo Python is too old. Need 3.10 or newer.
python --version
echo.
pause
exit /b 1

:notk
echo This Python has no tkinter, so the progress window cannot work.
echo Use the official installer from python.org (not a stripped embeddable build).
echo.
pause
exit /b 1

:pipfail
echo.
echo pip install failed. If you are behind a proxy, set it first:
echo   set HTTPS_PROXY=http://user:pass@host:port
echo.
pause
exit /b 1

:installfail
echo.
echo Failed to register the context menu.
echo.
pause
exit /b 1
