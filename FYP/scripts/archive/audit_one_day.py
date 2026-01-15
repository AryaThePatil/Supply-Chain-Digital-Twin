
import sys
import os
import json
import logging
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.simulation.engine import SimulationEngine
from src.data.config_loader import load_config

def audit_one_day():
    print("Starting 1-Day Manual Audit...")
    
    # Load strict production config
    config = load_config('config/simulation_config.yaml')
    
    # Initialize Engine (1 day, 1 min step for high resolution)
    engine = SimulationEngine(config, duration_days=1, time_step_minutes=1)
    
    # Capture events to stdout for Manual Audit
    def side_effect(topic, payload, qos=0, retain=False):
        t = payload.get('type') or payload.get('event_type')
        
        # Filter for interesting events
        interesting = [
            'order_placed', 'order_assigned', 
            'loading_started', 'loading_complete', 
            'truck_departure', 'truck_arrival', 
            'unloading_started', 'unloading_complete', 
            'delivery_completed'
        ]
        
        if t in interesting:
            # Print formatted log line for user inspection
            timestamp = payload.get('time', 0)
            truck_id = payload.get('truck_id', 'N/A')
            order_id = payload.get('order_id', 'N/A')
            
            msg = f"[{timestamp:6.1f}] {t:20} | Trk: {truck_id} | Ord: {order_id}"
            
            if t == 'loading_started':
                msg += f" | Dur: {payload.get('duration_minutes')} min"
            elif t == 'unloading_started':
                msg += f" | Dur: {payload.get('duration_minutes')} min"
            elif t == 'truck_arrival':
                msg += f" | Dest: {payload.get('destination')}"
                
            print(msg)
            
    mock_mqtt = MagicMock()
    mock_mqtt.publish.side_effect = side_effect
    engine.mqtt_client = mock_mqtt
    engine.mqtt_connected = True
    
    # Init components
    engine.initialize_road_network(use_cache=True)
    engine.initialize_weather_and_disruptions()
    
    from main import initialize_agents
    initialize_agents(engine, config)
    
    print("Components Initialized. Running Simulation...")
    
    # Run loop
    try:
        total_steps = int(24 * 60 / engine.time_step)
        for i in range(total_steps):
            # Simulation Loop Step
            engine._process_events()
            engine.current_time += engine.time_step
            engine._update_agents()
            engine._update_environment()
            
            if i % 60 == 0:
                print(f"--- Hour {i//60} ---")
                
    except KeyboardInterrupt:
        print("Interrupted.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    audit_one_day()
