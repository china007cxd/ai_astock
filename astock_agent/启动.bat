@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title A股选股 Agent
cd /d "%~dp0"

echo ================================================
echo   A股选股 Agent 一键启动（先 astock 后 agent）
echo ================================================

rem 1. 检查 astock 数据服务(8765)是否已在运行
curl -s -m 2 -o nul http://127.0.0.1:8765/api/dates
if !errorlevel!==0 (
  echo [1/3] astock 数据服务已在运行 (8765)
  goto agent
)
echo [1/3] astock 未运行，正在后台启动 ..\astock ...
set "ASTOCK_DIR=%~dp0..\astock"
start "astock" /D "%ASTOCK_DIR%" cmd /c "python server.py"

set /a tries=0
:wait_astock
curl -s -m 2 -o nul http://127.0.0.1:8765/api/dates
if !errorlevel!==0 goto astock_ok
set /a tries+=1
if !tries! geq 30 (
  echo [错误] astock 30 秒内未就绪，请手动运行 astock\启动.bat 后重试
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_astock
:astock_ok
echo [1/3] astock 已就绪 (8765)

:agent
rem 2. 启动 agent (8766)
echo [2/3] 正在启动 A股选股 Agent (8766)...
echo [3/3] 浏览器将自动打开 http://127.0.0.1:8766
start "" http://127.0.0.1:8766
uv run uvicorn astock_agent.main:app --host 127.0.0.1 --port 8766
pause
