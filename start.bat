@echo off
cd /d "%~dp0"

echo ============================================
echo   Accounting System - Startup Script
echo ============================================
echo.

echo [1/2] Starting backend (port 8001)...
start "Backend" cmd /k "cd /d %~dp0 && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001"

echo [2/2] Starting frontend (port 5173)...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8001/docs
echo.
echo Wait for both windows to start, then open the frontend URL.
echo Close each window to stop the corresponding service.
echo ============================================
pause