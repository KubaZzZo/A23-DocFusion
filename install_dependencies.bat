@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title DocFusion Dependency Installer

cd /d "%~dp0"

if /i "%~1"=="--install-tesseract-only" goto :install_tesseract_elevated

echo ============================================
echo   DocFusion - Dependency Installer
echo ============================================
echo.

set "PYTHON_CMD="
set "PIP_INSTALL="

call :detect_python
if errorlevel 1 goto :fail

echo [1/3] Detecting Python...
echo [ OK ] Using interpreter: !PYTHON_CMD!
echo.

echo [2/3] Installing requirements.txt...
!PIP_INSTALL! -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install Python dependencies.
    echo [ERROR] Please check your network or pip configuration.
    goto :fail
)
echo [ OK ] requirements.txt installed
echo.

echo [3/4] Verifying core imports...
!PYTHON_CMD! -c "import PyQt6, fastapi, sqlalchemy, openpyxl, docx, fitz, httpx, bs4, openai, pydantic, PIL, pytesseract; print('imports ok')"
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency verification failed.
    echo [ERROR] Please check the error output above.
    goto :fail
)
echo [ OK ] Core imports verified
echo.

echo [4/4] Checking Tesseract-OCR...
call :detect_tesseract
if defined TESSERACT_CMD_FOUND (
    echo [ OK ] Tesseract-OCR detected: !TESSERACT_CMD_FOUND!
) else (
    echo [INFO] Tesseract-OCR not found. Attempting automatic install...
    call :install_tesseract
    if errorlevel 1 (
        echo [WARN] Automatic Tesseract installation did not complete.
        echo [WARN] Manual download: https://github.com/UB-Mannheim/tesseract/wiki
    ) else (
        call :detect_tesseract
        if defined TESSERACT_CMD_FOUND (
            echo [ OK ] Tesseract-OCR installed: !TESSERACT_CMD_FOUND!
        ) else (
            echo [WARN] Install command finished, but Tesseract is still not detected in this shell.
            echo [WARN] You may need to reopen the terminal or set TESSERACT_CMD manually.
        )
    )
)
echo.
echo ============================================
echo   Install complete
echo   Next step: run start_docfusion.bat
echo ============================================
pause
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
    set "PIP_INSTALL=%~1 -m pip install"
) else (
    set "PYTHON_CMD=%~1 %~2"
    set "PIP_INSTALL=%~1 %~2 -m pip install"
)
exit /b 0

:detect_tesseract
set "TESSERACT_CMD_FOUND="
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    set "TESSERACT_CMD_FOUND=C:\Program Files\Tesseract-OCR\tesseract.exe"
    exit /b 0
)
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" (
    set "TESSERACT_CMD_FOUND=C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    exit /b 0
)
for /f "delims=" %%T in ('where tesseract 2^>nul') do (
    set "TESSERACT_CMD_FOUND=%%T"
    exit /b 0
)
exit /b 1

:install_tesseract
where winget >nul 2>&1
if errorlevel 1 (
    echo [WARN] winget is not available on this system.
    exit /b 1
)
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Requesting administrator permission for Tesseract install...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--install-tesseract-only' -Verb RunAs -Wait"
    exit /b %errorlevel%
)
goto :install_tesseract_elevated

:install_tesseract_elevated
echo [INFO] Installing Tesseract-OCR with winget...
winget install --id=UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
exit /b %errorlevel%

:fail
echo.
echo ============================================
echo   Install incomplete
echo ============================================
pause
exit /b 1
