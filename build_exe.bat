@echo off
echo ================================
echo   UniDown - EXE Olusturuluyor
echo ================================
echo.

:: Gerekli kurulumlar
pip install yt-dlp pyinstaller --quiet

echo EXE olusturuluyor...

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "UniDown" ^
  --icon NONE ^
  --hidden-import yt_dlp ^
  --hidden-import tkinter ^
  gui_app.py

echo.
echo ================================
if exist "dist\UniDown.exe" (
    echo   BASARILI! dist/UniDown.exe hazir!
) else (
    echo   HATA! EXE olusturulamadi.
)
echo ================================
pause
