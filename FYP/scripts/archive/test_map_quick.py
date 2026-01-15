"""Quick test to verify the Nagpur map loads correctly."""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.simulation.engine import SimulationEngine
from src.data.config_loader import load_config

print("Testing Nagpur city map load...")
config = load_config('config/simulation_config.yaml')

engine = SimulationEngine(config, duration_days=1, time_step_minutes=1)
engine.initialize_road_network(use_cache=False)

print(f"\nSUCCESS! Map Statistics:")
print(f"  Nodes: {len(engine.road_network.graph.nodes):,}")
print(f"  Edges: {len(engine.road_network.graph.edges):,}")
print(f"  BBox : N={engine.road_network.north}, S={engine.road_network.south}")
print(f"         E={engine.road_network.east}, W={engine.road_network.west}")
