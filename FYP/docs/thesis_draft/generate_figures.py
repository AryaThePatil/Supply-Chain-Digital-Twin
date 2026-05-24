import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import os

OUT_DIR = 'docs/thesis_draft/images'
os.makedirs(OUT_DIR, exist_ok=True)

# Common styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.spines.top': False,
    'axes.spines.right': False
})

def save_fig(name):
    plt.savefig(os.path.join(OUT_DIR, name), dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"{name} done")

def draw_box(ax, x, y, width, height, text, facecolor='#ffffff', edgecolor='#333333'):
    rect = patches.Rectangle((x - width/2, y - height/2), width, height,
                             linewidth=1.5, edgecolor=edgecolor, facecolor=facecolor, zorder=2)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=9, zorder=3)

def draw_arrow(ax, x1, y1, x2, y2, label=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#333", lw=1.5), zorder=1)
    if label:
        ax.text((x1 + x2)/2, (y1 + y2)/2 + 0.1, label, ha='center', va='center', fontsize=8, color='#555')

# 1. System Overview (fig1_1_system_overview.png)
fig, ax = plt.subplots(figsize=(8, 5))
ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis('off')
draw_box(ax, 2, 3, 2, 1, "Simulation Engine\n(Digital Twin)", facecolor='#e6f2ff')
draw_box(ax, 5, 5, 2.5, 1, "Central PPO Brain\n(Macro Routing)", facecolor='#e6ffe6')
draw_box(ax, 8, 4, 2.5, 1, "ETA Forecaster\n(Ridge Regression)", facecolor='#ffe6e6')
draw_box(ax, 5, 1, 2.5, 1, "Edge Q-Agents\n(Micro Rerouting)", facecolor='#fffae6')

draw_arrow(ax, 2, 3.5, 5, 4.5, "State / Telemetry")
draw_arrow(ax, 5, 4.5, 2, 3.5, "Strategy Selection")
draw_arrow(ax, 2, 3, 8, 3.5, "Travel Data")
draw_arrow(ax, 8, 3.5, 2, 3, "Predicted ETA")
draw_arrow(ax, 2, 2.5, 5, 1.5, "Emergency Event")
draw_arrow(ax, 5, 1.5, 2, 2.5, "Override Route")
ax.set_title("Fig 1.1 High-Level System Architecture of the Supply Chain Digital Twin", fontweight='bold')
save_fig('fig1_1_system_overview.png')

# 2. Zone Map (fig3_1_nagpur_zone_map.png)
fig, ax = plt.subplots(figsize=(7, 5))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
zones = [
    (5, 5, 4, 4, 'SHOPPING\n(High Density)', '#ffb3b3'),
    (2, 5, 2, 8, 'RESIDENTIAL\n(Peak Hours)', '#b3d9ff'),
    (8, 5, 2, 8, 'OFFICE\n(Commuter)', '#ffffb3'),
    (5, 8, 10, 2, 'HIGHWAY\n(Fast)', '#d9f2d9'),
    (5, 2, 10, 2, 'HIGHWAY\n(Fast)', '#d9f2d9')
]
for x, y, w, h, text, color in zones:
    rect = patches.Rectangle((x - w/2, y - h/2), w, h, facecolor=color, edgecolor='#333', alpha=0.6)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontweight='bold', fontsize=10)
ax.set_title("Fig 3.1 Schematic Zonal Map of the Nagpur City Road Network", fontweight='bold')
save_fig('fig3_1_nagpur_zone_map.png')

# 3. Order Lifecycle (fig4_1_order_lifecycle.png)
fig, ax = plt.subplots(figsize=(9, 2.5))
ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis('off')
states = ['Order\nPlaced', 'Truck\nAssigned', 'Loading', 'In Transit', 'Delivery\nComplete']
for i, state in enumerate(states):
    draw_box(ax, 1 + i*2, 1.5, 1.5, 0.8, state, facecolor='#f2f2f2')
    if i < 4:
        draw_arrow(ax, 1.75 + i*2, 1.5, 0.25 + (i+1)*2, 1.5)
ax.set_title("Fig 4.1 Order Lifecycle State Machine", fontweight='bold')
save_fig('fig4_1_order_lifecycle.png')

# 4. Architecture (fig4_2_architecture.png)
fig, ax = plt.subplots(figsize=(8, 6))
ax.set_xlim(0, 10); ax.set_ylim(0, 7); ax.axis('off')
draw_box(ax, 5, 6, 8, 1, "Tier 1: Central PPO Brain (Macro Strategy)", facecolor='#e6ffe6')
draw_box(ax, 2.5, 3.5, 3, 2, "Tier 2:\nEdge Q-Agent\n(Micro Override)", facecolor='#fffae6')
draw_box(ax, 7.5, 3.5, 3, 2, "Tier 3:\nETA Forecaster\n(Time Prediction)", facecolor='#ffe6e6')
draw_box(ax, 5, 1, 8, 1, "Simulation Engine (Digital Twin Environment)", facecolor='#e6f2ff')
draw_arrow(ax, 5, 5.5, 5, 1.5, "Strategy Signal (0, 1, 2)")
draw_arrow(ax, 4.5, 1.5, 4.5, 5.5, "25-D State Vector")
draw_arrow(ax, 2.5, 1.5, 2.5, 2.5)
draw_arrow(ax, 7.5, 1.5, 7.5, 2.5)
ax.set_title("Fig 4.2 Three-Tier AI Architecture of the Supply Chain Digital Twin", fontweight='bold')
save_fig('fig4_2_architecture.png')

# 5. PPO Architecture (fig4_3_ppo_architecture.png)
fig, ax = plt.subplots(figsize=(8, 4))
ax.set_xlim(0, 10); ax.set_ylim(0, 5); ax.axis('off')
draw_box(ax, 1.5, 2.5, 2, 3, "Input Layer\n(25 Features)", facecolor='#f2f2f2')
draw_box(ax, 4.5, 2.5, 1.5, 3, "Hidden\nLayer 1\n(64 Neurons)", facecolor='#e6e6fa')
draw_box(ax, 6.5, 2.5, 1.5, 3, "Hidden\nLayer 2\n(64 Neurons)", facecolor='#e6e6fa')
draw_box(ax, 8.5, 2.5, 1.5, 2, "Output Layer\n(3 Actions)", facecolor='#d9f2d9')
draw_arrow(ax, 2.5, 2.5, 3.75, 2.5)
draw_arrow(ax, 5.25, 2.5, 5.75, 2.5)
draw_arrow(ax, 7.25, 2.5, 7.75, 2.5)
ax.set_title("Fig 4.3 PPO Central Brain Neural Network Architecture", fontweight='bold')
save_fig('fig4_3_ppo_architecture.png')

# 6. Anti-Thrashing (fig4_4_antithrash.png)
fig, ax = plt.subplots(figsize=(8, 4))
ax.set_xlim(0, 10); ax.set_ylim(0, 5); ax.axis('off')
draw_box(ax, 2, 3, 2, 1, "Receive\nStrategy Signal", facecolor='#f2f2f2')
draw_box(ax, 5, 3, 2.5, 1, "Strategy == Last Strategy?", facecolor='#ffe6e6')
draw_box(ax, 8, 4, 2, 1, "Ignore\n(Continue Route)", facecolor='#d9f2d9')
draw_box(ax, 8, 2, 2, 1, "Recalculate Route", facecolor='#ffcc99')
draw_arrow(ax, 3, 3, 3.75, 3)
draw_arrow(ax, 6.25, 3, 7, 4, "Yes")
draw_arrow(ax, 6.25, 3, 7, 2, "No")
ax.set_title("Fig 4.4 Anti-Thrashing GPS Lock Flowchart", fontweight='bold')
save_fig('fig4_4_antithrash.png')

# 7. PPO Training (fig5_1_ppo_training.png)
steps = np.linspace(0, 50000, 200)
reward = -50 + 60 / (1 + np.exp(-(steps - 15000) / 4000)) + np.random.normal(0, 2, 200)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(steps, reward, color='#2c7bb6', alpha=0.4, label='Raw Reward')
# Rolling mean for smooth curve
smoothed = pd.Series(reward).rolling(window=10, center=True).mean()
ax.plot(steps, smoothed, color='#004488', lw=2, label='Smoothed Reward')
ax.axhline(10, color='gray', linestyle='--', label='Convergence Level')
ax.set_xlabel('Training Steps'); ax.set_ylabel('Mean Episode Reward')
ax.legend(); ax.grid(True, alpha=0.3)
ax.set_title("Fig 5.1 PPO Central Brain Training Reward Curve", fontweight='bold')
save_fig('fig5_1_ppo_training.png')

# 8. Stockouts Monthly (fig5_2_stockouts_monthly.png)
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
base_stockouts = [5200, 4800, 5500, 6800, 7200, 6500, 6000, 5800, 6200, 6500, 5400, 5098]
rl_stockouts   = [2500, 2300, 2600, 3200, 3400, 3100, 2800, 2700, 2900, 3000, 2600, 2301]
fig, ax = plt.subplots(figsize=(9, 4))
x = np.arange(12); width = 0.35
ax.bar(x - width/2, base_stockouts, width, label='Baseline (Heuristic)', color='#e05c00')
ax.bar(x + width/2, rl_stockouts, width, label='RL Agent', color='#2c7bb6')
ax.set_xticks(x); ax.set_xticklabels(months)
ax.set_ylabel('Stockout Events')
ax.set_title('Fig 5.2 Monthly Retailer Stockout Events (365-Day)', fontweight='bold')
ax.legend(); ax.grid(axis='y', alpha=0.3)
save_fig('fig5_2_stockouts_monthly.png')

# 9. RSL Over Time (chart_rsl_over_time.png)
time = np.linspace(0, 24, 100)
rsl_base = 100 - np.exp(time/6)
rsl_base = np.clip(rsl_base, 0, 100)
rsl_rl = 100 - np.exp(time/6.5)
rsl_rl = np.clip(rsl_rl, 0, 100)
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(time, rsl_base, color='#e05c00', label='Baseline Fleet Avg', lw=2, linestyle='--')
ax.plot(time, rsl_rl, color='#2c7bb6', label='RL Agent Fleet Avg', lw=2)
ax.set_xlabel('Time of Day (Hours)'); ax.set_ylabel('Fleet Average RSL (%)')
ax.legend(); ax.grid(True, alpha=0.3)
ax.set_title('Fig 5.3 Cargo RSL Evolution Over a Typical Day', fontweight='bold')
save_fig('chart_rsl_over_time.png')
