# Digital Twin System Analysis
## Supply Chain — Nagpur Orange Distribution

**Purpose**: Document what the digital twin implements and what remains out of scope.  
**Scope**: All agents, their behaviours, AI/ML integration, and inter-agent communication.  
**Last updated**: March 2026 — reflects current codebase state after Phase 1 + Phase 2 fixes.

---

## What Is a Digital Twin?

A digital twin is a living, bidirectional model of a real system that:
1. **Mirrors** the real system in real time (sensor data → model state)
2. **Predicts** future states (forecasting, what-if analysis)
3. **Optimises** decisions in the real system (recommendations, autonomous control)
4. **Learns** from the real system over time (online model updates)

What we have is a high-fidelity simulation with real AI layers. It is not a full digital twin because the bidirectional link to a physical system is simulated rather than real — which is expected for an FYP. The architecture is correct and all AI/ML components are genuine.

---

## Agent Inventory

### Agents That Exist

| Agent | Type | AI Used |
|-------|------|---------|
| TruckAgent | Autonomous mobile agent | PPO (RL routing), Arrhenius RSL physics, online ETA ridge regression |
| WarehouseAgent | Resource management agent | RSL quality control (pre-dispatch + at-delivery), (s,S) inventory policy |
| RetailerAgent | Demand-driven ordering agent | EMA demand forecasting, (s,S) inventory policy, stockout-history priority |
| AIManager | Coordination hub | Owns PredictionPod + OptimizationPod, cross-agent stockout sync |
| WeatherModel | Environment model | Real IMD data (parquet) + stochastic simulation fallback |
| DisruptionModel | Stochastic event generator | Probabilistic accident model, truck risk accumulation |
| TrafficModel | Environment model | Linked Traffic Model (LTM) — Gaussian wave engine, BFS ripple propagation |
| Driver | Sub-agent of TruckAgent | Fatigue accumulation, mandatory breaks, sleep enforcement |

### Agents Out of Scope (FYP)

| Agent | Role | Why Out of Scope |
|-------|------|-----------------|
| SupplierAgent | Upstream orange supplier | Restocking is a scheduled event. A real supplier would respond to market prices and seasonal availability. Out of scope for FYP timeline. |
| SupplyChainAnomalyDetector | Cascade stockout detection | System-level anomaly detection across all retailers simultaneously. Useful but not required for FYP. |

---

## Agent Behaviours: Ideal vs Implemented

### TruckAgent

**What it does:**
- ✅ Navigates using A* router with multi-objective cost function (distance + time + fuel + road quality)
- ✅ Reroutes on blocked segments (heuristic) and via RL policy (PPO, OBS_DIM=25)
- ✅ Proactively reroutes on `accident_alert` EventBus events before physically reaching the blockage
- ✅ Maintains cargo temperature with refrigeration model (Arrhenius, insulation factor)
- ✅ Manages fuel with realistic consumption model (load-dependent, speed-dependent, stop-and-go penalty)
- ✅ Respects driver fatigue, mandatory breaks (4.5h), sleep requirements (10h accumulated)
- ✅ Publishes telemetry (GPS, temperature, fuel, RSL, speed, zone, ripple) every timestep
- ✅ Feeds segment traversals into ETAForecaster for online ridge regression learning
- ✅ `cargo_rsl` included in `get_state()` snapshot → written to `truck_state` InfluxDB measurement
- ✅ IoT sensor layer: GPS noise, temperature noise, stock sensor noise with packet loss simulation

**Remaining gaps (low priority):**
- Truck does not proactively request priority routing when cargo RSL is critical
- No direct ETA communication channel back to warehouse

---

### WarehouseAgent

**What it does:**
- ✅ FIFO batch allocation (oldest batches dispatched first)
- ✅ Priority-based order allocation (higher urgency = dispatched first)
- ✅ Smallest-fit truck selection (minimises wasted capacity)
- ✅ Pre-dispatch RSL check — batches below threshold are disposed before loading
- ✅ RSLForecaster called during dispatch to warn if cargo will spoil in transit
- ✅ RSL quality check at delivery — rejects batches below threshold, triggers emergency reorder
- ✅ Dynamic restocking when perceived inventory drops below reorder point (AI-driven InventoryModel)
- ✅ Capacity enforcement — rejects oversized restocks
- ✅ Handles truck destruction, stale orders (24h timeout), partial deliveries
- ✅ Reacts to `accident_alert` EventBus events — flags `trucks_changed` for re-allocation
- ✅ IoT sensor layer: temperature sensor and stock sensor with noise/packet loss
- ✅ `inventory_management` config section wired to `InventoryModel` (service level, lead time, EOQ)

**Remaining gaps (low priority):**
- Truck selection does not prefer refrigerated trucks for high-RSL-urgency cargo
- No adaptive dispatch learning from historical delivery performance

---

### RetailerAgent

**What it does:**
- ✅ Poisson demand model with time-of-day, day-of-week, seasonal, weather, temperature multipliers
- ✅ (s,S) inventory policy with dynamic reorder point (AI-informed via ForecastingAgentAdapter)
- ✅ Multi-warehouse subscription with distance/load scoring
- ✅ Stockout history influences reorder quantity (safety multiplier) and priority (stockout boost)
- ✅ Emergency reorder on quality rejection or truck destruction
- ✅ Stale order timeout (24h) to prevent permanent blockage
- ✅ `notify_delivery_failed` feedback loop — clears pending order and escalates urgency

**Remaining gaps (low priority):**
- Warehouse selection does not consider historical delivery performance
- No explicit urgency escalation over time for orders already placed

---

### AIManager (Coordination Hub)

**What it does:**
- ✅ Owns PredictionPod (RSLForecaster + ETAForecaster)
- ✅ Owns OptimizationPod (PPO routing policy)
- ✅ Routes sale events → DemandForecaster EMA update
- ✅ Routes stockout events → cross-agent sync: boosts order priority for affected retailer in all warehouses
- ✅ Routes segment traversals → ETAForecaster online learning
- ✅ Routes cargo_spoiled → RSL alert (reduces PPO epsilon for more exploitation)
- ✅ Saves RL checkpoint on simulation shutdown
- ✅ Warehouses registered for cross-agent coordination

**Remaining gaps (low priority):**
- No system-level cascade stockout detection (multiple simultaneous stockouts)

---

### EventBus

**What it does:**
- ✅ Created and passed to all agents at startup
- ✅ Publishes `weather_change` events on every weather state transition
- ✅ Publishes `accident_alert` events when accidents are generated
- ✅ TruckAgent subscribes to `accident_alert` → proactively reroutes if affected segment is on planned route
- ✅ TruckAgent subscribes to `weather_change` → updates `current_weather` immediately
- ✅ WarehouseAgent subscribes to `accident_alert` → flags `trucks_changed` for re-allocation

---

## Communication Map

### What Actually Happens

```
Engine
  ├── calls retailer.update() → retailer emits [sale, stockout, order_placed]
  ├── calls warehouse.update() → warehouse emits [order_assigned, delivery_complete, ...]
  ├── calls truck_agent.update() → truck emits [telemetry, route_changed, ...]
  ├── feeds events to _feed_ai_manager()
  │     ├── sale → AIManager.record_sale() → DemandForecaster EMA update
  │     ├── stockout → AIManager.trigger_cross_agent_sync('stockout') → boosts retailer priority in all warehouses
  │     ├── cargo_spoiled → AIManager.trigger_cross_agent_sync('rsl_alert') → reduces PPO epsilon
  │     ├── truck_destroyed_cleanup → retailer.notify_delivery_failed() + emergency reorder
  │     └── delivery_complete → logged for analytics
  ├── publishes weather_change to EventBus
  │     └── TruckAgent._on_weather_change() → updates current_weather immediately
  └── publishes accident_alert to EventBus
        ├── TruckAgent._on_accident_alert() → forces reroute check on next update
        └── WarehouseAgent._on_accident_alert() → sets trucks_changed flag

Retailer → Engine.event_queue → Warehouse (via OrderPlacedEvent)
Warehouse → Retailer (via retailer.receive_delivery())
Truck → Warehouse (via truck.status == "arrived" → start_unloading → _handle_retailer_delivery)
```

---

## Implementation Status

### Fully Implemented ✅

| Capability | Notes |
|------------|-------|
| Realistic simulation (physics, demand, traffic, weather) | OSM road network, Arrhenius RSL, Greenshields LTM, IMD weather |
| RL routing policy (PPO) | OBS_DIM=25, N_ACTIONS=3 (balanced/speed/fuel strategies), trained via RoutingEnv. Applied at dispatch AND rerouting. |
| Online ETA forecasting | Ridge regression, falls back to physics until 50 samples |
| RSL prediction at delivery | Arrhenius physics, used in pre-dispatch check and dispatch warning |
| Online demand forecasting | EMA per retailer, wired into (s,S) reorder point calculation |
| Dashboard with AI predictions | RSL at delivery, ETA, demand forecast, weather forecast, RL reroute count |
| Pre-dispatch RSL check | Batches below threshold disposed before loading |
| EventBus agent subscriptions | Trucks and warehouses react to accidents and weather changes |
| Cross-agent stockout response | Warehouse boosts order priority for stocked-out retailers |
| Delivery failure feedback loop | Retailer clears pending order and escalates urgency on failure |
| Stockout history in reorder | Quantity and priority both scale with accumulated stockout duration |
| Warehouse inventory_management config | InventoryModel reads service level, lead time, EOQ from YAML |
| RoutingEnv season from start_date | Season (summer/monsoon/winter) derived from simulation.start_date |
| validators.py regex | run_id pattern correctly anchored with $ inside the string |

### Out of Scope (FYP)

| Capability | Reason |
|------------|--------|
| Bidirectional link to real physical system | Expected for FYP — simulation is the physical system |
| SupplierAgent | Requires market price modelling, out of FYP timeline |
| Full MARL joint training | Computationally infeasible on laptop |
| Refrigeration-aware truck selection | Low impact, not required for FYP |
| Cascade stockout anomaly detection | Nice-to-have, not required for FYP |

---

## Key Architecture Notes

### Observation Vector (OBS_DIM=25)
```
[0]   rsl_norm              RSL / 100
[1]   critical_flag         1 if RSL < 70%
[2]   fuel_norm             fuel% / 100
[3]   load_norm             load_kg / capacity_kg
[4]   dist_to_dest_norm     remaining_km / 100
[5-9] traffic_0..4          density / jam_density for 5 neighbors
[10-14] accident_0..4       is_blocked flag for 5 neighbors
[15]  accident_ahead        1 if blocked segment in next 5 planned
[16]  has_planned_route     1 if route exists
[17]  current_zone          OFFICE=0.1, SHOPPING=0.4, RESIDENTIAL=0.7, HIGHWAY=1.0
[18-21] ripple_0..3         backpressure / jam_density for 4 neighbors
[22]  time_norm             hour / 24
[23]  sin(hour)
[24]  cos(hour)
```

### Status Codes (InfluxDB truck_state)
```python
{'idle': 0.0, 'loading': 1.0, 'in_transit': 2.0, 'unloading': 3.0,
 'unloading_complete': 4.0, 'arrived': 5.0, 'refueling': 6.0, 'destroyed': 7.0}
```

### Simulation Loop (per tick)
1. `_process_events()` — execute scheduled events (orders, restocks)
2. `_update_agents()` — retailers → warehouses → trucks (in that order)
3. `_update_environment()` — weather transitions, traffic model update
4. `_check_stochastic_events()` — probabilistic accident generation + EventBus publish
5. `_handle_logging()` — InfluxDB snapshots including `weather_state` (or CSV in headless mode)
6. `_check_and_write_heartbeat()` — liveness signal for dashboard simulation detection
7. `current_time += time_step`

### Perceived vs Actual Inventory
`_perceived_inventory_kg` is for reorder trigger decisions (uses IoT sensor noise).  
`current_inventory_kg` is ground truth used for actual batch allocation.  
Both are updated on restock and spoilage events.
