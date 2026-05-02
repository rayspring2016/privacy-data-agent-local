#!/bin/zsh
cd "$(dirname "$0")"

echo "========================================"
echo "Privacy Data Agent - Mac 安装"
echo "========================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3。"
  echo "请先安装 Python 3.11 或更高版本："
  echo "https://www.python.org/downloads/"
  echo
  read "unused?按回车退出..."
  exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
  echo "正在创建本地运行环境 .venv ..."
  python3 -m venv .venv
  if [ $? -ne 0 ]; then
    echo "创建 .venv 失败。"
    read "unused?按回车退出..."
    exit 1
  fi
fi

echo "正在安装本地工具依赖 ..."
".venv/bin/python" -m pip install -e .
if [ $? -ne 0 ]; then
  echo "安装失败。请检查网络连接或 Python 版本。"
  read "unused?按回车退出..."
  exit 1
fi

echo
echo "安装完成。之后可双击："
echo "03-launch-web-ui-mac.command"
echo
read "unused?按回车退出..."
