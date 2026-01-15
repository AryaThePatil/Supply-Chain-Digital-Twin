"""
Router for finding optimal paths through the road network.

Uses A* algorithm with multi-objective cost function considering:
- Distance (km)
- Time (minutes)
- Fuel consumption (liters)
"""

import networkx as nx
from typing import List, Tuple, Dict, Any, Optional
import math


class Router:
    """
    Router for finding optimal paths in road network.
    
    Uses A* pathfinding with configurable cost function that balances:
    - Distance: Total kilometers traveled
    - Time: Total travel time in minutes
    - Fuel: Total fuel consumption in liters
    
    Can avoid blocked segments (accidents) and recalculate routes dynamically.
    """
    
    def __init__(self, road_network, config: Dict[str, Any]):
        """
        Initialize router.
        
        Args:
            road_network: RoadNetwork instance
            config: Configuration dictionary with routing parameters
        """
        self.road_network = road_network
        self.config = config
        
        # Cost function weights
        routing_config = config.get('routing', {})
        cost_weights = routing_config.get('cost_weights', {})
        self.weight_distance = cost_weights.get('distance_km', 1.0)
        self.weight_time = cost_weights.get('time_minutes', 0.5)
        self.weight_fuel = cost_weights.get('fuel_liters', 2.0)
        self.weight_road_quality = cost_weights.get('road_quality', 5.0)  # New weight for road comfort/safety
        
        # Route caching for performance
        self.cache_enabled = routing_config.get('cache_enabled', True)
        self.cache_ttl_minutes = routing_config.get('cache_ttl_minutes', 30)
        self.route_cache: Dict[Tuple[int, int], Dict[str, Any]] = {}
        
        print(f"🧭 Router initialized")
        print(f"   Cost weights: distance={self.weight_distance}, "
              f"time={self.weight_time}, fuel={self.weight_fuel}, quality={self.weight_road_quality}")
        print(f"   Cache: {'enabled' if self.cache_enabled else 'disabled'}")
    
    def find_path(self, start_node: int, end_node: int, 
                  truck_type_config: Dict[str, Any],
                  load_fraction: float = 0.5,
                  avoid_blocked: bool = True,
                  current_time: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Find optimal path from start to end node.
        
        Uses A* algorithm with multi-objective cost function.
        
        Args:
            start_node: Starting node ID
            end_node: Destination node ID
            truck_type_config: Truck type configuration for fuel calculation
            load_fraction: Fraction of truck capacity loaded (0.0 to 1.0)
            avoid_blocked: If True, avoid blocked segments
            current_time: Current simulation time (for cache invalidation)
        
        Returns:
            Dictionary with route information:
            {
                'nodes': [node_ids],
                'segments': [segment_ids],
                'total_distance_km': float,
                'total_time_minutes': float,
                'total_fuel_liters': float,
                'total_cost': float
            }
            Returns None if no path exists
        """
        # Check cache
        cache_key = (start_node, end_node)
        if self.cache_enabled and cache_key in self.route_cache:
            cached_route = self.route_cache[cache_key]
            # Check if cache is still valid
            if current_time - cached_route['cached_at'] < self.cache_ttl_minutes:
                # Verify no segments are blocked
                if not avoid_blocked or not self._route_has_blocked_segments(cached_route):
                    return cached_route['route']
        
        # Define cost function for A*
        def edge_cost(u: int, v: int, edge_data: Dict[str, Any]) -> float:
            """Calculate cost for traversing an edge."""
            # Get segment_id from edge data (we stored it when building network)
            segment_id = edge_data.get('segment_id')
            
            if segment_id:
                segment = self.road_network.get_segment(segment_id)
            else:
                # Fallback: try to find segment by nodes (assume key=0)
                segment = self.road_network.get_segment_by_nodes(u, v, 0)
            
            if segment is None:
                return float('inf')
            
            # Skip blocked segments if requested
            if avoid_blocked and segment.is_blocked:
                return float('inf')
            
            # Calculate components
            distance_km = segment.length_km
            time_minutes = segment.get_travel_time_minutes()
            fuel_liters = segment.get_fuel_consumption_liters(truck_type_config, load_fraction)
            
            # Apply road quality penalty from config
            surface = segment.surface_type.lower() if segment.surface_type else 'unknown'
            road_penalties = self.config.get('routing', {}).get('road_quality_penalties', {})
            quality_penalty = road_penalties.get(surface, 1.5)  # Default to 1.5 for unknown
            
            # Additional lane penalty (narrow roads) from config
            if segment.lanes == 1:
                lane_penalty = self.config.get('routing', {}).get('single_lane_penalty', 1.0)
                quality_penalty += lane_penalty
            
            # Multi-objective cost
            # Cost = Distance + Time + Fuel + QualityPenalty * Weight
            cost = (self.weight_distance * distance_km +
                   self.weight_time * time_minutes +
                   self.weight_fuel * fuel_liters +
                   self.weight_road_quality * quality_penalty)
            
            return cost
        
        # Define heuristic function for A* (straight-line distance)
        def heuristic(u: int, v: int) -> float:
            """Estimate cost from u to v using straight-line distance."""
            pos_u = self.road_network.get_node_position(u)
            pos_v = self.road_network.get_node_position(v)
            
            if pos_u is None or pos_v is None:
                return 0.0
            
            # Haversine distance
            distance_km = self._haversine_distance(pos_u[0], pos_u[1], pos_v[0], pos_v[1])
            
            # Estimate cost using distance weight only (lower bound)
            return self.weight_distance * distance_km
        
        # Run A* algorithm
        try:
            node_path = nx.astar_path(
                self.road_network.graph,
                start_node,
                end_node,
                heuristic=heuristic,
                weight=edge_cost
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # No path exists
            return None
        
        # Build route information
        route = self._build_route_info(node_path, truck_type_config, load_fraction)
        
        # Cache the route
        if self.cache_enabled:
            self.route_cache[cache_key] = {
                'route': route,
                'cached_at': current_time
            }
        
        return route
    
    def _build_route_info(self, node_path: List[int], 
                         truck_type_config: Dict[str, Any],
                         load_fraction: float) -> Dict[str, Any]:
        """
        Build detailed route information from node path.
        
        Args:
            node_path: List of node IDs in path
            truck_type_config: Truck type configuration
            load_fraction: Load fraction
        
        Returns:
            Route information dictionary
        """
        segments = []
        total_distance_km = 0.0
        total_time_minutes = 0.0
        total_fuel_liters = 0.0
        
        # Process each edge in path
        for i in range(len(node_path) - 1):
            u = node_path[i]
            v = node_path[i + 1]
            
            # Get edge data (handle multigraph - may have multiple parallel edges)
            edge_data = self.road_network.graph.get_edge_data(u, v)
            if edge_data is None:
                continue
            
            # Handle multigraph: find best edge among parallel edges
            if isinstance(edge_data, dict) and len(edge_data) > 1:
                # Multiple parallel edges exist, find shortest/fastest
                best_key = None
                best_length = float('inf')
                
                for key, data in edge_data.items():
                    length = data.get('length', float('inf'))
                    if length < best_length:
                        best_length = length
                        best_key = key
                
                key = best_key if best_key is not None else 0
            elif isinstance(edge_data, dict) and 0 in edge_data:
                # Single edge in multigraph format
                key = 0
            else:
                # Simple graph
                key = 0
            
            # Get RoadSegment
            segment = self.road_network.get_segment_by_nodes(u, v, key)
            if segment is None:
                continue
            
            segments.append(segment.segment_id)
            total_distance_km += segment.length_km
            total_time_minutes += segment.get_travel_time_minutes()
            total_fuel_liters += segment.get_fuel_consumption_liters(truck_type_config, load_fraction)
        
        # Calculate total cost
        total_cost = (self.weight_distance * total_distance_km +
                     self.weight_time * total_time_minutes +
                     self.weight_fuel * total_fuel_liters)
        
        # Get actual RoadSegment objects for the route
        segment_objects = []
        for seg_id in segments:
            seg = self.road_network.get_segment(seg_id)
            if seg:
                segment_objects.append(seg)
        
        return {
            'nodes': node_path,
            'segments': segments,  # Keep segment IDs for reference
            'segment_objects': segment_objects,  # Add actual RoadSegment objects
            'total_distance_km': round(total_distance_km, 3),
            'total_time_minutes': round(total_time_minutes, 2),
            'total_fuel_liters': round(total_fuel_liters, 3),
            'total_cost': round(total_cost, 2)
        }
    
    def _route_has_blocked_segments(self, cached_route: Dict[str, Any]) -> bool:
        """
        Check if cached route contains any blocked segments.
        
        Args:
            cached_route: Cached route dictionary
        
        Returns:
            True if any segment is blocked
        """
        route = cached_route['route']
        for segment_id in route['segments']:
            segment = self.road_network.get_segment(segment_id)
            if segment and segment.is_blocked:
                return True
        return False
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
        
        Returns:
            Distance in kilometers
        """
        # Earth radius in km
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance
    
    def invalidate_cache(self) -> None:
        """Clear route cache (e.g., when accidents occur)."""
        self.route_cache.clear()
    
    def precompute_common_routes(self, warehouses: List, retailers: List, 
                                truck_types: Dict[str, Any]) -> None:
        """
        OPTIMIZATION 5: Pre-compute routes for common warehouse-retailer pairs.
        
        Called once at simulation start to populate route cache.
        Eliminates pathfinding delays during initial truck dispatches.
        
        Args:
            warehouses: List of warehouse agents
            retailers: List of retailer agents
            truck_types: Dictionary of truck type configurations
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.cache_enabled:
            logger.info("Route pre-computation skipped (cache disabled)")
            return
        
        logger.info("Pre-computing common routes...")
        route_count = 0
        
        # Pre-compute for each warehouse-retailer pair
        for wh in warehouses:
            # Warehouses are WarehouseAgent objects - access node_id directly
            wh_node = wh.node_id if hasattr(wh, 'node_id') else wh.warehouse.location_node if hasattr(wh, 'warehouse') else None
            
            if not wh_node:
                continue
            
            for ret in retailers:
                # Retailers are RetailerAgent objects - access node_id directly  
                ret_node = ret.node_id if hasattr(ret, 'node_id') else ret.retailer.location_node if hasattr(ret, 'retailer') else None
                
                if not ret_node:
                    continue
                
                # Use a typical truck type for pre-computation (medium)
                typical_truck = truck_types.get('medium', next(iter(truck_types.values())))
                
                # Pre-compute route (adds to cache)
                route = self.find_path(
                    wh_node, ret_node,
                    truck_type_config=typical_truck,
                    load_fraction=0.5,  # Assume half-loaded
                    avoid_blocked=True,
                    current_time=0.0
                )
                
                if route:
                    route_count += 1
        
        logger.info(f"Pre-computed {route_count} routes ({len(warehouses)} WH × {len(retailers)} retailers)")

    
    def should_reroute(self, current_route: Dict[str, Any], 
                      start_node: int, end_node: int,
                      truck_type_config: Dict[str, Any],
                      load_fraction: float,
                      current_time: float) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if truck should reroute based on current conditions.
        
        Compares current route with alternative route. Recommends rerouting
        if alternative is significantly better (>10% improvement).
        
        Args:
            current_route: Current route information
            start_node: Current position node
            end_node: Destination node
            truck_type_config: Truck type configuration
            load_fraction: Load fraction
            current_time: Current simulation time
        
        Returns:
            Tuple of (should_reroute: bool, new_route: Dict or None)
        """
        # Find alternative route
        alternative_route = self.find_path(
            start_node, end_node,
            truck_type_config, load_fraction,
            avoid_blocked=True,
            current_time=current_time
        )
        
        if alternative_route is None:
            # No alternative exists
            return (False, None)
        
        # Compare costs
        current_cost = current_route['total_cost']
        alternative_cost = alternative_route['total_cost']
        
        # Reroute if alternative is >10% better
        threshold = self.config.get('routing', {}).get('recalculation_threshold', 0.10)
        improvement = (current_cost - alternative_cost) / current_cost
        
        if improvement > threshold:
            return (True, alternative_route)
        
        return (False, None)
