@echo off
echo ====================================================
echo      Starting 10x Speed Presentation Simulation
echo ====================================================

echo Starting Simulation Engine (Data Generation) for 365 Days at 10x Speed...
start cmd /k "title Digital Twin 10x Simulation && cd C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP && python main.py --duration-days 365 --speed 10 --time-step 1"

echo.
echo Simulation has been launched in a new window at 10x speed!
echo.
pause
