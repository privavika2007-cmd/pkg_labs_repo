@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --name ImageInfo main.py
echo.
echo Готово: dist\ImageInfo.exe
pause
