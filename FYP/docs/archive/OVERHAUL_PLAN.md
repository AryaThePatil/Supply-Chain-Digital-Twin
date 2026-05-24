# Digital Twin Upgrade Plan
## 4-5 Day Execution Plan — Audited and Corrected

**Goal:** Upgrade from simulation to digital twin by fixing bugs, training the RL policy, and adding AI prediction visibility + scenario control to the dashboard.

**Date:** April 1, 2026 (Audited)
**Time budget:** 4-5 days

---

## What's Already Done (Don't Touch)

- Turbo-optimized simulation (1000× real-time speed) ✅
- All agents: TruckAgent, WarehouseAgent, RetailerAgent, AIManager ✅
- Physics: Arrhenius RSL decay, Greenshields traffic, driver fatigue ✅
- AI components: RSLForecaster, ETAForecaster, DemandForecaster ✅
- RL architecture: PPO strategy-selection (N_ACTIONS=3) ✅
- Dashboard: Map, entity panels, analytics tab, weather panel ✅
- TruckList already shows RSL predictions + RL reroute count per truck ✅
- API: `/ai/truck-predictions`, `/ai/retailer-predictions`, `/ai/weather-forecast` ✅
- 69/69 unit tests passing ✅

---

## Phase 1: Fix Critical Bug + Train + Benchmark
**Estimated time:** 3-4 hours (mostly waiting for training)

### Task 1.1 — Fix RL dispatch bug
**File:** `FYP/src/simulation/agents/truck_agent.py`
**Method:** `assign_delivery()` — lines ~1140-1200

The RL strategy is never applied at dispatch. The initial route always uses default weights. Fix: query the RL policy before calling `router.find_path()`.

**Exact change** — add this block BEFORE the existing `route = self.router.find_path(...)` call:

```python
# Query RL policy for initial routing strategy (if enabled)
cost_weights = None
if self.ai_manager is not None and self.ai_manager.optimization_pod.enabled:
    obs = self._build_obs(current_time)
    if obs is not None:
        action = self.ai_manager.select_routing_action(self.truck.truck_id, obs)
        strategy_names = ['balanced', 'speed', 'fuel']
        strategy_name = strategy_names[action] if action in {0, 1, 2} else 'balanced'
        strategies = self.config.get('routing', {}).get('strategies', {})
        default_weights = [
            {'distance_km': 1.0, 'time_minutes': 0.5, 'fuel_liters': 2.0},
            {'distance_km': 0.5, 'time_minutes': 2.0, 'fuel_liters': 0.5},
            {'distance_km': 1.0, 'time_minutes': 0.3, 'fuel_liters': 4.0},
        ]
        cost_weights = strategies.get(strategy_name, default_weights[action])
```

Then add `cost_weights=cost_weights` to the `router.find_path()` call.

### Task 1.2 — Fix `cargo_rsl` missing from dashboard state
**File:** `FYP/api/database.py`
**Method:** `get_complete_state()` — the truck_query

The `|> keep(columns: [...])` list does NOT include `cargo_rsl`. This means the map and dashboard never see RSL data. Add it:

```python
# In the truck_query keep() columns, add "cargo_rsl":
|> keep(columns: ["truck_id", "status_code", "speed_kmh", "current_load_kg", "fuel_percent", 
                 "latitude", "longitude", "timestamp", "total_distance_km", "load_factor", 
                 "cargo_batches_count", "total_deliveries", "route_progress", 
                 "assigned_order_id", "total_fuel_consumed_liters", "current_fuel_liters",
                 "cargo_rsl"])  # ← ADD THIS
```

### Task 1.3 — Enrich map truck popups with RSL
**File:** `FYP/dashboard_v2/src/components/dashboard/MapView.jsx`

The truck popup currently shows status, speed, cargo, fuel. Add RSL:

```jsx
<Popup>
  <strong>🚛 {truck.truck_id}</strong><br />
  Status: {truck.status}<br />
  Speed: {(truck.speed_kmh ?? 0).toFixed(1)} km/h<br />
  Cargo: {(truck.cargo_kg ?? 0).toFixed(0)} kg<br />
  Fuel: {(truck.fuel_percent ?? 0).toFixed(1)}%<br />
  {truck.cargo_rsl != null && (
    <>RSL: <span style={{color: truck.cargo_rsl > 70 ? '#10b981' : truck.cargo_rsl > 40 ? '#f59e0b' : '#ef4444'}}>
      {truck.cargo_rsl.toFixed(1)}%
    </span><br /></>
  )}
</Popup>
```

Note: `cargo_rsl` is now available because of Task 1.2. The `trucks` array in App.jsx maps from `data.trucks` which comes from `get_complete_state()`.

### Task 1.4 — Train PPO policy
```bash
# Delete old checkpoint (N_ACTIONS=6 incompatible with new N_ACTIONS=3)
del FYP/models/rl/ppo_routing_latest.zip

# Train (runs ~10-15 minutes)
python scripts/train_rl_policy.py --steps 200000
```

### Task 1.5 — Run benchmark
```bash
python scripts/evaluate_rl_policy.py --episodes 100
python scripts/compare_rl_vs_baseline.py --days 3 --seed 42
```

**Capture for FYP write-up:**
- Service level % (RL vs baseline)
- Avg RSL at delivery (RL vs baseline)
- Stockout count (RL vs baseline)
- Kg shipped (RL vs baseline)

---

## Phase 2: AI Insights Panel on Dashboard
**Estimated time:** 3-4 hours

**Note:** TruckList already shows per-truck RSL predictions and RL reroute counts. What's missing is:
1. A system-level view of RL strategy distribution
2. Per-retailer demand forecasts visible on the dashboard
3. A dedicated "AI Insights" tab

### Task 2.1 — New API endpoint: RL strategy activity
**File:** `FYP/api/routers/ai_insights.py`

Add endpoint `/ai/rl-activity` that returns system-level RL metrics:

```python
@router.get("/ai/rl-activity")
async def get_rl_activity(run_id: str = Query(...)) -> Dict[str, Any]:
    """System-level RL routing activity: strategy distribution and reroute counts."""
    db = get_db()
    
    # Query route_changed events with rl_strategy_ reason
    query = f'''
    from(bucket: "{db.bucket}")
        |> range(start: -7d)
        |> filter(fn: (r) => r["_measurement"] == "events")
        |> filter(fn: (r) => r["run_id"] == "{run_id}")
        |> filter(fn: (r) => r["event_type"] == "route_changed")
        |> filter(fn: (r) => r["_field"] == "reason")
    '''
    records = db.query(query)
    
    strategy_counts = {'balanced': 0, 'speed': 0, 'fuel': 0, 'heuristic': 0}
    for rec in records:
        reason = str(rec.get('_value', ''))
        if 'balanced' in reason: strategy_counts['balanced'] += 1
        elif 'speed' in reason: strategy_counts['speed'] += 1
        elif 'fuel' in reason: strategy_counts['fuel'] += 1
        else: strategy_counts['heuristic'] += 1
    
    total = sum(strategy_counts.values())
    return {
        'strategy_counts': strategy_counts,
        'total_reroutes': total,
        'strategy_pct': {k: round(v/total*100, 1) if total > 0 else 0 for k, v in strategy_counts.items()}
    }
```

### Task 2.2 — New React component: AIInsightsPanel
**File:** `FYP/dashboard_v2/src/components/panels/AIInsightsPanel.jsx`

Component that:
- Polls `/api/ai/rl-activity?run_id={runId}` every 30 seconds
- Polls `/api/ai/retailer-predictions?run_id={runId}` every 60 seconds
- Shows RL strategy distribution (balanced/speed/fuel as colored bars)
- Shows per-retailer demand forecast vs current inventory
- Shows system-level RSL health (count of ok/warn/reject trucks from TruckList data)

### Task 2.3 — Add AI Insights tab to App.jsx
Add a third tab "🤖 AI Insights" to the tab navigation. Pass `runId` and `trucks` (for RSL health summary) as props to AIInsightsPanel.

---

## Phase 3: Scenario Control Panel
**Estimated time:** 3-4 hours

**Architecture decision:** Use a shared JSON file (`data/scenario_commands.json`) instead of InfluxDB polling. The simulation and API run on the same machine, so file I/O is simpler and faster (no 50-100ms InfluxDB latency per tick).

### Task 3.1 — Scenario command file protocol
**File:** `FYP/data/scenario_commands.json` (created by API, read by engine)

Format:
```json
{
  "commands": [
    {"type": "inject_accident", "segment_id": "...", "severity": "moderate", "duration_minutes": 30, "applied": false},
    {"type": "adjust_demand", "retailer_id": "RET001", "multiplier": 2.0, "applied": false},
    {"type": "trigger_stockout", "warehouse_id": "WH001", "applied": false}
  ]
}
```

### Task 3.2 — New API endpoint: scenario injection
**File:** `FYP/api/routers/scenarios.py` (new file)

```python
from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter()
SCENARIO_FILE = Path("../data/scenario_commands.json")

@router.post("/scenarios/inject-accident")
async def inject_accident(segment_id: str, severity: str = "moderate", duration_minutes: int = 30):
    _append_command({"type": "inject_accident", "segment_id": segment_id, 
                     "severity": severity, "duration_minutes": duration_minutes, "applied": False})
    return {"status": "queued"}

@router.post("/scenarios/adjust-demand")
async def adjust_demand(retailer_id: str, multiplier: float):
    _append_command({"type": "adjust_demand", "retailer_id": retailer_id, 
                     "multiplier": multiplier, "applied": False})
    return {"status": "queued"}

@router.post("/scenarios/trigger-stockout")
async def trigger_stockout(warehouse_id: str):
    _append_command({"type": "trigger_stockout", "warehouse_id": warehouse_id, "applied": False})
    return {"status": "queued"}

def _append_command(cmd: dict):
    data = {"commands": []}
    if SCENARIO_FILE.exists():
        with open(SCENARIO_FILE) as f:
            data = json.load(f)
    data["commands"].append(cmd)
    with open(SCENARIO_FILE, "w") as f:
        json.dump(data, f)
```

Register in `api/main.py`:
```python
from routers import scenarios
app.include_router(scenarios.router, prefix="/api", tags=["Scenarios"])
```

### Task 3.3 — Engine: apply scenario commands each tick
**File:** `FYP/src/simulation/engine.py`

Add `_apply_scenario_commands()` method and call it from `step()` after `_process_events()`:

```python
def _apply_scenario_commands(self):
    """Read and apply pending scenario commands from the shared command file."""
    import json
    from pathlib import Path
    cmd_file = Path("data/scenario_commands.json")
    if not cmd_file.exists():
        return
    try:
        with open(cmd_file) as f:
            data = json.load(f)
        modified = False
        for cmd in data.get("commands", []):
            if cmd.get("applied"):
                continue
            ctype = cmd.get("type")
            if ctype == "inject_accident" and self.road_network:
                seg = self.road_network.get_segment(cmd["segment_id"])
                if seg:
                    seg.set_accident(severity=cmd.get("severity", "moderate"))
                    logger.info(f"[SCENARIO] Injected accident on {cmd['segment_id']}")
            elif ctype == "adjust_demand":
                for retailer in self.retailers:
                    if retailer.retailer_id == cmd["retailer_id"]:
                        retailer.demand_model.base_arrival_rate *= cmd.get("multiplier", 1.0)
                        logger.info(f"[SCENARIO] Adjusted demand for {cmd['retailer_id']} ×{cmd['multiplier']}")
            elif ctype == "trigger_stockout":
                for wh in self.warehouses:
                    if wh.warehouse_id == cmd["warehouse_id"]:
                        wh.current_inventory_kg = 0.0
                        wh.inventory_batches = []
                        logger.info(f"[SCENARIO] Triggered stockout at {cmd['warehouse_id']}")
            cmd["applied"] = True
            modified = True
        if modified:
            with open(cmd_file, "w") as f:
                json.dump(data, f)
    except Exception as e:
        logger.warning(f"[SCENARIO] Failed to apply commands: {e}")
```

In `step()`, add after `self._process_events()`:
```python
self._apply_scenario_commands()
```

### Task 3.4 — New React component: ScenarioControlPanel
**File:** `FYP/dashboard_v2/src/components/panels/ScenarioControlPanel.jsx`

Simple panel with:
- "Inject Accident" button (uses a random active truck's current segment)
- "Double Demand" dropdown (select retailer)
- "Trigger Stockout" dropdown (select warehouse)
- Activity log of recent injections

### Task 3.5 — Add to dashboard
Add ScenarioControlPanel to the dashboard sidebar in `App.jsx`, below TruckList.

---

## Phase 4: Polish + Documentation
**Estimated time:** 2-3 hours

### Task 4.1 — Update SYSTEM_ANALYSIS.md
- Change N_ACTIONS=6 → N_ACTIONS=3 in the RL section
- Update "Fully Implemented" table with current state
- Add benchmark results table once available

### Task 4.2 — Add RL metrics to StatsCards
**File:** `FYP/dashboard_v2/src/components/dashboard/StatsCards.jsx`

Pass `rlReroutes` and `avgRslAtDelivery` as props from App.jsx (fetched from `/api/ai/rl-activity`). Add two new stat cards.

### Task 4.3 — RSL trend chart in Analytics tab
The analytics tab already has Chart.js. Add a line chart showing RSL at delivery over time. Data source: query InfluxDB `events` measurement for `delivery_complete` events with `avg_rsl_at_delivery` field.

### Task 4.4 — Update README
Update startup procedure and add section on RL training.

---

## Implementation Order (strict)

1. Task 1.2 (database.py cargo_rsl fix) — one line, do first
2. Task 1.1 (dispatch bug fix) — most critical
3. Task 1.4 (train) — start training, do other tasks while it runs
4. Task 1.3 (map popup enrichment) — quick win, 20 minutes
5. Task 2.1 (RL activity API endpoint)
6. Task 2.2 (AIInsightsPanel component)
7. Task 2.3 (add AI tab to App.jsx)
8. Task 1.5 (benchmark) — run after training completes
9. Task 3.1 (scenario command file protocol)
10. Task 3.2 (scenario API endpoints)
11. Task 3.3 (engine scenario polling)
12. Task 3.4 (ScenarioControlPanel)
13. Task 3.5 (add to dashboard)
14. Task 4.1-4.4 (polish)

---

## Files to Change Summary

| File | Change | Priority |
|------|--------|----------|
| `api/database.py` | Add `cargo_rsl` to truck_query keep() columns | P1 |
| `src/simulation/agents/truck_agent.py` | Add RL strategy to `assign_delivery()` | P1 |
| `src/simulation/engine.py` | Add `_apply_scenario_commands()` | P2 |
| `api/routers/ai_insights.py` | Add `/ai/rl-activity` endpoint | P2 |
| `api/routers/scenarios.py` | New file — scenario injection endpoints | P2 |
| `api/main.py` | Register scenarios router | P2 |
| `dashboard_v2/src/components/dashboard/MapView.jsx` | Enrich truck popups with RSL | P1 |
| `dashboard_v2/src/components/panels/AIInsightsPanel.jsx` | New component | P2 |
| `dashboard_v2/src/components/panels/ScenarioControlPanel.jsx` | New component | P2 |
| `dashboard_v2/src/App.jsx` | Add AI Insights tab + Scenario panel | P2 |
| `dashboard_v2/src/components/dashboard/StatsCards.jsx` | Add RL metrics cards | P3 |
| `docs/SYSTEM_ANALYSIS.md` | Update with current architecture | P3 |
| `README.md` | Update startup + training instructions | P3 |

## Files NOT to Change (Frozen)
- `traffic_model.py`, `road_segment.py`
- `router.py` (already has cost_weights param)
- OBS_DIM=25 observation vector
- All unit tests (they should still pass after changes)

---

## What This Achieves for the FYP

After this plan is complete:

1. **Mirror** — Live telemetry from 38 trucks with IoT sensor noise, shown on map with RSL color coding ✅
2. **Predict** — AI Insights panel shows RSL-at-delivery, ETA, demand forecasts per entity ✅
3. **Optimise** — PPO routing strategy trained and benchmarked, applied at BOTH dispatch AND rerouting ✅
4. **Learn** — ETAForecaster updates online, demand EMA updates, PPO epsilon decays ✅
5. **Intervene** — Scenario Control panel lets user inject accidents, adjust demand, trigger stockouts ✅

**FYP claim:**
> "The system mirrors the Nagpur orange supply chain in real-time, predicts cargo freshness and delivery times using physics-based and ML models, optimises routing decisions using a trained PPO policy that improves RSL at delivery by X% and reduces fuel consumption by Y%, and allows scenario injection for what-if analysis — demonstrating all four pillars of a digital twin."
