"""
1-Day Full-Scale Simulation Audit
Monitors all events to verify realistic behavior on full Nagpur city map.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.simulation.engine import SimulationEngine
from src.data.config_loader import load_config
from main import initialize_agents
from unittest.mock import MagicMock
import json

def audit_full_scale():
    print("=" * 60)
    print("FULL-SCALE NAGPUR SIMULATION AUDIT (1 Day)")
    print("=" * 60)
    
    config = load_config('config/simulation_config.yaml')
    
    # Initialize
    engine = SimulationEngine(config, duration_days=1, time_step_minutes=1)
    engine.initialize_road_network(use_cache=True)
    engine.initialize_weather_and_disruptions()
    initialize_agents(engine, config)
    
    # Event tracking
    events_log = []
    order_timeline = {}  # order_id -> [events]
    truck_stats = {}     # truck_id -> {distance, trips}
    
    def track_event(topic, payload, qos=0, retain=False):
        event_type = payload.get('type') or payload.get('event_type')
        if not event_type:
            return
            
        event = {
            'time': payload.get('time', 0),
            'type': event_type,
            'data': payload
        }
        events_log.append(event)
        
        # Track order lifecycle
        order_id = payload.get('order_id')
        if order_id:
            if order_id not in order_timeline:
                order_timeline[order_id] = []
            order_timeline[order_id].append(event)
    
    mock_mqtt = MagicMock()
    mock_mqtt.publish.side_effect = track_event
    engine.mqtt_client = mock_mqtt
    engine.mqtt_connected = True
    
    print(f"\n✅ Initialized:")
    print(f"   Warehouses: {len(engine.warehouses)}")
    print(f"   Retailers : {len(engine.retailers)}")
    print(f"   Trucks    : {len(engine.trucks)}")
    print(f"   Map Nodes : {len(engine.road_network.graph.nodes):,}")
    print(f"   Map Edges : {len(engine.road_network.graph.edges):,}")
    
    # Run simulation
    total_steps = int(24 * 60 / engine.time_step)
    print(f"\n🏃 Running {total_steps} steps (24 hours @ 5min/step)...")
    
    for step in range(total_steps):
        engine._process_events()
        engine.current_time += engine.time_step
        engine._update_agents()
        engine._update_environment()
        
        if step % 60 == 0:  # Every 5 hours
            hour = (step * 5) / 60
            print(f"   Hour {hour:.1f}: {len(events_log)} events so far...")
    
    print(f"\n✅ Simulation complete! Total events: {len(events_log)}")
    
    # ANALYSIS
    print("\n" + "=" * 60)
    print("REALITY CHECK ANALYSIS")
    print("=" * 60)
    
    # Analyze a sample order
    if order_timeline:
        sample_order_id = list(order_timeline.keys())[0]
        sample_events = order_timeline[sample_order_id]
        
        print(f"\n📦 Sample Order: {sample_order_id}")
        print(f"   Events: {len(sample_events)}")
        
        times = {}
        for evt in sample_events:
            times[evt['type']] = evt['time']
            
        if 'order_placed' in times and 'loading_started' in times:
            dispatch_delay = times['loading_started'] - times['order_placed']
            print(f"   ⏱️  Dispatch  : {dispatch_delay:.1f} min")
        
        if 'loading_started' in times and 'loading_complete' in times:
            loading_time = times['loading_complete'] - times['loading_started']
            print(f"   📦 Loading   : {loading_time:.1f} min {'✅' if loading_time >= 10 else '⚠️  (too fast!)'}")
        
        if 'truck_departure' in times and 'truck_arrival' in times:
            travel_time = times['truck_arrival'] - times['truck_departure']
            print(f"   🚚 Transit   : {travel_time:.1f} min {'✅' if travel_time >= 10 else '⚠️  (too fast!)'}")
        
        if 'unloading_started' in times and 'unloading_complete' in times:
            unload_time = times['unloading_complete'] - times['unloading_started']
            print(f"   📤 Unloading : {unload_time:.1f} min {'✅' if unload_time >= 10 else '⚠️  (too fast!)'}")
    
    # Event type summary
    event_counts = {}
    for evt in events_log:
        event_type = evt['type']
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    print(f"\n📊 Event Summary:")
    for event_type in sorted(event_counts.keys()):
        print(f"   {event_type:25s}: {event_counts[event_type]:4d}")
    
    print("\n" + "=" * 60)
    print("VERDICT:")
    if order_timeline:
        sample_events = order_timeline[list(order_timeline.keys())[0]]
        times = {evt['type']: evt['time'] for evt in sample_events}
        
        checks = []
        if 'loading_complete' in times and 'loading_started' in times:
            load_time = times['loading_complete'] - times['loading_started']
            checks.append(("Loading delay", load_time >= 10, f"{load_time:.1f} min"))
        
        if 'truck_arrival' in times and 'truck_departure' in times:
            travel_time = times['truck_arrival'] - times['truck_departure']
            checks.append(("Travel time", travel_time >= 10, f"{travel_time:.1f} min"))
        
        if 'unloading_complete' in times and 'unloading_started' in times:
            unload_time = times['unloading_complete'] - times['unloading_started']
            checks.append(("Unloading delay", unload_time >= 10, f"{unload_time:.1f} min"))
        
        all_pass = all(check[1] for check in checks)
        
        for name, passed, value in checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {name:20s} = {value}")
        
        if all_pass:
            print("\n🎉 SIMULATION IS REALISTIC!")
        else:
            print("\n⚠️  Some checks failed - review above")
    else:
        print("⚠️  No orders processed - may need longer simulation")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        audit_full_scale()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
