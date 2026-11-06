@echo off
setlocal
cd /d "%~dp0"

echo === PDF2Pic build ===
python -m PyInstaller --noconfirm --clean --windowed --onedir --name PDF2Pic --icon app.ico --exclude-module numpy --exclude-module numpy.libs --exclude-module matplotlib --exclude-module scipy --exclude-module pandas pdf2pic.py
if errorlevel 1 goto fail

echo.
echo === Packaging zip ===
python package.py
if errorlevel 1 goto fail

echo.
echo Build OK
echo   app : dist\PDF2Pic\PDF2Pic.exe
echo   zip : release\
goto end

:fail
echo.
echo Build FAILED

:end
pause
