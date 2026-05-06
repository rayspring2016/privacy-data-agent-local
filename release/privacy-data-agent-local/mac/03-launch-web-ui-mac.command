#!/bin/zsh
cd "$(dirname "$0")/.."

echo "========================================"
echo "Privacy Data Agent - Mac 本地网页界面"
echo "========================================"
echo

if [ ! -f ".venv/bin/python" ]; then
  echo "尚未安装本地运行环境。"
  echo "请先双击 00-install-mac.command。"
  echo
  read "unused?按回车退出..."
  exit 1
fi

echo "正在启动本地网页界面 ..."
echo "Web UI 地址: http://127.0.0.1:8501"
echo "浏览器将自动打开，也可手动访问上述地址。"
echo "如需退出，请关闭本窗口。"
echo

(sleep 6 && open http://127.0.0.1:8501) &

export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_CLIENT_TOOLBAR_MODE=viewer

".venv/bin/python" -m streamlit run src/privacy_data_agent/web_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false --client.toolbarMode viewer --server.headless true

read "unused?按回车退出..."
