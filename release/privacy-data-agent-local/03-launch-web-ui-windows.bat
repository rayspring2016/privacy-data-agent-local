@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo Privacy Data Agent - 本地网页界面
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo 尚未安装本地运行环境。
  echo 请先双击 00-install-windows.bat。
  echo.
  pause
  exit /b 1
)

echo 正在启动本地网页界面 ...
echo 浏览器打开后即可上传 Excel/CSV 进行脱敏。
echo 如需退出，请关闭本窗口。
echo.

set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
set STREAMLIT_CLIENT_TOOLBAR_MODE=viewer

".venv\Scripts\python.exe" -m streamlit run src\privacy_data_agent\web_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false --client.toolbarMode viewer

pause
