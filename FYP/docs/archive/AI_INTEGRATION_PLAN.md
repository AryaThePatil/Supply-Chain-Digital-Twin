# AI/ML/RL Integration Plan
## Digital Twin Supply Chain — Nagpur

**Timeline**: 5 days  
**Goal**: Working prediction + optimization digital twin with demonstrable, measurable results

---

## Honest Assessment of Current State

### What Works Well
- Full simulation engine: OSM road network, traffic model, weather (real IMD data), RSL physics, agent lifecycle
- InfluxDB + MQTT data pipeline: snapshots, telemetry, events all flowing
- Dashboard: map, entity panels, analytics charts
- API: complete REST layer over InfluxDB
- RL training infrastructure: RoutingEnv, OptimizationPod, train/evaluate scripts

### What Is Broken or Suboptimal

**1. RL Policy — Training-Deployment Mismatch (Critical)**  
The policy was trained in `RoutingEnv` where action 0 = "advance along pre-computed route."  
In the full simulation (`TruckAgent._check_rerouting`), action 0 = "no-op, keep current route."  
These are semantically different. The policy learned to use action 0 as a "safe move" in training,  
but in deployment it means "do nothing." This is why the comparison showed mixed results.

**2. RL Policy — Wrong Problem Formulation**  
The current formulation asks the policy to make routing decisions every 5 simulated minutes  
regardless of whether there's anything interesting happening. Most of the time, the optimal  
action is "stay on route" — so the policy learns to always output 0, which is trivially correct  
but adds no value over the heuristic.

**3. Project Bloat**  
- `FYP/cache/` — 1,530 JSON files (osmnx HTTP cache, safe to delete)
- `FYP/data/cache/` — 1,173 JSON files (duplicate osmnx cache)
- `FYP/logs/` — 100+ log files from development runs
- `FYP/scripts/archive/` — old scripts
- `FYP/check_fixes.py`, `pytest_*.txt`, `test_results*.txt` — development artifacts
- `FYP/config/*.backup` — backup files
- `FYP/docs/PHASE*_SUMMARY.md` — 5 phase summary docs (redundant with code)

**4. OBS_DIM Inconsistency**  
We changed OBS_DIM from 11 to 13 mid-session. The saved checkpoint was trained with 11 features.  
Loading it with a 13-feature policy will silently fail or produce garbage. This needs to be resolved  
before any further training or deployment.

---

## Revised Architecture: What We Actually Need

The goal is a **prediction + optimization digital twin**. That means:

1. **Prediction layer** — forecasts that agents use to make better decisions
2. **Optimization layer** — RL policy that demonstrably improves on the heuristic
3. **Measurement layer** — metrics that prove the improvement

### What Each AI Component Should Do

| Component | Role | Status | Action Needed |
|-----------|------|--------|---------------|
| `DemandForecaster` | Predict retailer demand → better reorder timing | Online learning, wired | Verify it's actually influencing reorder decisions |
| `ETAForecaster` | Predict delivery time → better dispatch decisions | Online learning, wired | Verify segment traversals are being recorded |
| `RSLForecaster` | Predict RSL at delivery → reject bad dispatches | Physics-based, wired | Already working, no action needed |
| `RoutingPolicy (PPO)` | Choose better routes under traffic/RSL pressure | Broken formulation | Redesign (see below) |

---

## Day-by-Day Plan

### Day 1: Fix the Foundation

**Morning: Resolve OBS_DIM inconsistency**
- Revert OBS_DIM back to 11 in all files (routing_env.py, optimization_pod.py, marl_env.py, truck_agent.py)
- The 250k-step checkpoint was trained with 11 features and is our best policy
- Changing to 13 features requires retraining from scratch — not worth it in 5 days

**Afternoon: Fix the training-deployment mismatch**
- The real fix is to align what the policy does in training with what it does in deployment
- In deployment, `_check_rerouting` is called every 5 minutes and the policy decides whether to deviate
- The training env should mirror this: at each step, the truck is on a route, and the policy decides to follow or deviate
- The current `RoutingEnv` already does this correctly — the issue is that action 0 in training advances the route, but in deployment it means "no-op"
- Fix: in `TruckAgent._check_rerouting`, when the policy returns action 0, explicitly advance the truck one hop along its planned route (same as training)

**Evening: Clean up project bloat**
- Delete `FYP/cache/` (1,530 files, osmnx cache — regenerated automatically)
- Delete `FYP/data/cache/` (1,173 files, duplicate)
- Archive old logs to `FYP/logs/archive/` (keep last 5)
- Delete development artifacts: `check_fixes.py`, `pytest_*.txt`, `test_results*.txt`
- Delete `FYP/config/*.backup`

### Day 2: Retrain and Validate

**Morning: Retrain with fixed environment**
- Increase route pool to 200 routes (cached to disk, one-time cost)
- Train 250k steps with corrected action semantics
- Evaluate: target >25% delivery rate vs 0% random

**Afternoon: Fix the comparison script**
- Fix RSL capture (capture before unloading, not after)
- Add more metrics: average delivery time, route deviation frequency, RSL improvement
- Run 3-day comparison with seed 42

**Evening: Verify online learners are working**
- Check that `DemandForecaster` is receiving sale events and updating
- Check that `ETAForecaster` is receiving segment traversals and updating
- Add a simple log line showing when each forecaster switches from fallback to learned mode

### Day 3: Dashboard AI Panel

The dashboard currently shows operational data (trucks, inventory, weather).  
It needs an AI panel to show that the prediction + optimization layer is active and useful.

**Components to add:**
1. **Demand Forecast Panel** — for each retailer, show predicted demand vs actual demand
2. **RSL Risk Panel** — show which trucks have cargo at risk of spoilage before delivery
3. **RL Routing Activity** — show how often the RL policy deviates from the heuristic route and whether it helps

**Implementation:**
- Add 3 new API endpoints: `/api/ai/demand-forecast`, `/api/ai/rsl-risk`, `/api/ai/routing-stats`
- Add `AIPanel` component to dashboard
- Wire to existing `AIManager` data

### Day 4: Full Integration Test

**Run a 7-day simulation with everything enabled:**
- RL routing: enabled
- Demand forecasting: online learning active
- ETA forecasting: online learning active
- RSL prediction: active

**Collect and document results:**
- Service level % (baseline vs RL)
- Average RSL at delivery (baseline vs RL)
- Stockout frequency (baseline vs RL)
- Demand forecast accuracy (MAPE after 24h of learning)
- ETA forecast accuracy (MAE after 50 segment traversals)

### Day 5: Polish and Documentation

- Fix any remaining bugs found during Day 4 testing
- Update README with how to run the full system
- Write a brief results summary (not a full report, just the key numbers)
- Make sure the dashboard looks presentable for demonstration

---

## What We Are NOT Doing (and Why)

**Not building separate training environments for warehouse/retailer agents**  
These agents use rule-based policies (s,S inventory, priority dispatch) that are already well-calibrated.  
Adding RL to them would require months of training and would likely perform worse than the heuristics  
for a supply chain with this level of complexity. The value-add is not worth the time cost.

**Not training for seasonal variation**  
The route pool covers all 12 months via random time sampling. Seasonal variation in routing decisions  
is minimal — traffic patterns matter more than season. The demand forecaster handles seasonality.

**Not implementing MARL (multi-agent RL)**  
True MARL (where agents learn to coordinate) requires joint training that is computationally  
infeasible on a laptop in 5 days. The current architecture (independent per-truck policy with  
shared weights) is the correct approach for this scale.

---

## Project Structure After Cleanup

```
FYP/
├── api/                    # FastAPI backend
├── config/                 # YAML configs (no backups)
├── dashboard_v2/           # React frontend
├── data/
│   ├── Datasets/           # OSM files
│   └── processed/          # Weather, traffic parquet files
├── docs/                   # This plan + startup guide
├── logs/                   # Last 5 simulation logs only
├── models/
│   └── rl/                 # PPO checkpoint + route pool
├── scripts/                # train, evaluate, compare
├── src/
│   ├── data/               # Loaders, config, MQTT
│   ├── simulation/         # Engine, agents, models, network
│   └── utils/              # Logger
├── tests/                  # Unit + integration tests
├── main.py
├── requirements.txt
└── docker-compose.yml
```

Removed:
- `cache/` (1,530 files) — osmnx HTTP cache, auto-regenerated
- `data/cache/` (1,173 files) — duplicate
- `logs/` old files — keep last 5
- Development artifacts: `check_fixes.py`, `pytest_*.txt`, `test_results*.txt`, `AUDIT_REPORT.md`
- Config backups: `*.backup`
- Old scripts: `scripts/archive/`, `fix_indent.py`, `fix_rel_imports.py`, `refactor_codebase.py`, `update_imports.py`

---

## Key Technical Decisions

### Why OBS_DIM stays at 11
The 250k-step checkpoint is our best trained policy. Changing OBS_DIM to 13 requires retraining  
from scratch. The two new features (route_progress, hops_remaining) are useful but not worth  
losing the trained weights. We can add them in a future training run after submission.

### Why the RL formulation is correct but the deployment is wrong
The `RoutingEnv` correctly models the problem: truck has a route, policy decides to follow or deviate.  
The bug is in `TruckAgent._check_rerouting`: when action == 0, the truck should advance one hop  
along its planned route (as in training), not do nothing. This is a 3-line fix.

### Why we use a route pool instead of on-demand A*
A* on the 77k-node Nagpur graph takes ~800ms per call. With 200 routes pre-computed and cached,  
reset() is O(1) and training runs at 640 steps/sec. The pool covers enough diversity for the policy  
to generalise to unseen routes in the full simulation.

---

## Success Criteria

The project is "done" when:
1. RL policy consistently outperforms baseline on at least 3 of 5 metrics in a 3-day comparison
2. Dashboard shows live AI predictions (demand forecast, RSL risk)
3. System runs end-to-end without crashes for a 7-day simulation
4. README explains how to start the full system in 3 commands
