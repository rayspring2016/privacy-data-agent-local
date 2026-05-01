@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo Privacy Data Agent - Windows 安装
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  ) else (
    echo 未找到 Python。
    echo 请先安装 Python 3.11 或更高版本，并勾选 Add Python to PATH。
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建本地运行环境 .venv ...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo 创建 .venv 失败。
    pause
    exit /b 1
  )
)

echo 正在安装本地工具依赖 ...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
  echo 安装失败。请检查网络连接或 Python 版本。
  pause
  exit /b 1
)

echo.
echo 安装完成。之后可双击：
echo 01-anonymize-data.bat  进行脱敏
echo 02-restore-report.bat  进行报告反脱敏
echo.
pause
