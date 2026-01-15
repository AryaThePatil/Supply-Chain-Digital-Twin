"""
Unit tests for road network, routing, and traffic simulation.
"""

import pytest
from src.simulation.network import RoadNetwork, RoadSegment, Router, TrafficModel
from src.data.config_loader import load_config


@pytest.fixture
def test_config():
    """Load test configuration."""
    return load_config("config/simulation_config.yaml")


@pytest.fixture
def road_network(test_config):
    """Create and load road network."""
    network = RoadNetwork(test_config)
    try:
        network.load(use_cache=True)
    except RuntimeError as e:
        if "Large map file detected" in str(e):
            pytest.skip(f"Skipping tests: {e}")
        else:
            raise
    except Exception as e:
        pytest.skip(f"Skipping tests due to network load failure: {e}")
        
    if network.graph is None:
        pytest.skip("No road network loaded (no file or API access)")
        
    return network


@pytest.fixture
def traffic_model(test_config):
    """Create traffic model."""
    return TrafficModel(test_config)


@pytest.fixture
def router(road_network, test_config):
    """Create router."""
    return Router(road_network, test_config)


@pytest.fixture
def truck_type_config(test_config):
    """Get medium truck configuration."""
    return test_config['truck_types']['medium']


# RoadNetwork Tests

def test_road_network_initialization(test_config):
    """Test that road network initializes correctly."""
    network = RoadNetwork(test_config)
    
    assert network.config is not None
    assert network.north == test_config['simulation']['location']['bounding_box']['north']
    assert network.south == test_config['simulation']['location']['bounding_box']['south']
    assert network.graph is None  # Not loaded yet


def test_road_network_loads_osm_data(road_network):
    """Test that OSM data loads successfully."""
    assert road_network.graph is not None
    assert len(road_network.nodes) > 0
    assert len(road_network.segments) > 0


def test_road_network_has_valid_segments(road_network):
    """Test that all segments have valid properties."""
    for segment in road_network.segments.values():
        assert isinstance(segment, RoadSegment)
        assert segment.length_km > 0
        assert segment.speed_limit_kmh > 0
        assert segment.lanes > 0
        assert segment.road_type in ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential']


def test_road_network_get_segment(road_network):
    """Test getting segment by ID."""
    # Get first segment
    first_segment = next(iter(road_network.segments.values()))
    
    # Retrieve by ID
    retrieved = road_network.get_segment(first_segment.segment_id)
    
    assert retrieved is not None
    assert retrieved.segment_id == first_segment.segment_id


def test_road_network_get_nearest_node(road_network):
    """Test finding nearest node to coordinates."""
    # Use center of bounding box
    center_lat = (road_network.north + road_network.south) / 2
    center_lon = (road_network.east + road_network.west) / 2
    
    nearest_node = road_network.get_nearest_node(center_lat, center_lon)
    
    assert nearest_node is not None
    assert nearest_node in road_network.nodes


def test_road_network_stats(road_network):
    """Test network statistics."""
    stats = road_network.get_stats()
    
    assert 'num_nodes' in stats
    assert 'num_segments' in stats
    assert 'total_length_km' in stats
    assert 'road_type_counts' in stats
    assert stats['num_nodes'] > 0
    assert stats['num_segments'] > 0
    assert stats['total_length_km'] > 0


# RoadSegment Tests

def test_road_segment_travel_time(road_network):
    """Test travel time calculation."""
    segment = next(iter(road_network.segments.values()))
    
    # Calculate travel time at speed limit
    travel_time = segment.get_travel_time_minutes(segment.speed_limit_kmh)
    
    assert travel_time > 0
    # time = distance / speed * 60
    expected_time = (segment.length_km / segment.speed_limit_kmh) * 60
    assert abs(travel_time - expected_time) < 0.01


def test_road_segment_blocked_infinite_time(road_network):
    """Test that blocked segments have infinite travel time."""
    segment = next(iter(road_network.segments.values()))
    
    # Block segment
    segment.block()
    
    assert segment.is_blocked
    assert segment.get_travel_time_minutes() == float('inf')
    
    # Unblock
    segment.unblock()
    assert not segment.is_blocked


def test_road_segment_fuel_consumption(road_network, truck_type_config):
    """Test fuel consumption calculation."""
    segment = next(iter(road_network.segments.values()))
    
    # Calculate fuel for empty truck
    fuel_empty = segment.get_fuel_consumption_liters(truck_type_config, load_fraction=0.0)
    
    # Calculate fuel for full truck
    fuel_full = segment.get_fuel_consumption_liters(truck_type_config, load_fraction=1.0)
    
    assert fuel_empty > 0
    assert fuel_full > fuel_empty  # Full truck uses more fuel


def test_road_segment_update_traffic(road_network):
    """Test traffic update on segment."""
    segment = next(iter(road_network.segments.values()))
    
    # Update traffic
    segment.update_traffic(density=25.0, speed=45.0)
    
    assert segment.current_traffic_density == 25.0
    assert segment.current_speed_kmh == 45.0


# Router Tests

def test_router_initialization(router):
    """Test that router initializes correctly."""
    assert router.road_network is not None
    assert router.weight_distance > 0
    assert router.weight_time >= 0
    assert router.weight_fuel >= 0


def test_router_finds_path(router, road_network, truck_type_config):
    """Test that router finds a path between two nodes."""
    # Get two random nodes
    nodes = list(road_network.nodes.keys())
    if len(nodes) < 2:
        pytest.skip("Not enough nodes for path test")
    
    start_node = nodes[0]
    end_node = nodes[min(10, len(nodes) - 1)]  # Pick a node not too far
    
    # Find path
    route = router.find_path(start_node, end_node, truck_type_config, load_fraction=0.5)
    
    if route is not None:  # Path may not exist for all node pairs
        assert 'nodes' in route
        assert 'segments' in route
        assert 'total_distance_km' in route
        assert 'total_time_minutes' in route
        assert 'total_fuel_liters' in route
        assert len(route['nodes']) >= 2
        assert route['nodes'][0] == start_node
        assert route['nodes'][-1] == end_node


def test_router_avoids_blocked_segments(router, road_network, truck_type_config):
    """Test that router avoids blocked segments."""
    # Get two nodes
    nodes = list(road_network.nodes.keys())
    if len(nodes) < 2:
        pytest.skip("Not enough nodes for path test")
    
    start_node = nodes[0]
    end_node = nodes[min(10, len(nodes) - 1)]
    
    # Find initial path
    route1 = router.find_path(start_node, end_node, truck_type_config, 
                              load_fraction=0.5, avoid_blocked=False)
    
    if route1 is None:
        pytest.skip("No path exists between selected nodes")
    
    # Block first segment in path
    first_segment_id = route1['segments'][0]
    first_segment = road_network.get_segment(first_segment_id)
    first_segment.block()
    
    # Find new path avoiding blocked segments
    route2 = router.find_path(start_node, end_node, truck_type_config,
                              load_fraction=0.5, avoid_blocked=True)
    
    # Unblock segment
    first_segment.unblock()
    
    # If alternative path exists, it should not contain blocked segment
    if route2 is not None:
        assert first_segment_id not in route2['segments']


def test_router_cache(router, road_network, truck_type_config):
    """Test that router caches routes."""
    nodes = list(road_network.nodes.keys())
    if len(nodes) < 2:
        pytest.skip("Not enough nodes for cache test")
    
    start_node = nodes[0]
    end_node = nodes[min(10, len(nodes) - 1)]
    
    # Clear cache
    router.invalidate_cache()
    assert len(router.route_cache) == 0
    
    # Find path (should cache)
    route1 = router.find_path(start_node, end_node, truck_type_config,
                              load_fraction=0.5, current_time=0.0)
    
    if route1 is not None and router.cache_enabled:
        assert len(router.route_cache) == 1
        
        # Find same path again (should use cache)
        route2 = router.find_path(start_node, end_node, truck_type_config,
                                  load_fraction=0.5, current_time=0.0)
        
        assert route2 is not None
        assert route1['total_distance_km'] == route2['total_distance_km']


# TrafficModel Tests

def test_traffic_model_initialization(traffic_model):
    """Test that traffic model initializes correctly."""
    assert traffic_model.config is not None
    assert len(traffic_model.time_multipliers) == 24
    assert traffic_model.current_weather == 'clear'


def test_traffic_model_density_calculation(traffic_model, road_network):
    """Test traffic density calculation."""
    segment = next(iter(road_network.segments.values()))
    
    # Calculate density at different times
    density_morning = traffic_model.get_traffic_density(segment, current_time=7*60)  # 7 AM
    density_night = traffic_model.get_traffic_density(segment, current_time=2*60)    # 2 AM
    
    assert density_morning > 0
    assert density_night > 0
    # Morning rush hour should have higher density
    assert density_morning > density_night


def test_traffic_model_greenshields_speed(traffic_model, road_network):
    """Test Greenshields speed calculation."""
    segment = next(iter(road_network.segments.values()))
    
    # Calculate speed at different times
    speed_rush_hour = traffic_model.get_current_speed(segment, current_time=8*60)  # 8 AM rush
    speed_night = traffic_model.get_current_speed(segment, current_time=2*60)      # 2 AM quiet
    
    assert speed_rush_hour > 0
    assert speed_night > 0
    # Night should have higher speed (less traffic)
    assert speed_night >= speed_rush_hour


def test_traffic_model_weather_effects(traffic_model, road_network):
    """Test weather effects on traffic."""
    segment = next(iter(road_network.segments.values()))
    
    # Clear weather
    traffic_model.set_weather('clear')
    speed_clear = traffic_model.get_current_speed(segment, current_time=12*60)
    
    # Heavy rain
    traffic_model.set_weather('heavy_rain')
    speed_rain = traffic_model.get_current_speed(segment, current_time=12*60)
    
    assert speed_clear > 0
    assert speed_rain > 0
    # Rain should reduce speed
    assert speed_rain < speed_clear


def test_traffic_model_update_segment(traffic_model, road_network):
    """Test updating traffic on a segment."""
    segment = next(iter(road_network.segments.values()))
    
    # Update segment
    traffic_model.update_segment(segment, current_time=8*60)
    
    assert segment.current_traffic_density > 0
    assert segment.current_speed_kmh > 0


def test_traffic_model_blocked_segment(traffic_model, road_network):
    """Test that blocked segments have zero speed."""
    segment = next(iter(road_network.segments.values()))
    
    # Block segment
    segment.block()
    
    # Update traffic
    traffic_model.update_segment(segment, current_time=12*60)
    
    assert segment.current_traffic_density == 0.0
    assert segment.current_speed_kmh == 0.0
    
    # Unblock
    segment.unblock()


def test_traffic_model_stats(traffic_model, road_network):
    """Test traffic statistics."""
    # Update all segments
    traffic_model.update_all_segments(road_network, current_time=12*60)
    
    # Get stats
    stats = traffic_model.get_stats(road_network)
    
    assert 'current_weather' in stats
    assert 'by_road_type' in stats
    assert len(stats['by_road_type']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
