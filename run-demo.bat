@echo off
setlocal enabledelayedexpansion
title TaxCompliance AI — Demo

echo.
echo  ================================================
echo   TaxCompliance AI  --  Local Demo  (No Docker)
echo  ================================================
echo.

:: ── Exact paths found on this machine ────────────────────────────────────────
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

set "PYTHON=C:\Users\Piyush\AppData\Local\Programs\Python\Python312\python.exe"
set "NODE_DIR=C:\Users\Piyush\OneDrive\Desktop\office work\LECTURE TIME\associate-piyus"
set "NODE=%NODE_DIR%\node.exe"
set "NPM=%NODE_DIR%\npm.cmd"
set "NPX=%NODE_DIR%\npx.cmd"

:: Add Node to PATH for child processes
set "PATH=%NODE_DIR%;%PATH%"

echo   Python : %PYTHON%
echo   Node   : %NODE%
echo   DB     : SQLite (no setup needed)
echo.

:: ── Step 1 — Python virtualenv ───────────────────────────────────────────────
echo [STEP 1/5] Python virtual environment
echo.

cd /d "%BACKEND%"

if not exist ".venv\Scripts\activate.bat" (
    echo   Creating virtualenv...
    "%PYTHON%" -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create Python venv.
        pause & exit /b 1
    )
    echo [OK] Virtualenv created
) else (
    echo [OK] Virtualenv already exists
)

call "%BACKEND%\.venv\Scripts\activate.bat"

:: ── Step 2 — Install Python packages ─────────────────────────────────────────
echo.
echo [STEP 2/5] Installing Python packages (first run takes ~2 min)
echo.

pip install -q -r "%BACKEND%\requirements.demo.txt"
if errorlevel 1 (
    echo [ERROR] pip install failed. Check internet connection.
    pause & exit /b 1
)
echo [OK] Python packages installed

:: ── Step 3 — Write backend .env (SQLite — zero setup) ────────────────────────
echo.
echo [STEP 3/5] Writing backend config (.env)
echo.

(
echo DEMO_MODE=true
echo DEBUG=false
echo SECRET_KEY=demo-local-secret-key-not-for-prod-1234567890ab
echo VAULT_MASTER_KEY=demo-local-vault-key-not-for-prod-9876543
echo VAULT_SALT=taxcompliance-demo-salt-2025
echo DATABASE_URL=sqlite+aiosqlite:///./demo.db
echo REDIS_URL=redis://localhost:6379/0
echo CELERY_BROKER_URL=redis://localhost:6379/1
echo CELERY_RESULT_BACKEND=redis://localhost:6379/2
echo GEMINI_API_KEY=
echo AI_MODEL=gemini-2.0-flash
echo AWS_ACCESS_KEY_ID=
echo AWS_SECRET_ACCESS_KEY=
echo RAZORPAY_KEY_ID=
echo RAZORPAY_KEY_SECRET=
echo RAZORPAY_WEBHOOK_SECRET=
echo DEMO_USER_EMAIL=demo@taxcomplianceai.in
echo DEMO_USER_PASSWORD=demo123
) > "%BACKEND%\.env"

echo [OK] .env written ^(using SQLite — no database server needed^)

:: ── Step 4 — Start backend ────────────────────────────────────────────────────
echo.
echo [STEP 4/5] Starting backend (FastAPI on http://localhost:8000)
echo.

del /f /q "%BACKEND%\demo.db" >nul 2>&1

start "TaxCompliance-Backend" cmd /k ^
  "cd /d "%BACKEND%" && ^
   call "%BACKEND%\.venv\Scripts\activate.bat" && ^
   echo Backend starting... && ^
   "%BACKEND%\.venv\Scripts\uvicorn.exe" main:app --host 0.0.0.0 --port 8000 --reload"

echo [OK] Backend window opened — waiting 8 seconds for startup...
timeout /t 8 /nobreak >nul

:: ── Step 5 — Start frontend ───────────────────────────────────────────────────
echo.
echo [STEP 5/5] Setting up + starting frontend (Vite on http://localhost:3000)
echo.

cd /d "%FRONTEND%"

if not exist "node_modules" (
    echo   Installing Node.js packages (first run takes ~3 min)...
    "%NPM%" install --legacy-peer-deps
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        pause & exit /b 1
    )
    echo [OK] Node packages installed
) else (
    echo [OK] node_modules already present
)

start "TaxCompliance-Frontend" cmd /k ^
  "cd /d "%FRONTEND%" && ^
   set VITE_DEMO_MODE=true && ^
   set VITE_API_URL=http://localhost:8000 && ^
   echo Frontend starting... && ^
   "%NPX%" vite --port 3000 --host"

echo.
echo  ================================================
echo   ALL DONE!
echo  ================================================
echo.
echo   Two windows are now open:
echo     "TaxCompliance-Backend"  -- FastAPI + Python
echo     "TaxCompliance-Frontend" -- React + Vite
echo.
echo   Wait ~10 more seconds, then open:
echo.
echo     http://localhost:3000
echo.
echo   Login: demo@taxcomplianceai.in / demo123
echo   Or click the amber "Enter Demo Mode" button
echo.
echo   Swagger API docs: http://localhost:8000/api/docs
echo.
echo   *** Keep this window open while using the demo ***
echo   *** Press any key here to STOP everything ***
echo.

timeout /t 10 /nobreak >nul
start "" "http://localhost:3000"

pause

:: Cleanup: kill the two windows when user presses a key
taskkill /fi "WindowTitle eq TaxCompliance-Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq TaxCompliance-Frontend*" /f >nul 2>&1
echo Demo stopped.
