"""Truck entity with type-specific attributes."""

from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class TruckType:
    """Type definition for trucks with operational characteristics."""
    
    name: str
    capacity_kg: int
    fuel_tank_liters: float
    fuel_consumption_empty_l_per_100km: float
    fuel_consumption_full_l_per_100km: float
    fuel_efficiency_by_speed: dict  # speed_kmh -> multiplier
    max_speed_kmh: float
    cost_per_liter: float
    loading_time_per_ton_minutes: float
    unloading_time_per_ton_minutes: float


class Truck:
    """Physical truck entity with fuel, cargo, and location tracking."""
    
    def __init__(self, truck_id: str, truck_type: TruckType, 
                 warehouse_id: str, initial_location: Tuple[float, float]):
        """
        Initialize a Truck.
        
        Args:
            truck_id: Unique identifier
            truck_type: TruckType definition with operational parameters
            warehouse_id: ID of owning warehouse
            initial_location: (lat, lon) starting position
        """
        self.truck_id = truck_id
        self.truck_type = truck_type
        self.warehouse_id = warehouse_id
        
        # Location tracking
        self.current_location = initial_location  # (lat, lon)
        self.current_node = None  # Current road network node
        
        # Fuel management
        self.current_fuel_liters = truck_type.fuel_tank_liters  # Start full
        self.total_fuel_consumed_liters = 0.0
        
        # Cargo tracking
        self.current_load_kg = 0.0
        self.cargo_batches = []  # List of OrangeBatch objects
        
        # Status tracking
        self.status = "idle"  # idle, loading, in_transit, unloading, refueling
        self.assigned_order_id: Optional[str] = None
        
        # Route tracking
        self.current_route: Optional[List] = None  # List of road segments
        self.route_progress = 0  # Index in current_route
        self.segment_distance_traveled = 0.0  # Distance traveled in current segment (km)
        self.destination_node = None
        
        # Operational metrics
        self.current_speed_kmh = 0.0  # Current speed for dashboard display
        self.total_distance_km = 0.0
        self.total_deliveries = 0
        self.last_reroute_time = 0
        
    def get_load_factor(self) -> float:
        """
        Calculate current load as fraction of capacity.
        
        Returns:
            Load factor between 0.0 (empty) and 1.0 (full)
        """
        return min(1.0, self.current_load_kg / self.truck_type.capacity_kg)
    
    def get_fuel_consumption_rate(self, speed_kmh: float) -> float:
        """
        Calculate fuel consumption rate in L/100km based on load and speed.
        
        Uses linear interpolation between empty and full consumption rates,
        then applies speed-dependent efficiency multiplier.
        
        Args:
            speed_kmh: Current speed in km/h
            
        Returns:
            Fuel consumption in L/100km
        """
        load_factor = self.get_load_factor()
        
        # Linear interpolation between empty and full consumption
        base_consumption = (
            self.truck_type.fuel_consumption_empty_l_per_100km * (1 - load_factor) +
            self.truck_type.fuel_consumption_full_l_per_100km * load_factor
        )
        
        # Apply speed efficiency multiplier (interpolate between speed brackets)
        speed_multiplier = self._get_speed_efficiency_multiplier(speed_kmh)
        
        return base_consumption * speed_multiplier
    
    def _get_speed_efficiency_multiplier(self, speed_kmh: float) -> float:
        """
        Get fuel efficiency multiplier for given speed using linear interpolation.
        
        Args:
            speed_kmh: Current speed
            
        Returns:
            Efficiency multiplier (1.0 = optimal, >1.0 = worse)
        """
        # Extract speed brackets from config (e.g., "20_kmh" -> 20)
        speed_brackets = sorted([
            int(k.split('_')[0]) 
            for k in self.truck_type.fuel_efficiency_by_speed.keys()
        ])
        
        # Clamp speed to valid range
        speed_kmh = max(speed_brackets[0], min(speed_brackets[-1], speed_kmh))
        
        # Find surrounding brackets for interpolation
        lower_speed = speed_brackets[0]
        upper_speed = speed_brackets[-1]
        
        for i in range(len(speed_brackets) - 1):
            if speed_brackets[i] <= speed_kmh <= speed_brackets[i + 1]:
                lower_speed = speed_brackets[i]
                upper_speed = speed_brackets[i + 1]
                break
        
        # Get multipliers for surrounding speeds
        lower_key = f"{lower_speed}_kmh"
        upper_key = f"{upper_speed}_kmh"
        lower_mult = self.truck_type.fuel_efficiency_by_speed[lower_key]
        upper_mult = self.truck_type.fuel_efficiency_by_speed[upper_key]
        
        # Linear interpolation
        if upper_speed == lower_speed:
            return lower_mult
        
        t = (speed_kmh - lower_speed) / (upper_speed - lower_speed)
        return lower_mult + t * (upper_mult - lower_mult)
    
    def consume_fuel(self, distance_km: float, speed_kmh: float, efficiency_multiplier: float = 1.0) -> float:
        """
        Consume fuel for given distance and speed.
        
        Args:
            distance_km: Distance traveled
            speed_kmh: Average speed during travel
            efficiency_multiplier: Multiplier for driver efficiency (1.0 = normal)
            
        Returns:
            Fuel consumed in liters
        """
        consumption_rate = self.get_fuel_consumption_rate(speed_kmh)
        # Apply efficiency multiplier (e.g., 1.1 = 10% more fuel used)
        consumption_rate *= efficiency_multiplier
        
        fuel_consumed = (consumption_rate / 100.0) * distance_km
        
        self.current_fuel_liters -= fuel_consumed
        self.total_fuel_consumed_liters += fuel_consumed
        self.total_distance_km += distance_km
        
        # Clamp fuel to non-negative
        self.current_fuel_liters = max(0.0, self.current_fuel_liters)
        
        return fuel_consumed
    
    def refuel(self, amount_liters: Optional[float] = None):
        """
        Refuel the truck.
        
        Args:
            amount_liters: Amount to refuel (None = fill tank)
        """
        if amount_liters is None:
            self.current_fuel_liters = self.truck_type.fuel_tank_liters
        else:
            self.current_fuel_liters = min(
                self.truck_type.fuel_tank_liters,
                self.current_fuel_liters + amount_liters
            )
    
    def get_fuel_percentage(self) -> float:
        """Get current fuel level as percentage of tank capacity."""
        return (self.current_fuel_liters / self.truck_type.fuel_tank_liters) * 100.0
    
    def is_low_fuel(self, threshold: float = 20.0) -> bool:
        """Check if fuel is below threshold percentage."""
        return self.get_fuel_percentage() < threshold
    
    def load_cargo(self, batches: List) -> bool:
        """
        Load cargo batches onto truck.
        
        Args:
            batches: List of OrangeBatch objects
            
        Returns:
            True if loaded successfully, False if exceeds capacity
        """
        total_weight = sum(batch.quantity for batch in batches)
        
        if self.current_load_kg + total_weight > self.truck_type.capacity_kg:
            return False
        
        self.cargo_batches.extend(batches)
        self.current_load_kg += total_weight
        return True
    
    def unload_cargo(self) -> List:
        """
        Unload all cargo from truck.
        
        Returns:
            List of OrangeBatch objects that were unloaded
        """
        unloaded = self.cargo_batches.copy()
        self.cargo_batches.clear()
        self.current_load_kg = 0.0
        return unloaded
    
    def get_loading_time_minutes(self) -> float:
        """Calculate time required to load current cargo."""
        tons = self.current_load_kg / 1000.0
        return tons * self.truck_type.loading_time_per_ton_minutes
    
    def get_unloading_time_minutes(self) -> float:
        """Calculate time required to unload current cargo."""
        tons = self.current_load_kg / 1000.0
        return tons * self.truck_type.unloading_time_per_ton_minutes
    
    def get_state(self) -> dict:
        """
        Get current truck state for snapshot logging.
        
        Returns:
            Dictionary with truck state data for InfluxDB
        """
        return {
            'truck_id': self.truck_id,
            'warehouse_id': self.warehouse_id,
            'truck_type': self.truck_type.name,
            'status': self.status,
            'location': {
                'lat': self.current_location[0],
                'lon': self.current_location[1]
            },
            'current_load_kg': round(self.current_load_kg, 2),
            'load_factor': round(self.get_load_factor(), 3),
            'current_fuel_liters': round(self.current_fuel_liters, 2),
            'fuel_percent': round(self.get_fuel_percentage(), 1),
            'speed_kmh': round(self.current_speed_kmh, 1),  # Current speed for dashboard
            'total_distance_km': round(self.total_distance_km, 2),
            'total_fuel_consumed_liters': round(self.total_fuel_consumed_liters, 2),
            'total_deliveries': self.total_deliveries,
            'assigned_order_id': self.assigned_order_id if self.assigned_order_id else '',
            'route_progress': self.route_progress,
            'cargo_batches_count': len(self.cargo_batches)
        }
    
    def __repr__(self) -> str:
        return (f"Truck(id={self.truck_id}, type={self.truck_type.name}, "
                f"status={self.status}, load={self.current_load_kg:.0f}kg, "
                f"fuel={self.get_fuel_percentage():.1f}%)")
