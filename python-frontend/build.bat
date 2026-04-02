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
echo === PyInstaller Build Complete ===
echo Output: dist\Meetily\
echo Run:    dist\Meetily\Meetily.exe

:: --- Optional: Build Windows installer with Inno Setup ---
if /i "%1"=="--installer" goto :build_installer
if /i "%1"=="-i" goto :build_installer
goto :done

:build_installer
echo.
echo === Building Installer ===

:: Find Inno Setup compiler
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Install from: https://jrsoftware.org/isinfo.php
    echo Then re-run:  build.bat --installer
    exit /b 1
)

echo Using: %ISCC%
"%ISCC%" installer\meetily.iss

if errorlevel 1 (
    echo ERROR: Installer build failed.
    exit /b 1
)

echo.
echo === Installer Build Complete ===
echo Output: dist\Meetily-0.1.0-Setup.exe

:done
endlocal
