@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "LOCAL_COPY=%LOCALAPPDATA%\PrivacyDataAgent\privacy-data-agent-local"

if "%SCRIPT_DIR:~0,2%"=="\\" (
  if exist "%LOCAL_COPY%\windows\02-restore-report.bat" (
    echo This tool is running from a shared/network path.
    echo Starting from local Windows folder instead:
    echo %LOCAL_COPY%
    start "Privacy Data Agent Restore" "%LOCAL_COPY%\windows\02-restore-report.bat" %*
    exit /b 0
  )
)

pushd "%PROJECT_DIR%"
if errorlevel 1 (
  echo Failed to enter script directory: %~dp0
  pause
  exit /b 1
)

echo ========================================
echo Privacy Data Agent - Local Report Restore
echo ========================================
echo.

if not exist ".venv\Scripts\privacy-data-agent.exe" (
  echo Local environment is not installed yet.
  echo Please double-click 00-install-windows.bat first.
  echo.
  pause
  exit /b 1
)

set "REPORT_FILE=%~1"
if "%REPORT_FILE%"=="" (
  echo Drag the report file into this window, or type the full file path:
  set /p "REPORT_FILE=> "
)

if "%REPORT_FILE%"=="" (
  echo No report file path was provided.
  pause
  exit /b 1
)

if not exist "%REPORT_FILE%" (
  echo Report file does not exist: %REPORT_FILE%
  pause
  exit /b 1
)

set "MAPPING_FILE=%~2"
if "%MAPPING_FILE%"=="" (
  if exist "runs\local\mapping.local.json" (
    set "MAPPING_FILE=runs\local\mapping.local.json"
    echo Using default mapping file: %MAPPING_FILE%
  ) else (
    echo Drag mapping.local.json or mapping_table.csv into this window, or type the full file path:
    set /p "MAPPING_FILE=> "
  )
)

if "%MAPPING_FILE%"=="" (
  echo No mapping file path was provided.
  pause
  exit /b 1
)

if not exist "%MAPPING_FILE%" (
  echo Mapping file does not exist: %MAPPING_FILE%
  pause
  exit /b 1
)

set "OUTPUT_FILE=runs\local\report.restored.md"
echo.
echo Default output report: %OUTPUT_FILE%
echo Press Enter to use the default, or type another output file path:
set /p "CUSTOM_OUTPUT=> "
if not "%CUSTOM_OUTPUT%"=="" set "OUTPUT_FILE=%CUSTOM_OUTPUT%"

echo.
echo Restoring report, please wait ...
".venv\Scripts\privacy-data-agent.exe" restore "%REPORT_FILE%" --mapping "%MAPPING_FILE%" --output "%OUTPUT_FILE%"
if errorlevel 1 (
  echo.
  echo Report restore failed.
  pause
  exit /b 1
)

echo.
echo Report restore complete: %OUTPUT_FILE%
echo.
pause
popd
