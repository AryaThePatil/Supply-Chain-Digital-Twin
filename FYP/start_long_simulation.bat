@echo off
echo ====================================================
echo      Starting Long-Running Presentation Simulation
echo ====================================================

echo Starting Simulation Engine (Data Generation) for 365 Days at 1x Speed...
start cmd /k "title Digital Twin Slow Simulation && cd C:\Users\aryap\OneDrive\Desktop\Arya_College\FYP_Dynamic\FYP && python main.py --duration-days 365 --speed 1 --time-step 1"

echo.
echo Simulation has been launched in a new window!
echo It will now run continuously for hours.
echo.
pause
