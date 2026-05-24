# Exact Copy-Paste Presentation Blueprint (28 Slides)

This blueprint is formatted exactly how your slides should look. You can literally copy the title and the bullet points, paste them into a blank PowerPoint slide, and drag the corresponding image in. It contains exactly 8 references on the final slide.

## User Review Required
> [!IMPORTANT]
> Please review this final copy-paste version. If this structure looks good, your planning phase is officially complete and you can start building the PPT!

---

### Phase 1: Introduction & Problem Context

**Slide 1: Title Slide**
*   **Title:** Supply Chain Digital Twin using Reinforcement Learning
*   **Visual:** `vnit_logo.png`
*   **Text:** 
    - Group Members: Ayaan Khan, Arya Patil, Nihaal Badam, Swastik Ankulge
    - Guide: Dr. Ravindra B. Keskar
    - Visvesvaraya National Institute of Technology, Nagpur

**Slide 2: The Challenge of Urban Logistics**
*   **Title:** The Challenge of Urban Logistics
*   **Visual:** (None)
*   **Text:**
    - Urban supply chains operate in highly stochastic environments.
    - Factors like weather, rush hours, and road accidents constantly change travel times.
    - Traditional static routing models (e.g., standard A*) fail to adapt to these real-time changes.

**Slide 3: The Freshness vs. Fuel Dilemma**
*   **Title:** The Freshness vs. Fuel Dilemma
*   **Visual:** (None)
*   **Text:**
    - Fast deliveries preserve the Remaining Shelf Life (RSL) of perishable cargo.
    - However, fast routes often require using congested highways, which drastically increases fuel consumption.
    - Standard algorithms struggle to balance these conflicting multi-objective goals.

**Slide 4: Project Objectives**
*   **Title:** Project Objectives
*   **Visual:** `fig1_1_system_overview.png`
*   **Text:**
    - Develop a discrete-event Simulation Engine (Digital Twin) of Nagpur city.
    - Implement a Macro-Routing Agent using Proximal Policy Optimization (PPO).
    - Implement Micro-Rerouting Edge Agents using Q-Learning.
    - Predict real-time traffic using an online Ridge Regression model.

---

### Phase 2: The Digital Twin Environment

**Slide 5: Simulation Engine Overview**
*   **Title:** Simulation Engine Overview
*   **Visual:** (None)
*   **Text:**
    - A custom discrete-event engine stepping in 15-minute simulated intervals.
    - Deterministic random seeding ensures fair benchmarking between algorithms.
    - Continuously injects dynamic environmental events (rain, heat, accidents).

**Slide 6: The Nagpur City Graph**
*   **Title:** The Nagpur City Graph
*   **Visual:** `fig3_1_nagpur_zone_map.png`
*   **Text:**
    - Road network modeled mathematically using the NetworkX library.
    - Segmented into 4 unique geographic zones: HIGHWAY, RESIDENTIAL, OFFICE, SHOPPING.
    - Each zone features distinct hourly and weekly traffic cyclicity.

**Slide 7: Actor 1 - Retailers**
*   **Title:** Actor 1: Retailer Nodes
*   **Visual:** (None)
*   **Text:**
    - Generate stochastic consumer demand based on geographic zone.
    - Automatically trigger an `order_placed` event when local inventory drops below threshold.
    - Log a permanent `stockout` penalty if inventory hits zero before replenishment.

**Slide 8: Actor 2 - The Warehouse**
*   **Title:** Actor 2: The Warehouse Depot
*   **Visual:** (None)
*   **Text:**
    - Acts as the central supply hub for the entire city graph.
    - Maintains the global queue of pending retailer orders.
    - Responsible for executing the fleet allocation algorithm to dispatch idle trucks.

**Slide 9: Actor 3 - Truck Fleet & State Machine**
*   **Title:** Actor 3: Truck Fleet & State Machine
*   **Visual:** `fig4_1_order_lifecycle.png`
*   **Text:**
    - Fleet of 10 autonomous delivery vehicles.
    - Follows a strict lifecycle: Idle $\to$ Loading $\to$ In-Transit $\to$ Delivering $\to$ Returning.
    - Physically tracks fuel consumption over distance and RSL decay over time.

---

### Phase 3: The Three-Tier AI Architecture

**Slide 10: AI Architecture Overview**
*   **Title:** Three-Tier AI Architecture
*   **Visual:** `fig4_2_architecture.png`
*   **Text:**
    - Replaced the baseline A* heuristic with a 3-tier intelligence stack.
    - **Tier 1:** Central PPO Brain for macro-strategy.
    - **Tier 2:** Edge Q-Agents for micro-tactics.
    - **Tier 3:** ETA Forecaster for predictive intelligence.

**Slide 11: Tier 1 - Central PPO Brain**
*   **Title:** Tier 1: Central PPO Brain
*   **Visual:** `screenshot_ppo_env.png`
*   **Text:**
    - Implemented using the Stable-Baselines3 library.
    - Multi-agent environment flattened into a single-agent Gymnasium wrapper via parameter sharing.
    - Neural Network Policy: 25-node input $\to$ two 64-node hidden layers $\to$ 3-node output.

**Slide 12: PPO State and Action Space**
*   **Title:** PPO State and Action Space
*   **Visual:** `fig4_3_ppo_architecture.png`
*   **Text:**
    - **25-Dimension State:** Observes truck fuel, cargo RSL, weather severity, and fleet averages.
    - **3-Discrete Actions:** Speed-Priority, Fuel-Priority, Balanced.
    - Operates sequentially at every dispatch decision point.

**Slide 13: The Reward Normalization Framework**
*   **Title:** The Reward Normalization Framework
*   **Visual:** (None)
*   **Text:**
    - $Reward = W_{del} - (W_{fuel} \times \Delta Fuel) - (W_{RSL} \times \Delta RSL)$
    - Fuel physically drops ~15\% per trip, while RSL drops only ~2\%.
    - We established a strict **5:1 penalty ratio** ($W_{RSL}=50.0$, $W_{fuel}=10.0$).
    - This forces the PPO agent to treat cargo freshness and fuel as equally critical.

**Slide 14: Tier 2 - Edge Q-Learning Agents**
*   **Title:** Tier 2: Edge Q-Learning Agents
*   **Visual:** (None)
*   **Text:**
    - Embedded individually on all 10 trucks.
    - Triggered strictly by stochastic road accidents blocking the active route.
    - Utilizes a 9-state tabular Q-learning matrix with Epsilon-Greedy exploration.
    - Overrides the Central Brain to execute immediate evasive maneuvers.

**Slide 15: Tier 3 - ETA Forecaster Design**
*   **Title:** Tier 3: ETA Forecaster Design
*   **Visual:** `screenshot_eta_forecaster_1.png`
*   **Text:**
    - Implemented via Scikit-learn's `SGDRegressor` (Ridge Regression).
    - Replaces static average-based heuristics with dynamic edge-cost predictions.
    - Trains *online* using `partial_fit()` as trucks successfully traverse the city.

**Slide 16: ETA Feature Engineering**
*   **Title:** ETA Feature Engineering
*   **Visual:** `screenshot_eta_forecaster_2.png`
*   **Text:**
    - Utilizes a highly optimized 8-Dimensional feature vector.
    - Encodes time-of-day and day-of-week using Sine/Cosine transformations.
    - *Why?* Prevents the mathematical discontinuity of Sunday (Day 7) appearing far from Monday (Day 1).

---

### Phase 4: Development Challenges & Training

**Slide 17: Telemetry & Data Logging**
*   **Title:** Telemetry & Data Logging
*   **Visual:** (None)
*   **Text:**
    - Simulation writes to permanent CSV artifacts (`events_sim.csv` and `telemetry_sim.csv`).
    - Captured over 2.4 million truck states across the 365-day benchmark.
    - Telemetry files serve as the ground truth for all performance comparisons.

**Slide 18: PPO Training Pipeline**
*   **Title:** PPO Training Pipeline
*   **Visual:** `screenshot_ppo_training_1.png`
*   **Text:**
    - Agent trained offline for 50,000 timesteps.
    - Hyperparameters: Learning Rate 3e-4, Batch Size 64.
    - Set Entropy Coefficient to 0.01 to force exploration of RSL-Priority paths.

**Slide 19: Preventing Overfitting**
*   **Title:** Preventing Overfitting
*   **Visual:** `screenshot_ppo_training_2.png`
*   **Text:**
    - PPO models are highly susceptible to overfitting to training seeds.
    - Integrated an `EvalCallback` to evaluate the model on a held-out environment every 5,000 steps.
    - Saved and deployed the absolute best policy (`best_model.zip`), not just the final step.

**Slide 20: The Route-Thrashing Challenge**
*   **Title:** Engineering Challenge: Route Thrashing
*   **Visual:** `fig4_4_antithrash.png`
*   **Text:**
    - **The Bug:** Trucks recalculated routes every 15 minutes upon receiving a PPO signal, paralyzing the fleet (49% delivery rate).
    - **The Solution:** Implemented an Anti-Thrashing GPS Lock state machine.
    - Trucks now ignore redundant signals, immediately restoring service levels to 99.9%.

---

### Phase 5: Experimental Benchmark & Results

**Slide 21: Benchmark Setup**
*   **Title:** 365-Day Comparative Benchmark
*   **Visual:** (None)
*   **Text:**
    - Goal: Prove RL outperforms static algorithms in long-term scenarios.
    - Run 1: 365-Day Baseline Simulation (Standard A* Heuristics).
    - Run 2: 365-Day RL-Enabled Simulation (PPO + Edge Q-Agent + Forecaster).
    - Both runs experienced identical weather, accidents, and retailer demand.

**Slide 22: PPO Training Convergence**
*   **Title:** PPO Training Convergence
*   **Visual:** `fig5_1_ppo_training.png`
*   **Text:**
    - The learning curve displays the mean episode reward over 50,000 steps.
    - Reward starts highly negative (random exploration) and climbs steeply.
    - The model successfully converged and plateaued around step 35,000.

**Slide 23: Result 1 - Service Level & Throughput**
*   **Title:** Result: Service Level & Throughput
*   **Visual:** `fig5_2_stockouts_monthly.png`
*   **Text:**
    - **Baseline Router:** 70,898 retailer stockout events.
    - **RL Architecture:** 33,401 retailer stockout events.
    - Achieved a massive **52.9% reduction in stockouts**.
    - Successfully delivered an additional +474,708 kg of cargo.

**Slide 24: Result 2 - RSL & Fuel Parity**
*   **Title:** Result: RSL & Fuel Parity
*   **Visual:** `chart_rsl_over_time.png`
*   **Text:**
    - Proved the 5:1 reward math worked flawlessly.
    - Average fleet fuel remained perfectly identical to the baseline (78.7%).
    - Average cargo freshness at delivery remained identical (99.7%).
    - The AI increased throughput *without* sacrificing efficiency or quality.

**Slide 25: Result 3 - Emergent Safety Behavior**
*   **Title:** Result: Emergent Safety Behavior
*   **Visual:** (None)
*   **Text:**
    - The RL Architecture recorded 135 fewer road accidents over the year.
    - This was an unprogrammed, emergent behavior.
    - The ETA Forecaster implicitly learned which zones had high accident probabilities during specific hours, naturally routing trucks away from danger.

**Slide 26: Achieving Pareto Optimality**
*   **Title:** Achieving Pareto Optimality
*   **Visual:** (None)
*   **Text:**
    - A system achieves Pareto improvement if it betters one objective without worsening another.
    - Our RL system strictly improved 6 metrics (throughput, service level, stockouts, accidents) while holding Fuel and RSL constant.
    - Conclusion: The multi-agent RL framework is strictly superior to static heuristics.

---

### Phase 6: Conclusion & References

**Slide 27: Future Scope**
*   **Title:** Future Scope
*   **Visual:** (None)
*   **Text:**
    - Scale the environment to multi-depot and multi-city configurations.
    - Integrate real-time physical IoT sensors (GPS, refrigerated container thermometers) into the Digital Twin.
    - Deploy the trained Central PPO Brain to embedded physical edge devices.

**Slide 28: References**
*   **Title:** References
*   **Visual:** (None)
*   **Text:**
    1. Schulman, J. et al., "Proximal Policy Optimization Algorithms," 2017.
    2. Mnih, V. et al., "Human-level control through deep reinforcement learning," *Nature*, 2015.
    3. Sutton, R. S. and Barto, A. G., *Reinforcement Learning: An Introduction*, 2nd ed., MIT Press, 2018.
    4. Raffin, A. et al., "Stable-Baselines3: Reliable Reinforcement Learning Implementations," *JMLR*, 2021.
    5. Hart, P. E. et al., "A Formal Basis for the Heuristic Determination of Minimum Cost Paths," *IEEE Transactions*, 1968.
    6. Hoerl, A. E. and Kennard, R. W., "Ridge Regression: Biased Estimation for Nonorthogonal Problems," *Technometrics*, 1970.
    7. Giannoccaro, I. and Pontrandolfo, P., "Inventory management in supply chains: A reinforcement learning approach," *Int. J. of Production Economics*, 2002.
    8. Towers, M. et al., "Gymnasium: A Standard Interface for Reinforcement Learning Environments," 2023.
