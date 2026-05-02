@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "LOCAL_COPY=%LOCALAPPDATA%\PrivacyDataAgent\privacy-data-agent-local"

if "%SCRIPT_DIR:~0,2%"=="\\" (
  echo This tool is running from a shared/network path.
  echo Syncing latest files to local Windows folder:
  echo %LOCAL_COPY%
  echo.
  if not exist "%LOCAL_COPY%" mkdir "%LOCAL_COPY%"
  robocopy "%PROJECT_DIR%" "%LOCAL_COPY%" /E /XD .venv runs __pycache__ .git /NFL /NDL /NJH /NJS /NP
  if errorlevel 8 (
    echo Failed to copy files to local Windows folder.
    pause
    exit /b 1
  )

  if exist "%LOCAL_COPY%\windows\03-launch-web-ui-windows.bat" (
    echo Starting from local Windows folder instead:
    echo %LOCAL_COPY%
    start "Privacy Data Agent Web UI" "%LOCAL_COPY%\windows\03-launch-web-ui-windows.bat" %*
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
echo Privacy Data Agent - Local Web UI
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Local environment is not installed yet.
  echo Please double-click 00-install-windows.bat first.
  echo.
  pause
  exit /b 1
)

echo Starting local web UI ...
echo After the browser opens, upload Excel/CSV files to anonymize them.
echo Close this window to stop the web UI.
echo.
echo Web UI address: http://127.0.0.1:8501
echo Log file: web-ui.log
echo.

".venv\Scripts\python.exe" -m streamlit --version
if errorlevel 1 (
  echo Streamlit is not installed correctly.
  echo Please double-click 00-install-windows.bat again.
  echo.
  pause
  exit /b 1
)

start "Privacy Data Agent Browser" cmd /c "timeout /t 8 /nobreak >nul & start http://127.0.0.1:8501"

set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_CLIENT_TOOLBAR_MODE=viewer

".venv\Scripts\python.exe" -m streamlit run src\privacy_data_agent\web_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false --client.toolbarMode viewer --server.headless true > web-ui.log 2>&1

echo.
echo Web UI stopped or failed to start.
echo Details from web-ui.log:
type web-ui.log

pause
popd
