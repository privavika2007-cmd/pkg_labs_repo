@echo off
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m unittest discover -s tests -t .
pyinstaller --noconfirm --onefile --windowed --name RasterLab main.py
echo.
echo Готово: dist\RasterLab.exe
pause
