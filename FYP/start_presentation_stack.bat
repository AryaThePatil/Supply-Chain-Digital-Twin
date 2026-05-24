@echo off
echo ====================================================
echo      Starting Digital Twin Presentation Stack
echo ====================================================

echo [1/3] Starting Backend API (Port 8000)...
start cmd /k "title Digital Twin API && cd C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP\api && python -m uvicorn main:app --port 8000"

echo [2/3] Starting Frontend Dashboard (Port 5173)...
start cmd /k "title Digital Twin Dashboard && cd C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP\dashboard_v2 && npm run dev"

echo [3/3] Starting Simulation Engine (Data Generation)...
start cmd /k "title Digital Twin Simulation Engine && cd C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP && python main.py --duration-days 30 --speed 5 --time-step 1"

echo.
echo All processes have been launched in separate windows!
echo Please wait 30 seconds for the database to populate, then open:
echo http://localhost:5173
echo.
pause
