@echo off
setlocal

cd /d "%~dp0.."

python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller fapiao.spec

echo.
echo Build finished. EXE is in dist\发票识别.exe
pause
