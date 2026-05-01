@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo Privacy Data Agent - 本地数据脱敏
echo ========================================
echo.

if not exist ".venv\Scripts\privacy-data-agent.exe" (
  echo 尚未安装本地运行环境。
  echo 请先双击 00-install-windows.bat。
  echo.
  pause
  exit /b 1
)

set "INPUT_FILE=%~1"
if "%INPUT_FILE%"=="" (
  echo 请把 CSV/XLSX 文件拖到本窗口，或输入完整文件路径：
  set /p "INPUT_FILE=> "
)

if "%INPUT_FILE%"=="" (
  echo 未提供文件路径。
  pause
  exit /b 1
)

if not exist "%INPUT_FILE%" (
  echo 文件不存在：%INPUT_FILE%
  pause
  exit /b 1
)

set "OUTPUT_DIR=runs\local"
echo.
echo 输出目录默认为：%OUTPUT_DIR%
echo 直接回车使用默认目录，或输入新的输出目录：
set /p "CUSTOM_OUTPUT=> "
if not "%CUSTOM_OUTPUT%"=="" set "OUTPUT_DIR=%CUSTOM_OUTPUT%"

echo.
echo 正在脱敏，请稍候 ...
".venv\Scripts\privacy-data-agent.exe" anonymize "%INPUT_FILE%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 (
  echo.
  echo 脱敏失败。
  pause
  exit /b 1
)

echo.
echo 脱敏完成。
echo 脱敏文件：%OUTPUT_DIR%\anonymized.csv
echo 匹配文件：%OUTPUT_DIR%\mapping.local.json
echo 匹配表：%OUTPUT_DIR%\mapping_table.csv
echo.
echo 注意：匹配文件和匹配表包含原始敏感信息，只能保存在本地。
echo.
pause
