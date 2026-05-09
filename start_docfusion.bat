@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title DocFusion One-Click Start

cd /d "%~dp0"

echo ============================================
echo   DocFusion - One-Click Start
echo ============================================
echo.

set "PYTHON_CMD="

call :detect_python
if errorlevel 1 goto :fail

echo [1/4] Detecting Python...
echo [ OK ] Using interpreter: !PYTHON_CMD!
echo.

echo [2/4] Checking core dependencies...
!PYTHON_CMD! -c "import PyQt6, fastapi, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Core dependencies are missing.
    echo [ERROR] Please run install_dependencies.bat first.
    goto :fail
)
echo [ OK ] Core dependencies are ready
echo.

echo [3/4] Checking optional OCR environment...
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [ OK ] Default Tesseract-OCR detected
) else (
    echo [INFO] Default Tesseract-OCR not found.
    echo [INFO] Image OCR may be unavailable until Tesseract is installed.
)
echo.

echo [4/4] Starting DocFusion...
echo [INFO] Local API: http://127.0.0.1:8000
echo [INFO] API docs : http://127.0.0.1:8000/docs
echo.
!PYTHON_CMD! main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Project startup failed.
    echo [ERROR] Please check the error output above.
    goto :fail
)
exit /b 0

:detect_python
call :try_python "py" "-3.13"
if defined PYTHON_CMD exit /b 0
call :try_python "py" "-3.12"
if defined PYTHON_CMD exit /b 0
call :try_python "py"
if defined PYTHON_CMD exit /b 0
call :try_python "python"
if defined PYTHON_CMD exit /b 0
echo [ERROR] No usable Python interpreter was found.
echo [ERROR] Please install Python 3.12 or 3.13 first.
exit /b 1

:try_python
%~1 %~2 --version >nul 2>&1
if errorlevel 1 exit /b 0
if "%~2"=="" (
    set "PYTHON_CMD=%~1"
) else (
    set "PYTHON_CMD=%~1 %~2"
)
exit /b 0

:fail
echo.
echo ============================================
echo   Start incomplete
echo ============================================
pause
exit /b 1
