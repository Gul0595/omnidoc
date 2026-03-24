@echo off
echo.
echo ========================================
echo   OmniDoc Setup — Windows 11 + RTX 4050
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1 || (echo ERROR: Python not found. Install from https://python.org & pause & exit /b 1)
echo [OK] Python found

:: Check GPU
nvidia-smi >nul 2>&1 && (echo [OK] NVIDIA GPU detected) || echo [WARN] GPU not detected

:: Create venv
python -m venv venv
call venv\Scripts\activate.bat
echo [OK] Virtual environment created

:: PyTorch with CUDA 12.1 for RTX 4050
echo Installing PyTorch with CUDA 12.1...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
echo [OK] PyTorch installed

:: All other dependencies
pip install -r requirements.txt -q
echo [OK] Dependencies installed

:: Verify CUDA
python -c "import torch; print('[GPU]', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU mode')"

:: Copy .env
if not exist .env (
    copy .env.example .env
    echo [OK] .env created — EDIT IT NOW and add your API keys
) else (
    echo [OK] .env already exists
)

echo.
echo ========================================
echo   Setup complete!
echo.
echo   NEXT STEPS:
echo   1. Edit .env — add GROQ_API_KEY at minimum
echo      Get free key: https://console.groq.com
echo.
echo   2. Start infrastructure:
echo      docker-compose up -d
echo.
echo   3. Run database migrations:
echo      alembic upgrade head
echo.
echo   4. Start backend:
echo      uvicorn main:app --reload --port 8000
echo.
echo   5. Start frontend (new terminal):
echo      cd ..\frontend && npm install && npm run dev
echo.
echo   6. Open: http://localhost:3000
echo ========================================
pause
