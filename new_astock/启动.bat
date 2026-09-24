@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [new_astock] 正在检查运行环境...
where python >nul 2>nul || (echo 未找到 Python 3.11+ & pause & exit /b 1)
where npm >nul 2>nul || (echo 未找到 Node.js/npm & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo [new_astock] 首次运行，正在创建 Python 虚拟环境...
  where uv >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv || (pause & exit /b 1)
  ) else (
    uv venv .venv || (pause & exit /b 1)
  )
)

call ".venv\Scripts\activate.bat"
python -c "import fastapi,uvicorn,sqlalchemy,httpx,apscheduler,openpyxl" >nul 2>nul
if errorlevel 1 (
  echo [new_astock] 正在安装后端依赖...
  where uv >nul 2>nul
  if errorlevel 1 (
    python -m pip install -e . || (pause & exit /b 1)
  ) else (
    uv sync || (pause & exit /b 1)
  )
)

if not exist "frontend\node_modules" (
  echo [new_astock] 正在安装前端依赖...
  call npm install --prefix frontend --no-audit --no-fund || (pause & exit /b 1)
)

echo [new_astock] 正在构建前端...
call npm run build --prefix frontend || (pause & exit /b 1)

echo [new_astock] 服务地址：http://127.0.0.1:8765
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765"
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765
endlocal
