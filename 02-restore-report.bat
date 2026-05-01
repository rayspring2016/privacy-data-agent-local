@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo Privacy Data Agent - 本地报告反脱敏
echo ========================================
echo.

if not exist ".venv\Scripts\privacy-data-agent.exe" (
  echo 尚未安装本地运行环境。
  echo 请先双击 00-install-windows.bat。
  echo.
  pause
  exit /b 1
)

set "REPORT_FILE=%~1"
if "%REPORT_FILE%"=="" (
  echo 请把待恢复的报告文件拖到本窗口，或输入完整文件路径：
  set /p "REPORT_FILE=> "
)

if "%REPORT_FILE%"=="" (
  echo 未提供报告文件路径。
  pause
  exit /b 1
)

if not exist "%REPORT_FILE%" (
  echo 报告文件不存在：%REPORT_FILE%
  pause
  exit /b 1
)

set "MAPPING_FILE=%~2"
if "%MAPPING_FILE%"=="" (
  if exist "runs\local\mapping.local.json" (
    set "MAPPING_FILE=runs\local\mapping.local.json"
    echo 已使用默认匹配文件：%MAPPING_FILE%
  ) else (
    echo 请把 mapping.local.json 或 mapping_table.csv 拖到本窗口，或输入完整文件路径：
    set /p "MAPPING_FILE=> "
  )
)

if "%MAPPING_FILE%"=="" (
  echo 未提供匹配文件路径。
  pause
  exit /b 1
)

if not exist "%MAPPING_FILE%" (
  echo 匹配文件不存在：%MAPPING_FILE%
  pause
  exit /b 1
)

set "OUTPUT_FILE=runs\local\report.restored.md"
echo.
echo 输出报告默认为：%OUTPUT_FILE%
echo 直接回车使用默认文件，或输入新的输出文件路径：
set /p "CUSTOM_OUTPUT=> "
if not "%CUSTOM_OUTPUT%"=="" set "OUTPUT_FILE=%CUSTOM_OUTPUT%"

echo.
echo 正在恢复报告，请稍候 ...
".venv\Scripts\privacy-data-agent.exe" restore "%REPORT_FILE%" --mapping "%MAPPING_FILE%" --output "%OUTPUT_FILE%"
if errorlevel 1 (
  echo.
  echo 报告恢复失败。
  pause
  exit /b 1
)

echo.
echo 报告恢复完成：%OUTPUT_FILE%
echo.
pause
