@echo off
:: build.bat — локальная сборка без GitHub Actions
:: Запускать из корня проекта: build.bat

echo ====================================
echo  LessonRecorder — Local Build Script
echo ====================================
echo.

:: Читаем версию
for /f "tokens=*" %%i in ('python -c "from version import __version__; print(__version__)"') do set VERSION=%%i
echo Version: %VERSION%
echo.

:: PyInstaller
echo [1/3] Running PyInstaller...
pyinstaller LessonRecorder.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller failed!
    pause
    exit /b 1
)
echo Done.
echo.

:: Inno Setup
echo [2/3] Building installer with Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)
%ISCC% installer\setup.iss
if %ERRORLEVEL% neq 0 (
    echo ERROR: Inno Setup failed! Make sure Inno Setup 6 is installed.
    echo Download: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)
echo Done.
echo.

:: Результат
echo [3/3] Finding output file...
for %%f in (dist\installer\*.exe) do (
    echo.
    echo ============================================
    echo  SUCCESS! Installer ready:
    echo  %%f
    echo ============================================
)
echo.
pause
