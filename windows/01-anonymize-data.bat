@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "LOCAL_COPY=%LOCALAPPDATA%\PrivacyDataAgent\privacy-data-agent-local"

if "%SCRIPT_DIR:~0,2%"=="\\" (
  if exist "%LOCAL_COPY%\windows\01-anonymize-data.bat" (
    echo This tool is running from a shared/network path.
    echo Starting from local Windows folder instead:
    echo %LOCAL_COPY%
    start "Privacy Data Agent Anonymize" "%LOCAL_COPY%\windows\01-anonymize-data.bat" %*
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
echo Privacy Data Agent - Local Data Anonymize
echo ========================================
echo.

if not exist ".venv\Scripts\privacy-data-agent.exe" (
  echo Local environment is not installed yet.
  echo Please double-click 00-install-windows.bat first.
  echo.
  pause
  exit /b 1
)

set "INPUT_FILE=%~1"
if "%INPUT_FILE%"=="" (
  echo Drag a CSV/XLSX file into this window, or type the full file path:
  set /p "INPUT_FILE=> "
)

if "%INPUT_FILE%"=="" (
  echo No file path was provided.
  pause
  exit /b 1
)

if not exist "%INPUT_FILE%" (
  echo File does not exist: %INPUT_FILE%
  pause
  exit /b 1
)

set "OUTPUT_DIR=runs\local"
echo.
echo Default output directory: %OUTPUT_DIR%
echo Press Enter to use the default, or type another output directory:
set /p "CUSTOM_OUTPUT=> "
if not "%CUSTOM_OUTPUT%"=="" set "OUTPUT_DIR=%CUSTOM_OUTPUT%"

echo.
echo Anonymizing data, please wait ...
".venv\Scripts\privacy-data-agent.exe" anonymize "%INPUT_FILE%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 (
  echo.
  echo Anonymize failed.
  pause
  exit /b 1
)

echo.
echo Anonymize complete.
echo Anonymized file: %OUTPUT_DIR%\anonymized.csv or %OUTPUT_DIR%\anonymized.xlsx
echo Mapping file: %OUTPUT_DIR%\mapping.local.json
echo Mapping table: %OUTPUT_DIR%\mapping_table.csv
echo.
echo Note: mapping files contain original sensitive data. Keep them local only.
echo.
pause
popd
