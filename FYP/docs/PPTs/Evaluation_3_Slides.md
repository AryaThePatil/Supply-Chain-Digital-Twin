# Evaluation 3 Presentation Slides
**Project:** Digital Twin for Perishable Food Supply Chain
**Institute:** VNIT Nagpur (Dept of CSE)
**Guide:** Prof. R. B. Keskar
**Team:** Ayaan Khan, Arya Patil, Nihaal Badam, Swastik Ankulge
**Date:** December 5, 2025

---

## Slide 1: Title Slide
**Title:** Digital Twin for Perishable Food Supply Chain
**Subtitle:** Evaluation 3: System Verification, Realistic Modeling, and Static DT Completion
**Presented By:** [Your Name]
**Team Members:** Ayaan Khan, Arya Patil, Nihaal Badam, Swastik Ankulge
**Guide:** Prof. R. B. Keskar

---

## Slide 2: Project Recap (Week 1 & 2 Context)
*Where we started and the "Big Picture" vision.*

**Project Goal:**
To build a **production-ready Digital Twin** for orange supply chain logistics in Nagpur. This system models the flow of perishable goods from warehouses to retailers, incorporating realistic traffic, weather, and demand variability.

**The "Zero Shortcuts" Philosophy:**
We committed to a research-backed approach:
*   **Real Maps:** OpenStreetMap (OSM) integration for Nagpur.
*   **Real Physics:** Arrhenius spoilage models (Ahmad et al., 2019) and Greenshields traffic models (1935).
*   **Real Behavior:** Probabilistic disruptions (WHO-backed accident rates) and Poisson demand processes.

**Previous Work (Week 1 & 2):**
*   **Foundation (Phase 1):** Established the Hybrid Simulation Engine (Time-stepped + Event-driven) and the 3-tier MQTT logging system (Events, Snapshots, Telemetry).
*   **Network (Phase 2):** Integrated the real-world road network of Nagpur using `osmnx`, moving beyond abstract graphs to a physically accurate topology with speed limits and turn restrictions.

---

## Slide 3: Phase 1 - The Foundation (Hybrid Engine)
*Building the "Brain" of the simulation.*

**Core Architecture:**
*   **Hybrid Simulation Engine:** Combines 1-minute time steps for continuous processes (traffic, weather) with an event queue for discrete logistics (orders, accidents).
*   **Data Pipeline:** A robust IoT simulation pipeline:
    *   **MQTT Broker:** For real-time message passing.
    *   **Telegraf & InfluxDB:** For time-series data storage and analysis.

**Key Models:**
*   **Arrhenius Spoilage:** Modeled specifically for Valencia oranges ($k = 1.4 \times 10^9 \times e^{-7456/T}$).
*   **Logging:** Captures every truck movement and temperature change for post-simulation analysis.

---

## Slide 4: Phase 2 - The Environment (Real-World Network)
*Moving from abstract graphs to the real world.*

**OpenStreetMap (OSM) Integration:**
*   **Data Source:** Full road network of Nagpur (Western Zone).
*   **Fidelity:** Includes road types (motorway vs. residential), one-way constraints, and surface quality.

**Traffic Physics:**
*   **Greenshields Model:** $v = v_{free} \times (1 - \rho/\rho_{jam})$. Traffic speed drops realistically as density increases.
*   **A* Routing:** Routes are calculated based on a multi-objective cost function:
    *   $Cost = w_1 \times Time + w_2 \times Fuel + w_3 \times Distance$
    *   This ensures trucks don't just take the shortest path, but the *fastest* and most *efficient* one.

---

## Slide 5: Phase 3 - The Agents (Intelligent Decision Making)
*The actors in our supply chain.*

**1. Warehouse Agents (2 Configured):**
*   **Inventory Policy:** $(s, S)$ Continuous Review.
    *   $s$ (Reorder Point): Based on lead time demand + safety stock (95% service level).
    *   $S$ (Order-up-to): Based on EOQ (Economic Order Quantity).
*   **Fleet Management:** Manages a heterogeneous fleet of 38 trucks (Small, Medium, Large) with priority allocation.

**2. Retailer Agents (12 Configured):**
*   **Demand Modeling:** Non-homogeneous Poisson Process. Demand varies by hour (rush peaks), day of week, and season.

**3. Truck Agents:**
*   **State Machine:** `IDLE` -> `LOADING` -> `TRANSIT` -> `UNLOADING` -> `REFUELING`.
*   **Fuel Logic:** Consumption depends on **Load** (40% higher when full) and **Speed** (efficiency curves).

---

## Slide 6: Phase 4 - Realism & Dynamics (The "Twin" Aspect)
*Making the simulation behave like the real world.*

**1. Dynamic Weather:**
*   **5 States:** Clear, Light Rain, Rain, Heavy Rain, Fog.
*   **Impact:** Rain reduces road capacity and increases accident probability. Fog drastically reduces speed limits.

**2. Disruption Modeling:**
*   **Accidents:** Probabilistic generation based on WHO statistics.
*   **Response:** Trucks automatically recalculate routes when they encounter a blocked segment.

**3. Driver Behavior:**
*   **Fatigue:** Drivers accumulate fatigue and must take mandatory 30-minute breaks after 5 hours.
*   **Skill:** Driver skill levels affect fuel efficiency and accident risk.

---

## Slide 7: Phase 5 - Verification & Validation
*Proving it works.*

**Unit Testing:**
*   **Suite:** 113 Unit Tests covering all modules (Engine, Network, Agents, Models).
*   **Coverage:** Verified critical logic like the Arrhenius equation and Inventory policy calculations.

**System Verification:**
*   **End-to-End Runs:** Successfully executed multi-day simulations on the full Nagpur map.
*   **Telemetry Analysis:** Confirmed that trucks follow traffic rules, fuel decreases correctly, and cargo spoils faster in heat.

---

## Slide 8: Challenges & Solutions (The "Big Data" Reality)
*Engineering hurdles we overcame.*

**The Problem: Massive Map Data**
*   **Issue:** The high-fidelity OSM map for the region is a **5GB+ XML file**.
*   **Impact:** Loading this into memory caused timeouts and crashes with standard tools. API downloads failed due to server limits.

**The Solution:**
*   **Local Caching & Optimization:** We implemented a robust local file loader that bypasses the API.
*   **Lazy Loading Strategy:** (Planned) We are optimizing the loader to parse only necessary chunks or use a spatial database (PostGIS) for future scalability.
*   **Current Status:** The simulation *can* run on the full map, but initialization takes time (proof of complexity!).

---

## Slide 9: Future Roadmap (Dynamic Digital Twin)
*Moving from "Simulation" to "Optimization".*

**Goal:** Transition from a **Static Model** (fixed rules) to a **Dynamic, Learning System**.

**1. AI & Reinforcement Learning (RL):**
*   **Ready:** The platform is stable and ready for the next phase of AI integration.

---
