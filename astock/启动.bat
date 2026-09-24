@echo off
chcp 65001 >nul
title A股复盘看盘
cd /d "%~dp0"
echo 正在启动 A股复盘看盘服务...
echo 浏览器将自动打开 http://127.0.0.1:8765
start "" http://127.0.0.1:8765
python server.py
pause
