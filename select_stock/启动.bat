@echo off
chcp 65001 >nul
title A股智能选股
cd /d "%~dp0"
echo 正在启动 A股智能选股服务...
echo 浏览器将自动打开 http://127.0.0.1:5188
start "" http://127.0.0.1:5188
uv run python main.py
pause