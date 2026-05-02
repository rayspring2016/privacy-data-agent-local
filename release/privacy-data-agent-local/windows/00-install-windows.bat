@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "LOCAL_COPY=%LOCALAPPDATA%\PrivacyDataAgent\privacy-data-agent-local"

if "%SCRIPT_DIR:~0,2%"=="\\" (
  echo This tool is running from a shared/network path:
  echo %SCRIPT_DIR%
  echo.
  echo Windows/Python may fail to create .venv there.
  echo Copying this tool to a real local Windows folder:
  echo %LOCAL_COPY%
  echo.

  if not exist "%LOCAL_COPY%" mkdir "%LOCAL_COPY%"
  robocopy "%PROJECT_DIR%" "%LOCAL_COPY%" /E /XD .venv runs __pycache__ .git /NFL /NDL /NJH /NJS /NP
  if errorlevel 8 (
    echo Failed to copy files to local Windows folder.
    pause
    exit /b 1
  )

  echo.
  echo Starting installer from the local Windows folder ...
  start "Privacy Data Agent Install" "%LOCAL_COPY%\windows\00-install-windows.bat"
  exit /b 0
)

pushd "%PROJECT_DIR%"
if errorlevel 1 (
  echo Failed to enter script directory: %~dp0
  pause
  exit /b 1
)

echo ========================================
echo Privacy Data Agent - Windows Install
echo ========================================
echo.

call :find_python
if not defined PYTHON_CMD (
  echo Python 3.11 or 3.12 x64 was not found.
  echo Trying to install Python 3.12 x64 with winget ...
  echo.
  call :install_python
  if errorlevel 1 exit /b 1
  call :find_python
)

if not defined PYTHON_CMD (
  if not "%PDA_RELAUNCHED_AFTER_PYTHON%"=="1" (
    echo Python was installed, but this window cannot find it yet.
    echo Restarting installer once to refresh PATH ...
    echo.
    set "PDA_RELAUNCHED_AFTER_PYTHON=1"
    start "Privacy Data Agent Install" "%~f0"
    exit /b 0
  ) else (
    echo Python was installed, but this window cannot find a working Python 3.11/3.12 x64.
    echo.
    echo Detected Python candidates:
    call :show_python_info "%LocalAppData%\Programs\Python\Python312\python.exe"
    call :show_python_info "%LocalAppData%\Programs\Python\Python311\python.exe"
    call :show_python_info "%ProgramFiles%\Python312\python.exe"
    call :show_python_info "%ProgramFiles%\Python311\python.exe"
    call :show_python_info "%ProgramFiles(x86)%\Python312\python.exe"
    call :show_python_info "%ProgramFiles(x86)%\Python311\python.exe"
    where python
    echo.
    echo If this is a Windows ARM virtual machine, winget may have installed ARM64 Python.
    echo This web package needs x64 Python because some dependencies do not provide Windows ARM64 wheels.
    echo Please install Python 3.11 or 3.12 x64 manually and enable "Add Python to PATH".
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
  )
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; version=sys.version.upper(); ok=(3, 11) <= sys.version_info < (3, 13) and sys.maxsize > 2**32 and ('AMD64' in version or 'X86_64' in version); raise SystemExit(0 if ok else 1)" >nul 2>&1
  if errorlevel 1 (
    echo Existing .venv uses an unsupported Python version or architecture.
    echo Recreating .venv ...
    rmdir /s /q .venv
  ) else (
    ".venv\Scripts\python.exe" -c "import streamlit; import sys; version=tuple(int(x) for x in streamlit.__version__.split('.')[:2]); raise SystemExit(0 if version >= (1, 35) else 1)" >nul 2>&1
    if errorlevel 1 (
      echo Existing .venv has broken or outdated Streamlit.
      echo Recreating .venv ...
      rmdir /s /q .venv
    )
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local environment .venv ...
  "%PYTHON_CMD%" --version
  "%PYTHON_CMD%" -m venv .venv > install-venv.log 2>&1
  if errorlevel 1 (
    echo Failed to create .venv.
    echo.
    echo Details from install-venv.log:
    type install-venv.log
    pause
    exit /b 1
  )
)

echo Installing local package dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo Failed to upgrade pip tools.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade --only-binary=:all: "cryptography>=42.0.0" "openpyxl>=3.1.2" "pandas>=2.2.0" "pydantic>=2.7.0" "python-docx>=1.1.0" "python-pptx>=0.6.23" "streamlit>=1.35.0,<2" "typer>=0.12.3"
if errorlevel 1 (
  echo Failed to install binary package dependencies.
  echo This usually means Python is too new or pip cannot access prebuilt Windows wheels.
  echo Please use Python 3.11 or 3.12 on Windows.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --no-deps -e .
if errorlevel 1 (
  echo Install failed. Please check your network connection and Python version.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import streamlit; print('Streamlit', streamlit.__version__)"
if errorlevel 1 (
  echo Streamlit validation failed.
  pause
  exit /b 1
)

echo.
echo Install complete. You can now double-click:
echo windows\01-anonymize-data.bat  anonymize data
echo windows\02-restore-report.bat  restore a report
echo windows\03-launch-web-ui-windows.bat  open web UI
echo.
pause
popd
exit /b 0

:find_python
set "PYTHON_CMD="

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  call :validate_python "%LocalAppData%\Programs\Python\Python312\python.exe"
  if defined PYTHON_CMD exit /b 0
)

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  call :validate_python "%LocalAppData%\Programs\Python\Python311\python.exe"
  if defined PYTHON_CMD exit /b 0
)

if exist "%ProgramFiles%\Python312\python.exe" (
  call :validate_python "%ProgramFiles%\Python312\python.exe"
  if defined PYTHON_CMD exit /b 0
)

if exist "%ProgramFiles%\Python311\python.exe" (
  call :validate_python "%ProgramFiles%\Python311\python.exe"
  if defined PYTHON_CMD exit /b 0
)

if exist "%ProgramFiles(x86)%\Python312\python.exe" (
  call :validate_python "%ProgramFiles(x86)%\Python312\python.exe"
  if defined PYTHON_CMD exit /b 0
)

if exist "%ProgramFiles(x86)%\Python311\python.exe" (
  call :validate_python "%ProgramFiles(x86)%\Python311\python.exe"
  if defined PYTHON_CMD exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
  call :validate_python python
  if defined PYTHON_CMD exit /b 0
)

exit /b 0

:validate_python
"%~1" -c "import sys; version=sys.version.upper(); ok=(3, 11) <= sys.version_info < (3, 13) and sys.maxsize > 2**32 and ('AMD64' in version or 'X86_64' in version); raise SystemExit(0 if ok else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=%~1"
)
exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 (
  echo winget was not found on this computer.
  echo Please install Python 3.11 or 3.12 and enable "Add Python to PATH".
  echo Download: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

winget install --id Python.Python.3.12 -e --source winget --architecture x64
if errorlevel 1 (
  echo Python x64 install failed.
  echo Please install Python 3.11 or 3.12 x64 manually and enable "Add Python to PATH".
  echo Download: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

exit /b 0

:show_python_info
if exist "%~1" (
  echo %~1
  "%~1" -c "import platform, sys; print('  version:', sys.version.split()[0]); print('  machine:', platform.machine()); print('  executable:', sys.executable)" 2>nul
)
exit /b 0
