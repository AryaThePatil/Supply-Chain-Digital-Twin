@echo off
echo =========================================================
echo       DIGITAL TWIN PIPELINE: TRAINING ^& BENCHMARK
echo =========================================================
echo.
echo Step 1: Training the PPO Neural Network (50,000 steps)...
echo This takes approximately ~70 minutes.
python scripts\train_rl_policy.py --steps 50000

echo.
echo Step 2: Running the 30-Day Academic Benchmark...
echo This will run both Baseline and RL architectures side-by-side.
echo This takes approximately ~1.5 hours.
python scripts\run_benchmark.py

echo.
echo Step 3: Analyzing Telemetry Data and Generating Final Report...
python scripts\final_analysis.py

echo.
echo =========================================================
echo FINAL PIPELINE COMPLETE.
echo Please review data\analysis\benchmark_final_opt_results.txt
echo =========================================================
pause
