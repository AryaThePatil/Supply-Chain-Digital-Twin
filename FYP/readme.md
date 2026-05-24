# 🍊 Cognitive Digital Twin — Nagpur Orange Supply Chain
### Final Year Project | Computer Engineering | RTMNU Nagpur

A real-time supply chain digital twin simulating the orange distribution network in Nagpur, India. Features autonomous warehouse, truck, and retailer agents, PPO-based RL routing, live weather/accident disruptions, and a React dashboard.

---

## 📋 Prerequisites

Install these before anything else:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.10+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop/ |

---

## ⚡ Quick Setup (First Time Only)

### Step 1 — Install Python dependencies
```bash
cd FYP
pip install -r requirements.txt
pip install stable-baselines3 torch --index-url https://download.pytorch.org/whl/cpu
```

### Step 2 — Install Dashboard dependencies
```bash
cd dashboard_v2
npm install
cd ..
```

### Step 3 — Copy environment file
```bash
copy .env.example .env
```
The default values in `.env.example` work out of the box with Docker — no changes needed.

---

## 🚀 Running the Simulation (Every Session)

Open **4 separate terminals** in the `FYP/` folder:

### Terminal 1 — Start Docker infrastructure
```bash
docker-compose up -d
```
Wait ~30 seconds. Verify all services are up: `docker-compose ps`
> Starts: InfluxDB (port 8086), Mosquitto MQTT (1883), Telegraf, FastAPI (8000)

### Terminal 2 — Start the Dashboard
```bash
cd dashboard_v2
npm run dev
```
Open browser: **http://localhost:5173**

### Terminal 3 — Run the Simulation (with live dashboard)
```bash
python main.py --duration-days 7 --speed 10 --start-date 2023-07-15
```

### Terminal 4 — (Optional) API hot-reload for development
```bash
cd api
uvicorn main:app --reload
```

---

## 🎯 Useful Simulation Scenarios

```bash
# Monsoon stress test (rain, accidents, RSL degradation)
python main.py --duration-days 7 --speed 10 --start-date 2023-07-15

# Winter fog scenario
python main.py --duration-days 7 --speed 10 --start-date 2023-01-10

# Summer heat (fast RSL degradation)
python main.py --duration-days 7 --speed 10 --start-date 2023-05-01

# Headless benchmark (no dashboard, max speed - for long runs)
python main.py --headless --duration-days 30 --seed 42 --start-date 2023-01-01

# RL vs Baseline benchmark (runs both phases automatically)
RUN_BENCHMARK.bat        # Windows: double-click this file
```

---

## 🧠 Simulation CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--duration-days` | 7 | How many days to simulate |
| `--time-step` | 5 | Minutes per simulation tick |
| `--seed` | random | Fix seed for reproducibility |
| `--start-date` | 2023-01-01 | Season start (affects weather/demand) |
| `--speed` | max | Real-time pacing (10 = 10× faster) |
| `--headless` | off | No InfluxDB/MQTT, max CPU speed |

---

## 🗂️ Project Structure

```
FYP/
├── main.py                          # Simulation entry point
├── RUN_BENCHMARK.bat                # Double-click to run RL vs Baseline benchmark
├── requirements.txt                 # Python dependencies
├── docker-compose.yml               # Infrastructure services
├── config/
│   └── simulation_config.yaml       # All simulation parameters (edit this)
├── src/
│   └── simulation/
│       ├── engine.py                # Core simulation loop
│       ├── agents/                  # WarehouseAgent, RetailerAgent, TruckAgent
│       ├── network/                 # Road network (OSM), A* Router, Traffic
│       ├── environment_models.py    # Weather + Disruption (accidents)
│       ├── business_models.py       # Demand, Inventory, RSL models
│       ├── optimization_pod.py      # PPO RL agent (Stable-Baselines3)
│       ├── prediction_pod.py        # Demand forecasting + ETA prediction
│       └── edge_brain.py            # On-truck EdgeAI decision making
├── api/                             # FastAPI backend (reads InfluxDB → dashboard)
├── dashboard_v2/                    # React frontend (Vite + Leaflet + Chart.js)
├── scripts/
│   ├── run_benchmark.py             # RL vs baseline comparison runner
│   ├── analyze_longterm_sim.py      # Post-run telemetry analysis + charts
│   ├── train_rl_policy.py           # Train/continue PPO training
│   └── evaluate_rl_policy.py        # Evaluate trained PPO policy
├── models/
│   ├── rl/                          # Trained PPO checkpoints (included)
│   │   └── ppo_routing_latest.zip   # Latest trained model
│   ├── eta/                         # ETA forecaster weights
│   └── ml/                          # RSL ML model
├── data/
│   ├── cache/osm/                   # Pre-built road network cache (saves 10 min download)
│   ├── processed/weather/           # Nagpur 2023 historical weather dataset
│   └── analysis/                    # Output charts and reports (generated)
└── tests/                           # Unit tests
```

---

## 🤖 AI / RL Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **PPO Routing Agent** | Stable-Baselines3 | Optimal truck route selection |
| **Demand Forecaster** | Exponential Smoothing | Predictive inventory ordering |
| **RSL Forecaster** | Custom model | Cargo freshness prediction |
| **ETA Forecaster** | Ridge Regression | Delivery time estimation |
| **Edge Brain** | Lightweight Neural Net | Per-truck autonomous decisions |
| **EKF** | Extended Kalman Filter | Sensor-fused inventory tracking |

---

## 📊 Viewing Results After a Long Run

After `main.py --headless` completes, run the analysis script:
```bash
python scripts/analyze_longterm_sim.py
```
Charts and a summary report are saved to `data/analysis/`.

---

## ⚙️ Configuration

All simulation parameters are in `config/simulation_config.yaml`:
- Warehouse locations, capacities, and restock schedules
- Fleet size and truck types
- Demand model parameters (seasonal patterns)
- Accident rates and weather effects
- AI/RL settings (enable/disable PPO)

To **disable RL** and run heuristic-only baseline:
```yaml
ai:
  optimization:
    enabled: false
```

---

## 🐛 Troubleshooting

**Docker services not starting:**
- Make sure Docker Desktop is fully open (whale icon visible in taskbar)
- Run `docker-compose down` then `docker-compose up -d` again

**Road network takes long to load first time:**
- Normal — downloading Nagpur OSM data (~2 min). Cached after first run.
- If it fails, delete `data/cache/osm/` and retry.

**`stable-baselines3` not found:**
- Run: `pip install stable-baselines3`

**Dashboard shows no data:**
- Make sure simulation is running (Terminal 3) and Docker is up (Terminal 1)
- Check API health: http://localhost:8000/health

---

## 📁 Note on Large Data Files

The `data/Datasets/` folder (~5.3 GB of raw historical datasets) is **not included** in the shared package. The simulation runs fully without it. If needed for additional ML training, contact the project team.

---

*Built with Python 3.11, React 18, FastAPI, InfluxDB 2.7, Stable-Baselines3, OSMnx*
