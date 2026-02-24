@echo off
setlocal

echo === Meetily Build ===

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.10+.
    exit /b 1
)

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing build dependencies...
    python -m pip install -e ".[dev]"
)

if not exist meetily\resources\icon.ico (
    echo WARNING: meetily\resources\icon.ico not found -- app will have no icon.
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Running PyInstaller...
python -m PyInstaller meetily.spec --noconfirm

echo.
echo === Build Complete ===
echo Output: dist\Meetily\
echo Run:    dist\Meetily\Meetily.exe

endlocal
