@echo off
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ImageLab --add-data "images;images" main.py
echo.
echo Готово: dist\ImageLab.exe
pause
