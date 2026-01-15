
import sys
import os
import networkx as nx

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.simulation.engine import SimulationEngine
from src.data.config_loader import load_config
from src.simulation.network.road_network import RoadNetwork
from src.simulation.network.router import Router

def debug_network():
    import sys
    print("🗺️  Starting Road Network Realism Check...", flush=True)
    
    config = load_config('config/simulation_config.yaml')
    
    # 1. Inspect Coordinates from Config
    wh_config = next(w for w in config['warehouses'] if w['id'] == 'WH001')
    wh_loc = (wh_config['location']['lat'], wh_config['location']['lon'])
    
    # Retailer locations are generated/fixed. We need to instantiate Engine to see them.
    print("   Initializing Road Network (loading OSM data)... (This may take time)", flush=True)
    try:
        engine = SimulationEngine(config, duration_days=1, time_step_minutes=1)
        engine.initialize_road_network(use_cache=False)
        print("   ✅ OSM Data Downloaded/Loaded!", flush=True)
    except Exception as e:
        print(f"   ❌ FAILED to load OSM Data: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return
    
    # DEBUG: Check Network Scale
    print(f"\n🗺️  Network Stats:", flush=True)
    print(f"   Nodes: {len(engine.road_network.graph.nodes)}")
    print(f"   Edges: {len(engine.road_network.graph.edges)}")
    print(f"   BBox : N={engine.road_network.north}, S={engine.road_network.south}, E={engine.road_network.east}, W={engine.road_network.west}")
    sys.stdout.flush()
    
    from main import initialize_agents
    initialize_agents(engine, config)
    
    # Find a random retailer
    if not engine.retailers:
        print("❌ No retailers found!")
        return
        
    ret_agent = engine.retailers[0] # Pick the first one
    ret_loc = ret_agent.location
    
    print(f"\n📍 Locations (Full Scale Check):")
    print(f"   WH001 : {wh_loc}")
    print(f"   RET_0 : {ret_loc} (ID: {ret_agent.retailer_id})")
    
    # 2. Calculate Haversine Distance (Air)
    def haversine_distance(lat1, lon1, lat2, lon2):
        import math
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    air_dist = haversine_distance(wh_loc[0], wh_loc[1], ret_loc[0], ret_loc[1])
    print(f"\n📏 Air Distance: {air_dist:.4f} km")
    
    # 3. Network Nodes
    print(f"\n🕸️  Graph Node Mapping:")
    wh_node = engine.road_network.get_nearest_node(wh_loc[0], wh_loc[1])
    ret_node = engine.road_network.get_nearest_node(ret_loc[0], ret_loc[1])
    
    wh_node_loc = engine.road_network.graph.nodes[wh_node]
    ret_node_loc = engine.road_network.graph.nodes[ret_node]
    
    dist_wh_snap = haversine_distance(wh_loc[0], wh_loc[1], wh_node_loc['y'], wh_node_loc['x'])
    dist_ret_snap = haversine_distance(ret_loc[0], ret_loc[1], ret_node_loc['y'], ret_node_loc['x'])
    
    print(f"   WH001 Node : {wh_node} (Snap Dist: {dist_wh_snap:.4f} km)")
    print(f"     -> Target Loc: {wh_loc}")
    print(f"     -> Node Loc  : ({wh_node_loc['y']}, {wh_node_loc['x']})")
    
    print(f"   RET_0 Node : {ret_node} (Snap Dist: {dist_ret_snap:.4f} km)")
    print(f"     -> Target Loc: {ret_loc}")
    print(f"     -> Node Loc  : ({ret_node_loc['y']}, {ret_node_loc['x']})")
    
    if dist_wh_snap > 2.0 or dist_ret_snap > 2.0:
        print("   ⚠️  WARNING: Location is VERY FAR from any road! Routing likely to fail.")
    
    print(f"\n🕸️  Network Nodes:")
    print(f"   WH001 Node : {wh_node}")
    print(f"   RET009 Node: {ret_node}")
    
    if wh_node == ret_node:
        print("   ⚠️  WARNING: Warehouse and Retailer map to the SAME node! Travel time will be 0.")
    
    # 4. Route Calculation
    print(f"\n🚗 Calculating A* Route on Road Graph...")
    router = Router(engine.road_network, config)
    
    try:
        # Dummy truck config
        truck_config = config['truck_types']['medium']
        truck_type_dict = {
            'capacity_kg': truck_config['capacity_kg'],
            'fuel_consumption_empty_l_per_100km': truck_config['fuel_consumption_empty_l_per_100km'],
            'fuel_consumption_full_l_per_100km': truck_config['fuel_consumption_full_l_per_100km'],
            'fuel_efficiency_by_speed': truck_config['fuel_efficiency_by_speed']
        }
        
        path = router.find_path(
            wh_node, ret_node, 
            truck_type_config=truck_type_dict, 
            current_time=0.0
        )
        
        if path:
            segments = path.get('segment_objects', [])
            total_dist_road = sum(s.length_km for s in segments)
            total_time_min = sum(s.get_travel_time_minutes() for s in segments)
            
            print(f"   Route Found!")
            print(f"   Segments     : {len(segments)}")
            print(f"   Road Distance: {total_dist_road:.4f} km")
            print(f"   Est. Time    : {total_time_min:.4f} minutes")
            
            print("\n   Detailed Segments:")
            for i, seg in enumerate(segments[:5]):
                print(f"     {i+1}. Len: {seg.length_km:.3f}km | Speed: {seg.current_speed_kmh}km/h | Time: {seg.get_travel_time_minutes():.3f}m")
            if len(segments) > 5: print("     ...")
        else:
            print("   ❌ No path found!")
            
    except Exception as e:
        print(f"   ❌ Routing Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_network()
