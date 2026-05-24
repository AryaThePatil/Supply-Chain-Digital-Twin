@echo off
echo ====================================================================
echo FULL YEAR (365-DAY) BENCHMARKING PIPELINE
echo Note: PPO Training is skipped because the AI is already perfectly trained.
echo Expected Duration: ~28 to 30 Hours
echo ====================================================================

REM Step 1: Run Baseline and RL benchmarks for 365 days
echo.
echo [1/2] Running 365-Day Benchmarks (Baseline followed by RL)...
python scripts/run_benchmark.py
if errorlevel 1 goto error

REM Step 2: Run final analysis and generate graphs
echo.
echo [2/2] Running Final Analysis and generating 365-Day Report...
python scripts/final_analysis.py
if errorlevel 1 goto error

echo.
echo ====================================================================
echo PIPELINE COMPLETE!
echo Check data\analysis\benchmark_final_opt_results.txt for the final 1-Year data!
echo ====================================================================
pause
exit /b 0

:error
echo.
echo ====================================================================
echo PIPELINE FAILED!
echo An error occurred during the 365-Day execution.
echo ====================================================================
pause
exit /b 1
