import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(16, 9))
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis('off')

# Colors
color_env = '#e0f2f1'  
color_eng = '#e3f2fd'  
color_ai = '#fff3e0'   
color_stack = '#f3e5f5' 
border_color = '#263238'
sub_color = '#ffffff'

def draw_box(x, y, w, h, text, color, title=None, fontsize=10):
    box = patches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.1,rounding_size=0.15', 
                                 linewidth=1.5, edgecolor=border_color, facecolor=color)
    ax.add_patch(box)
    if title:
        ax.text(x + w/2, y + h - 0.35, title, ha='center', va='center', fontsize=12, fontweight='bold', color=border_color)
        ax.text(x + w/2, y + h/2 - 0.2, text, ha='center', va='center', fontsize=fontsize, wrap=True, color=border_color)
    else:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize, wrap=True, color=border_color)

# 1. Environmental Layers
draw_box(0.5, 1, 4.5, 7, '', color_env, 'Environmental Data Layers')

draw_box(1.0, 6.0, 3.5, 1.2, 'Ground Truth Physics Engine\nThermodynamics (RSL Decay)\nKinematics ($\Delta$ Fuel Consumption)', sub_color, fontsize=10)
draw_box(1.0, 4.2, 3.5, 1.2, 'City Topography Modeler\nNetworkX Graph Matrix\n(4 Dynamic Traffic Zones)', sub_color, fontsize=10)
draw_box(1.0, 2.4, 3.5, 1.2, 'Simulated IoT Sensors\nReal-time GPS (Lat/Lon)\nRefrigerated Container Temp ($^\circ$C)', sub_color, fontsize=10)

# 2. Simulation Engine
draw_box(5.5, 1, 5.0, 7, '', color_eng, 'Digital Twin Simulation Engine')
ax.text(8.0, 7.3, '(Python 3.10 Discrete-Event Core)', ha='center', va='center', fontsize=10, fontstyle='italic')

draw_box(6.0, 5.7, 4.0, 1.3, 'Tier 1: Central PPO Brain\nStable-Baselines3 MLP Policy\n(25 $\\rightarrow$ 64 $\\rightarrow$ 64 $\\rightarrow$ 3)\nReward Function Normalization (5:1)', color_ai, fontsize=10)
draw_box(6.0, 3.9, 4.0, 1.3, 'Tier 2: Edge Q-Learning Agents\nPer-Truck Autonomous Micro-Routing\nTabular 9-State Epsilon-Greedy', color_ai, fontsize=10)
draw_box(6.0, 2.1, 4.0, 1.3, 'Tier 3: Online ETA Forecaster\nScikit-Learn SGDRegressor (Ridge)\n8-Dim Vector (Sine/Cosine Encoding)', color_ai, fontsize=10)

# 3. Full-Stack Layer
draw_box(11.0, 1, 4.5, 7, '', color_stack, 'Full-Stack Information Flow')

draw_box(11.5, 5.7, 3.5, 1.3, 'InfluxDB (Time-Series DB)\nBucket: "supply-chain"\nContinuous Snapshot Retention', sub_color, fontsize=10)
draw_box(11.5, 3.9, 3.5, 1.3, 'FastAPI (REST Backend)\nUvicorn ASGI Server\nHigh-Concurrency JSON Endpoints', sub_color, fontsize=10)
draw_box(11.5, 2.1, 3.5, 1.3, 'Vite / React (Frontend)\nLive Interactive Map\nDynamic KPI Analytics Cards', sub_color, fontsize=10)

# Arrows and Annotations
def draw_arrow(x1, y1, x2, y2, text=None):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle='-|>', lw=2, color=border_color))
    if text:
        ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, text, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1565c0')

# Env -> Engine
draw_arrow(5.0, 4.5, 5.5, 4.5, 'State Vector ($S_t$)')

# Engine -> InfluxDB
draw_arrow(10.5, 6.35, 11.5, 6.35, 'Telemetry\nWrites')

# DB -> API
draw_arrow(13.25, 5.7, 13.25, 5.2, 'Flux Queries')

# API -> React
draw_arrow(13.25, 3.9, 13.25, 3.4, 'Axios HTTP GET')

# Inter-Engine Arrows
ax.annotate('', xy=(8.0, 5.7), xytext=(8.0, 5.2), arrowprops=dict(arrowstyle='<->', lw=1.5, color='#ff9800', ls='--'))
ax.annotate('', xy=(8.0, 3.9), xytext=(8.0, 3.4), arrowprops=dict(arrowstyle='<->', lw=1.5, color='#ff9800', ls='--'))

# Main Title
plt.title('Cognitive Digital Twin: Highly Technical Architecture Blueprint', fontsize=20, fontweight='bold', pad=20, color='#111111')

plt.tight_layout()
plt.savefig('docs/PPTs/full_system_architecture_detailed.png', dpi=300, bbox_inches='tight')
plt.close()
print('Detailed diagram generated at docs/PPTs/full_system_architecture_detailed.png')
