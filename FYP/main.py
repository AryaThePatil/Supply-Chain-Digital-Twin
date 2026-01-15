"""
Main entry point for Digital Twin Supply Chain Simulation.

Usage:
    python main.py [--config CONFIG] [--duration-days DAYS] [--time-step MINUTES] [--seed SEED]

Examples:
    # Run 7-day simulation with default settings
    python main.py
    
    # Run 30-day simulation with 5-minute time steps
    python main.py --duration-days 30 --time-step 5
    
    # Run with specific random seed for reproducibility
    python main.py --seed 42
"""

from src.simulation.engine import SimulationEngine, parse_arguments
from src.data.config_loader import load_config
from src.simulation.agents.warehouse_agent import WarehouseAgent
from src.simulation.agents.retailer_agent import RetailerAgent
from src.simulation.entities.truck import TruckType
from typing import Dict
import random
import logging

# Configuration loaded from simulation_config.yaml


# ============================================================================
# DYNAMIC AGENT GENERATION FUNCTIONS (Phase 2 - New Code)
# ============================================================================

def generate_dynamic_warehouses(config, road_network):
    """
    Generate warehouses with random counts and capacities.
    
    FIXED: Validates locations are on roads.
    FIXED: Collision detection (1km minimum spacing).
    FIXED: Dynamic sizing and fleet configuration.
    
    Args:
        config: Configuration dictionary with agent_generation section
        road_network: RoadNetwork instance for location validation
    
    Returns:
        List of warehouse configuration dictionaries
    """
    gen_config = config['agent_generation']['warehouses']
    bbox = config['simulation']['location']['bounding_box']
    
    # Random warehouse count
    wh_count = random.randint(*gen_config['count_range'])
    
    # Get size probabilities from config
    size_probabilities = gen_config.get('size_probabilities', {
        'small': 0.4, 'medium': 0.4, 'large': 0.2
    })
    sizes = ['small', 'medium', 'large']
    size_weights = [size_probabilities.get(s, 0.3) for s in sizes]
    
    warehouses = []
    # Get minimum distance from config
    min_distance = config['agent_generation']['min_distances']['warehouse_km']
    
    # Get max attempts from config
    max_placement_attempts = config['agent_generation']['max_placement_attempts']
    
    # Get percentages from config
    initial_inventory_pct = gen_config.get('initial_inventory_pct', 0.7)
    restock_pct = gen_config.get('restock_pct', 0.6)
    
    for i in range(wh_count):
        # Pick random size
        size = random.choices(sizes, weights=size_weights)[0]
        size_config = gen_config[size]
        
        # Random capacity within range for this size
        capacity = random.uniform(*size_config['capacity_range_kg'])
        
        # Fleet size based on capacity
        fleet_size = random.randint(*size_config['fleet_range'])
        
        # Generate fleet mix based on percentages
        fleet = []
        for truck_type, percentage in size_config['fleet_mix'].items():
            count = int(fleet_size * percentage)
            if count > 0:
                fleet.append({'type': truck_type, 'count': count})
        
        # Find valid location (on road, not colliding)
        valid_location = None
        
        for attempt in range(max_placement_attempts):
            lat = random.uniform(bbox['south'], bbox['north'])
            lon = random.uniform(bbox['west'], bbox['east'])
            
            # Check if near road
            nearest_node = road_network.get_nearest_node(lat, lon)
            if nearest_node is None:
                continue
            
            # Check collision with existing warehouses using Haversine
            too_close = False
            for existing in warehouses:
                ex_lat = existing['location']['lat']
                ex_lon = existing['location']['lon']
                # Use Haversine distance (accurate for lat/lon)
                dist = road_network._haversine_distance(lat, lon, ex_lat, ex_lon)
                if dist < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                valid_location = (lat, lon)
                break
        
        if valid_location is None:
            logging.warning(f"Could not find valid location for warehouse {i+1}, skipping")
            continue
        
        lat, lon = valid_location
        
        warehouse = {
            'id': f'WH{i+1:03d}',
            'name': f'{size.capitalize()} Distribution Hub {i+1}',
            'location': {'lat': lat, 'lon': lon},
            'initial_inventory_kg': capacity * initial_inventory_pct,  # From config
            'fleet': fleet,
            'restock_schedule': {
                'day_of_week': 0,  # Sunday
                'time_of_day': '06:00',  # 6 AM
                'quantity_kg': capacity * restock_pct  # From config
            },
            '_size': size,  # Internal metadata
            '_capacity': capacity,
            'max_capacity_kg': capacity  # NEW - for capacity enforcement
        }
        
        warehouses.append(warehouse)
    
    return warehouses




def generate_dynamic_retailers(config, warehouses, road_network):
    """
    Generate retailers with random counts and capacities.
    
    FIXED: Validates locations are on roads.
    FIXED: Size-based distribution (40% small, 40% medium, 20% large).
    FIXED: Collision detection.
    
    Args:
        config: Configuration dictionary with agent_generation section
        warehouses: List of warehouse configurations (for assignment)
        road_network: RoadNetwork instance for location validation
    
    Returns:
        List of retailer configuration dictionaries
    """
    gen_config = config['agent_generation']['retailers']
    bbox = config['simulation']['location']['bounding_box']
    
    # Random retailer count
    ret_count = random.randint(*gen_config['count_range'])
    
    retailers = []
    # Get minimum distance from config
    min_distance = config['agent_generation']['min_distances']['retailer_km']
    
    # Get max attempts from config
    max_placement_attempts = config['agent_generation']['max_placement_attempts']
    
    # Get capacity ranges from config
    capacity_ranges = gen_config.get('capacity_ranges', {
        'small': [500, 2000],
        'medium': [2000, 5000],
        'large': [5000, 10000]
    })
    
    for i in range(ret_count):
        # Retailer size distribution (40-40-20)
        size_type = random.choices(
            ['small', 'medium', 'large'],
            weights=[0.4, 0.4, 0.2]
        )[0]
        
        # Capacity based on size (from config)
        capacity = random.uniform(*capacity_ranges[size_type])
        
        # Find valid location
        valid_location = None
        
        for attempt in range(max_placement_attempts):
            lat = random.uniform(bbox['south'], bbox['north'])
            lon = random.uniform(bbox['west'], bbox['east'])
            
            # Check if near road
            nearest_node = road_network.get_nearest_node(lat, lon)
            if nearest_node is None:
                continue
            
            # Check collision using Haversine distance
            too_close = False
            for existing in retailers + warehouses:
                ex_lat = existing['location']['lat']
                ex_lon = existing['location']['lon']
                # Use Haversine distance (accurate for lat/lon)
                dist = road_network._haversine_distance(lat, lon, ex_lat, ex_lon)
                if dist < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                valid_location = (lat, lon)
                break
        
        if valid_location is None:
            logging.warning(f"Could not find valid location for retailer {i+1}, skipping")
            continue
        
        lat, lon = valid_location
        
        init_pct = random.uniform(*gen_config['initial_stock_percentage'])
        initial_stock = capacity * init_pct
        
        reorder_pct = random.uniform(*gen_config['reorder_point_percentage'])
        reorder_point = capacity * reorder_pct
        
        # Multi-warehouse subscription (N7 feature)
        subscription_config = config['agent_generation']['retailer_warehouse_subscription']
        min_wh = subscription_config['min_warehouses']
        max_wh = subscription_config['max_warehouses'] or len(warehouses)
        
        # Determine how many warehouses this retailer subscribes to
        num_subscriptions = random.randint(min_wh, min(max_wh, len(warehouses)))
        
        # Sort warehouses by distance (Haversine - N3 fix)
        warehouses_by_distance = sorted(
            warehouses,
            key=lambda w: road_network._haversine_distance(
                lat, lon, w['location']['lat'], w['location']['lon']
            )
        )
        
        # Subscribe to N closest warehouses
        subscribed_warehouse_ids = [
            wh['id'] for wh in warehouses_by_distance[:num_subscriptions]
        ]
        
        retailer = {
            'id': f'RET{i+1:03d}',
            'warehouse_ids': subscribed_warehouse_ids,  # List, not single ID
            'location': {'lat': lat, 'lon': lon},
            'initial_stock_kg': initial_stock,
            '_storage_capacity': capacity,
            '_reorder_point': reorder_point,
            '_size_type': size_type
        }

        
        retailers.append(retailer)
    
    return retailers


def parse_truck_types(config) -> Dict[str, TruckType]:
    """
    Parse truck types from configuration.
    
    Helper function to avoid code duplication between main.py and engine.py.
    
    Args:
        config: Configuration dictionary containing truck_types section
        
    Returns:
        Dictionary mapping truck type names to TruckType objects
    """
    truck_types = {}
    for type_name, type_config in config['truck_types'].items():
        truck_types[type_name] = TruckType(
            name=type_name,
            capacity_kg=type_config['capacity_kg'],
            fuel_tank_liters=type_config['fuel_tank_liters'],
            fuel_consumption_empty_l_per_100km=type_config['fuel_consumption_empty_l_per_100km'],
            fuel_consumption_full_l_per_100km=type_config['fuel_consumption_full_l_per_100km'],
            fuel_efficiency_by_speed=type_config['fuel_efficiency_by_speed'],
            max_speed_kmh=type_config['max_speed_kmh'],
            cost_per_liter=type_config['cost_per_liter'],
            loading_time_per_ton_minutes=type_config['loading_time_per_ton_minutes'],
            unloading_time_per_ton_minutes=type_config['unloading_time_per_ton_minutes']
        )
    return truck_types


def initialize_agents(engine, config):
    """
    Initialize all agents (warehouses, retailers, trucks).
    
    Args:
        engine: SimulationEngine instance
        config: Configuration dictionary
    """
    # 1. Parse truck types from config
    truck_types = parse_truck_types(config)
    
    print(f"   [OK] Truck types: {list(truck_types.keys())}")
    
    #Always use dynamic agent generation
    warehouses_config = generate_dynamic_warehouses(config, engine.road_network)
    print(f"   [OK] Generated {len(warehouses_config)} warehouses dynamically")
    
    retailers_config = generate_dynamic_retailers(config, warehouses_config, engine.road_network)
    print(f"   [OK] Generated {len(retailers_config)} retailers dynamically")
    
    # ========================================================================
    # REST OF INITIALIZATION (unchanged - works with both dynamic and legacy)
    # ========================================================================
    
    # 2. Create warehouse agents
    for wh_config in warehouses_config:
        warehouse = WarehouseAgent(
            warehouse_id=wh_config['id'],
            location=(wh_config['location']['lat'], wh_config['location']['lon']),
            initial_inventory_kg=wh_config['initial_inventory_kg'],
            fleet_config=wh_config['fleet'],
            truck_types=truck_types,
            road_network=engine.road_network,
            router=engine.router,
            config=config
        )
        
        # Add restock schedule
        warehouse.restock_schedule = wh_config['restock_schedule']
        
        engine.warehouses.append(warehouse)
        
        # Collect all trucks from this warehouse
        engine.trucks.extend(warehouse.trucks)
        
        print(f"   [OK] {warehouse.warehouse_id}: {len(warehouse.trucks)} trucks, "
              f"{warehouse.current_inventory_kg:.0f}kg inventory")
    
    # Create retailer agents (DEDENTED - outside warehouse loop)
    for ret_config in retailers_config:
        retailer = RetailerAgent(
            retailer_id=ret_config['id'],
            location=(ret_config['location']['lat'], ret_config['location']['lon']),
            initial_inventory_kg=ret_config['initial_stock_kg'],
            warehouse_ids=ret_config['warehouse_ids'],  # Changed from warehouse_id
            demand_config=config['retailers']['demand'],
            inventory_config=config['retailers']['inventory'],
            road_network=engine.road_network,
            config=config  # Pass full config for selection weights
        )
        engine.retailers.append(retailer)
    
    print(f"   [OK] Created {len(engine.retailers)} retailers")
    print(f"   [OK] Total trucks: {len(engine.trucks)}")
    print(f"   [OK] Total agents: {len(engine.warehouses)} warehouses, "
          f"{len(engine.retailers)} retailers, {len(engine.trucks)} trucks")


def main():
    """Main entry point for the simulation."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Initialize logging FIRST (before any other operations)
    from src.utils.logger import setup_logging
    import logging
    from datetime import datetime
    
    # Create unique run ID
    run_id = f"sim-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Load config first to get log level
    config_path = args.config if args.config else 'config/simulation_config.yaml'
    try:
        from src.data.config_loader import load_config
        config = load_config(config_path)
        log_level_str = config.get('logging', {}).get('log_level', 'INFO')
        log_level = getattr(logging, log_level_str, logging.INFO)
    except Exception:
        log_level = logging.INFO  # Fallback
        config = None
    
    # Setup logging with config-driven level
    log_file = setup_logging(run_id, log_dir="logs", log_level=log_level)

    logger = logging.getLogger(__name__)
    
    logger.info("Digital Twin Supply Chain Simulation")
    logger.info("=" * 80)
    
    logger.info("Loading configuration...")
    config_path = args.config if args.config else 'config/simulation_config.yaml'
    
    try:
        config = load_config(config_path)
        logger.info(f"Configuration loaded from: {config_path}")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        print(f"[ERROR] Configuration file not found: {config_path}")
        return 1
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        print(f"[ERROR] Error loading configuration: {e}")
        return 1
    
    # Create simulation engine
    try:
        engine = SimulationEngine(
            config=config,
            duration_days=args.duration_days,
            time_step_minutes=args.time_step,
            random_seed=args.seed,
            speed_multiplier=args.speed,
            start_date=args.start_date
        )
    except Exception as e:
        print(f"[ERROR] Error initializing simulation: {e}")
        return 1
    
    # Initialize components
    try:
        print("\n" + "=" * 60)
        print("Initializing Simulation Components")
        print("=" * 60 + "\n")
        
        # Initialize road network (Phase 2)
        print("📍 Initializing road network...")
        engine.initialize_road_network(use_cache=True)
        
        # Initialize weather and disruptions (Phase 4)
        print("[WEATHER]  Initializing weather and disruptions...")
        engine.initialize_weather_and_disruptions()
        
        # Initialize agents (Phase 3/4)
        print("🏭 Initializing agents (warehouses, retailers, trucks)...")
        initialize_agents(engine, config)
        
        # Schedule warehouse restocking events
        if engine.warehouses:
            engine.schedule_warehouse_restocking()
        
        print("\n[OK] All components initialized")
        
    except Exception as e:
        print(f"[ERROR] Error initializing components: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Run simulation
    try:
        engine.run()
        print("\n[OK] Simulation completed successfully")
        return 0
    except KeyboardInterrupt:
        print("\n[WARNING]  Simulation interrupted by user")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Simulation error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
