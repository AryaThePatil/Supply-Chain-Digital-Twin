# Supply Chain Digital Twin - System Startup Script
# This script starts all required services in the correct order

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Supply Chain Digital Twin - Startup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Docker Desktop
Write-Host "[1/5] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerRunning = $null
try {
    $dockerRunning = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Desktop is not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and run this script again." -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "  ✓ Docker Desktop is running" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker is not available!" -ForegroundColor Red
    pause
    exit 1
}

# Step 2: Start Docker Containers
Write-Host ""
Write-Host "[2/5] Starting Docker containers..." -ForegroundColor Yellow
try {
    docker-compose up -d mosquitto influxdb 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    
    $containers = docker ps --format "{{.Names}}" 
    if ($containers -match "dt-mosquitto" -and $containers -match "influxdb") {
        Write-Host "  ✓ MQTT Broker (dt-mosquitto) - Running on port 1883" -ForegroundColor Green
        Write-Host "  ✓ InfluxDB - Running on port 8086" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Warning: Some containers may not have started" -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERROR: Failed to start Docker containers" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

# Step 3: Start Backend API
Write-Host ""
Write-Host "[3/5] Starting Backend API (FastAPI)..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
try {
    $apiPath = ".\api"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$apiPath'; Write-Host 'Starting FastAPI Backend...' -ForegroundColor Cyan; uvicorn main:app --reload"
    Write-Host "  ✓ Backend API starting on http://localhost:8000" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Failed to start Backend API" -ForegroundColor Yellow
}

# Step 4: Start Frontend Dashboard
Write-Host ""
Write-Host "[4/5] Starting Frontend Dashboard..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
try {
    $dashboardPath = ".\dashboard_v2"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dashboardPath'; Write-Host 'Starting React Dashboard...' -ForegroundColor Cyan; npm run dev"
    Write-Host "  ✓ Frontend Dashboard starting on http://localhost:5173" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Failed to start Frontend Dashboard" -ForegroundColor Yellow
}

# Step 5: Ask about Simulation
Write-Host ""
Write-Host "[5/5] Simulation Setup" -ForegroundColor Yellow
Write-Host "Do you want to start the simulation now? (Y/N)" -ForegroundColor Cyan
$response = Read-Host

if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host "  Starting simulation..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    try {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Simulation...' -ForegroundColor Cyan; python main.py"
        Write-Host "  ✓ Simulation started" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Failed to start Simulation" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⊗ Simulation not started (you can run 'python main.py' manually)" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "System Startup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services running:" -ForegroundColor White
Write-Host "  • MQTT Broker:  localhost:1883" -ForegroundColor White
Write-Host "  • InfluxDB:     http://localhost:8086" -ForegroundColor White
Write-Host "  • Backend API:  http://localhost:8000" -ForegroundColor White
Write-Host "  • Dashboard:    http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Open http://localhost:5173 in your browser to view the dashboard!" -ForegroundColor Cyan
Write-Host ""
pause
