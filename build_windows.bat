@echo off
setlocal
REM Finance Manager Windows EXE build.
REM The --collect-all options are essential: PDF modules are imported only
REM when users click Print, so PyInstaller cannot reliably discover them.

python -m pip install --upgrade pyinstaller reportlab qrcode[pil]

python -m PyInstaller --noconfirm --clean --windowed ^
  --name FinanceManager ^
  --icon app_icon.ico ^
  --collect-all reportlab ^
  --collect-all qrcode ^
  --collect-all PIL ^
  --hidden-import reportlab.graphics.barcode.qr ^
  --hidden-import reportlab.graphics.shapes ^
  --hidden-import reportlab.graphics.charts.piecharts ^
  main.py

echo.
echo Build complete. Use dist\FinanceManager\FinanceManager.exe
pause
