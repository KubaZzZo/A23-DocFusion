@echo off
chcp 65001 >nul
echo ============================================
echo   DocFusion 打包脚本
echo ============================================
echo.

:: 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] 正在安装 PyInstaller...
    pip install pyinstaller
)

:: 清理旧构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [INFO] 开始打包...
echo.

pyinstaller DocFusion.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败，请检查错误信息
    pause
    exit /b 1
)

:: 创建数据目录
mkdir dist\DocFusion\data 2>nul
mkdir dist\DocFusion\data\uploads 2>nul
mkdir dist\DocFusion\data\outputs 2>nul
mkdir dist\DocFusion\data\crawled 2>nul
mkdir dist\DocFusion\data\backups 2>nul
mkdir dist\DocFusion\data\cache 2>nul
mkdir dist\DocFusion\data\logs 2>nul

echo.
echo ============================================
echo   打包完成!
echo   输出目录: dist\DocFusion\
echo   启动程序: dist\DocFusion\DocFusion.exe
echo ============================================
pause
