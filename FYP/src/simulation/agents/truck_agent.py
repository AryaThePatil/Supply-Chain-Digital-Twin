"""TruckAgent - Autonomous agent for truck operations."""

import logging
from typing import Optional, List, Dict, Tuple
from ..entities.truck import Truck
from ..entities.orange_batch import OrangeBatch
from ..entities.driver import Driver
from ..network.router import Router
from ..network.road_network import RoadNetwork
from ..sensors.sensor import GPSSensor, TemperatureSensor, StockSensor

# Module-level logger
logger = logging.getLogger(__name__)


class TruckAgent:
    """
    Autonomous agent managing truck operations.
    
    Responsibilities:
    - Move along route consuming fuel
    - Monitor cargo condition (temperature, RSL)
    - Dynamic rerouting based on traffic/accidents
    - Fuel management and low fuel warnings
    - Publish telemetry data
    """
    
    def __init__(self, truck: Truck, road_network: RoadNetwork, 
                 router: Router, config: Dict):
        """
        Initialize TruckAgent.
        
        Args:
            truck: Truck entity to control
            road_network: Road network for navigation
            router: Router for pathfinding
            config: Configuration dict
        """
        self.truck = truck
        self.road_network = road_network
        self.router = router
        self.config = config  # Store for refueling params
        
        # Configuration
        routing_config = config.get('routing', {})
        cargo_config = config.get('cargo', {})
        logging_config = config.get('logging', {})
        sensor_config = config.get('sensors', {})
        
        # IoT Sensors (New Layer)
        self.sensors = {
            'gps': GPSSensor(
                f"gps_{truck.truck_id}", 
                {'noise_std_dev': sensor_config.get('gps_noise', 0.00005)}
            ),
            'temp': TemperatureSensor(
                f"temp_{truck.truck_id}",
                {'noise_std_dev': sensor_config.get('temp_noise', 0.5)}
            ),
            'stock': StockSensor(
                f"stock_{truck.truck_id}",
                {'noise_std_dev': sensor_config.get('stock_noise_kg', 2.0)}
            )
        }
        
        self.reroute_interval = routing_config.get('recalculation_interval_minutes', 5)  # minutes
        self.reroute_threshold = routing_config.get('recalculation_threshold', 0.10)  # 10% improvement
        self.low_fuel_threshold = 20.0  # 20% fuel remaining triggers warning
        # Telemetry now syncs with timestep (set dynamically in update())
        
        # State tracking
        self.last_reroute_check = 0
        self.last_telemetry_time = 0
        self.current_speed_kmh = 0.0
        
        # Events to publish
        self.events_to_publish = []
        
        # Track ambient temperature for telemetry (canvas trucks use ambient)
        self.last_ambient_temperature = 25.0
        
        # Driver Model
        driver_config = config.get('driver_model', {})
        self.driver = Driver(f"DRV_{truck.truck_id}", driver_config)
        
        # Refueling state
        self.is_refueling = False
        self.refuel_remaining_time = 0.0
        
        # Loading/Unloading state (new)
        self.current_task_remaining_min = 0.0
        
        # Weather tracking (initialized before first update)
        self.current_weather = 'clear'  # Default until first weather update from engine

        
    def update(self, current_time: float, time_step: float, ambient_temperature: float = 25.0, ambient_humidity: float = 50.0, current_weather: str = 'clear') -> List[Dict]:
        """
        Update truck state for one time step.
        
        Args:
            current_time: Current simulation time
            time_step: Time step duration
            ambient_temperature: Current ambient temperature
            ambient_humidity: Current relative humidity (%)
            current_weather: Current weather state (clear, rain, etc.)
            
        Returns:
            List of events generated
        """
        # Clear events from previous step
        self.events_to_publish = []
        
        # Store current weather for accident checks
        self.current_weather = current_weather
        

        # Handle refueling (blocks all other actions)
        if self.is_refueling:
            self.refuel_remaining_time -= time_step
            if self.refuel_remaining_time <= 0:
                self.is_refueling = False
                self.truck.refuel()
                # Log actual refuel completion with correct duration
                self.events_to_publish.append({
                    'type': 'refueled',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'fuel_added_liters': self.truck.truck_type.fuel_tank_liters
                })
            # Don't check fuel while refueling - only after completion
            return self.events_to_publish
        
        # If truck is idle, nothing to update
        if self.truck.status == 'idle':
            return self.events_to_publish
        
        # If loading, handle loading time
        if self.truck.status == 'loading':
            self.current_task_remaining_min -= time_step
            if self.current_task_remaining_min <= 0:
                # Loading finished -> Depart
                self.truck.status = "in_transit"
                self.events_to_publish.append({
                    'type': 'loading_complete',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'order_id': self.truck.assigned_order_id
                })
                
                # Now trigger departure event (moved from assign_delivery)
                segments = self.truck.current_route.get('segment_objects', []) if self.truck.current_route else []
                self.events_to_publish.append({
                    'type': 'truck_departure',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'order_id': self.truck.assigned_order_id,
                    'destination': self.truck.destination_node,
                    'cargo_kg': self.truck.current_load_kg,
                    'route_segments': len(segments)
                })
            return self.events_to_publish

        # Handle Unloading Delay
        if self.truck.status == "unloading":
            self.current_task_remaining_min -= time_step
            if self.current_task_remaining_min <= 0:
                # Unloading finished
                self.truck.status = "unloading_complete"
                self.events_to_publish.append({
                    'type': 'unloading_complete',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'order_id': self.truck.assigned_order_id
                })
            return self.events_to_publish
            
        # Update driver state
        is_moving = self.truck.status == "in_transit" and not self.is_refueling
        self.driver.update(time_step, is_moving)
        
        # Check for driver sleep (blocks all movement)
        if self.driver.is_sleeping:
            return self.events_to_publish
        
        if self.truck.status == "in_transit":
            # Check for driver break
            if self.driver.is_on_break:
                # Truck stops during break
                return self.events_to_publish

            self._update_movement(current_time, time_step)
            self._update_cargo(current_time, time_step, ambient_temperature, ambient_humidity)
            self._check_rerouting(current_time)
            self._check_fuel_level(current_time)
            
            # Publish telemetry every timestep (synchronized with snapshots)
            if current_time - self.last_telemetry_time >= time_step:
                self._publish_telemetry(current_time)
                self.last_telemetry_time = current_time
        
        return self.events_to_publish
    
    def _update_movement(self, current_time: float, time_step: float):
        """
        Move truck along route, consuming fuel.
        
        Tracks position within current segment realistically.
        
        Args:
            current_time: Current simulation time in minutes
            time_step: Time step duration in minutes
        """
        # Check if route exists and has segment_objects
        if not self.truck.current_route:
            self._handle_arrival(current_time)
            return
        
        # Get segment objects from route
        segments = self.truck.current_route.get('segment_objects', [])
        if not segments or self.truck.route_progress >= len(segments):
            # Reached destination
            self._handle_arrival(current_time)
            return
        
        # Get current road segment
        segment = segments[self.truck.route_progress]
        
        # Check if segment is blocked
        if segment.is_blocked:
            # Trigger immediate reroute
            self._perform_reroute(current_time, reason="blocked_segment")
            return
        
        # Calculate speed (limited by truck max speed, segment speed, and driver factors)
        max_speed = min(
            self.truck.truck_type.max_speed_kmh,
            segment.current_speed_kmh
        )
        
        # Apply driver speed multiplier (skill/fatigue)
        self.current_speed_kmh = max_speed * self.driver.get_speed_multiplier()
        
        # Sync speed to truck entity for snapshot logging
        self.truck.current_speed_kmh = self.current_speed_kmh
        
        # Calculate distance that can be traveled in this time step
        distance_available_km = (self.current_speed_kmh / 60.0) * time_step
        
        # Calculate remaining distance in current segment
        segment_remaining_km = segment.length_km - self.truck.segment_distance_traveled
        
        if distance_available_km >= segment_remaining_km:
            # Will complete current segment and possibly more
            distance_to_travel = segment_remaining_km
            
            # Consume fuel for this segment (adjusted by driver efficiency)
            fuel_mult = self.driver.get_fuel_efficiency_multiplier()
            self.truck.consume_fuel(distance_to_travel, self.current_speed_kmh, efficiency_multiplier=fuel_mult)
            
            # Update location to end of segment
            self.truck.current_location = segment.end_location
            self.truck.current_node = segment.end_node
            
            # Move to next segment
            self.truck.route_progress += 1
            self.truck.segment_distance_traveled = 0.0
            
            # Check if reached destination
            segments = self.truck.current_route.get('segment_objects', [])
            if self.truck.route_progress >= len(segments):
                self._handle_arrival(current_time)
                return

            # Check fuel for next segment BEFORE processing it
            next_segment = segments[self.truck.route_progress]
            # Estimate fuel needed (conservative estimate using full load consumption + margin)
            max_consumption = self.truck.truck_type.fuel_consumption_full_l_per_100km
            
            # Get refueling safety margin from config
            refuel_config = self.config.get('truck_types', {}).get('small', {}).get('refueling', {})
            safety_margin_pct = refuel_config.get('safety_margin_percent', 20) / 100.0
            refuel_duration = refuel_config.get('default_duration_minutes', 15.0)
            
            estimated_needed_liters = (next_segment.length_km / 100.0) * max_consumption * (1 + safety_margin_pct)
            
            if self.truck.current_fuel_liters < estimated_needed_liters:
                # Force refuel
                self.is_refueling = True
                self.refuel_remaining_time = refuel_duration
                self.events_to_publish.append({
                    'type': 'refueling_started',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'duration_minutes': refuel_duration,
                    'reason': 'insufficient_fuel_for_segment',
                    'fuel_remaining': self.truck.current_fuel_liters,
                    'segment_length_km': next_segment.length_km
                })
                return # Stop movement to refuel

            # Continue moving if there's remaining distance and time
            remaining_distance = distance_available_km - distance_to_travel
            remaining_time = (remaining_distance / self.current_speed_kmh) * 60.0 if self.current_speed_kmh > 0 else 0
            
            if remaining_time > 0.01:  # More than 0.01 minutes remaining
                self._update_movement(current_time, remaining_time)
        else:
            # Will not complete current segment in this time step
            fuel_mult = self.driver.get_fuel_efficiency_multiplier()
            self.truck.consume_fuel(distance_available_km, self.current_speed_kmh, efficiency_multiplier=fuel_mult)
            self.truck.segment_distance_traveled += distance_available_km
            
            # NEW: Use segment's curved interpolation method
            # Automatically uses curved geometry if available, falls back to linear
            current_lat, current_lon = segment.interpolate_position(
                self.truck.segment_distance_traveled
            )
            
            self.truck.current_location = (current_lat, current_lon)
            
            # Check for truck accident (NEW - Phase 1 Fix)
            if self._check_truck_accident(current_time, segment):
                return  # Truck destroyed, stop processing
    
    def _update_cargo(self, current_time: float, time_step: float, ambient_temperature: float, ambient_humidity: float):
        """Update cargo quality (RSL) for canvas trucks."""
        if not self.truck.cargo_batches:
            return
        
        # Store ambient temperature for telemetry
        self.last_ambient_temperature = ambient_temperature
        
        # All trucks are canvas - cargo directly exposed to ambient conditions
        effective_temp = ambient_temperature
        effective_humidity = ambient_humidity
        
        # Update RSL for all batches
        for batch in self.truck.cargo_batches:
            batch.update_rsl(effective_temp, effective_humidity, current_time)
            
            # Check for spoilage
            if batch.is_spoiled():
                self.events_to_publish.append({
                    'type': 'cargo_spoiled',
                    'truck_id': self.truck.truck_id,
                    'batch_id': batch.batch_id,
                    'time': current_time
                })
    
    def _check_rerouting(self, current_time: float):
        """
        Periodically check if rerouting would improve delivery time.
        
        Args:
            current_time: Current simulation time in minutes
        """
        # Only check at specified intervals
        if current_time - self.last_reroute_check < self.reroute_interval:
            return
        
        self.last_reroute_check = current_time
        
        # Calculate remaining route cost
        if not self.truck.current_route or not self.truck.destination_node:
            return
        
        segments = self.truck.current_route.get('segment_objects', [])
        if not segments:
            return
        
        current_route_cost = sum(
            seg.get_travel_time_minutes() 
            for seg in segments[self.truck.route_progress:]
        )
        
        # Find alternative route from current position
        try:
            # Convert TruckType to dict for router
            truck_type_dict = {
                'capacity_kg': self.truck.truck_type.capacity_kg,
                'fuel_consumption_empty_l_per_100km': self.truck.truck_type.fuel_consumption_empty_l_per_100km,
                'fuel_consumption_full_l_per_100km': self.truck.truck_type.fuel_consumption_full_l_per_100km,
                'fuel_efficiency_by_speed': self.truck.truck_type.fuel_efficiency_by_speed
            }
            
            new_route = self.router.find_path(
                self.truck.current_node,
                self.truck.destination_node,
                truck_type_config=truck_type_dict,
                load_fraction=self.truck.get_load_factor(),
                avoid_blocked=True,
                current_time=current_time
            )
            
            if new_route:
                new_segments = new_route.get('segment_objects', [])
                new_route_cost = sum(seg.get_travel_time_minutes() for seg in new_segments)
                
                # Switch if new route is significantly better
                # FIX: Check for zero to prevent division by zero
                if current_route_cost > 0:
                    improvement = (current_route_cost - new_route_cost) / current_route_cost
                    if improvement > self.reroute_threshold:
                        self._perform_reroute(current_time, reason="better_route", 
                                             improvement=improvement)
        except (AttributeError, KeyError, ValueError, IndexError) as e:
            # Routing failed due to missing data or invalid state - continue with current route
            # These are expected exceptions from routing logic, not bugs
            pass
        except Exception as e:
            # Unexpected exception - log it for debugging
            logger.warning(f"Unexpected error in rerouting check for truck {self.truck.truck_id}: {type(e).__name__}: {e}")
            # Continue with current route
    
    def _perform_reroute(self, current_time: float, reason: str, improvement: float = 0.0):
        """
        Execute rerouting to avoid blockage or improve time.
        
        Args:
            current_time: Current simulation time
            reason: Reason for rerouting
            improvement: Percentage improvement (if applicable)
        """
        if not self.truck.destination_node:
            return
        
        try:
            # Convert TruckType to dict for router
            truck_type_dict = {
                'capacity_kg': self.truck.truck_type.capacity_kg,
                'fuel_consumption_empty_l_per_100km': self.truck.truck_type.fuel_consumption_empty_l_per_100km,
                'fuel_consumption_full_l_per_100km': self.truck.truck_type.fuel_consumption_full_l_per_100km,
                'fuel_efficiency_by_speed': self.truck.truck_type.fuel_efficiency_by_speed
            }
            
            new_route = self.router.find_path(
                self.truck.current_node,
                self.truck.destination_node,
                truck_type_config=truck_type_dict,
                load_fraction=self.truck.get_load_factor(),
                avoid_blocked=True,
                current_time=current_time
            )
            
            if new_route:
                old_segments = self.truck.current_route.get('segment_objects', []) if self.truck.current_route else []
                old_route_length = len(old_segments) - self.truck.route_progress
                new_segments = new_route.get('segment_objects', [])
                
                self.truck.current_route = new_route
                self.truck.route_progress = 0
                self.truck.segment_distance_traveled = 0.0
                
                self.events_to_publish.append({
                    'type': 'route_changed',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'reason': reason,
                    'improvement_percent': improvement * 100,
                    'old_segments': old_route_length,
                    'new_segments': len(new_segments)
                })
        except Exception as e:
            # Rerouting failed
            self.events_to_publish.append({
                'type': 'reroute_failed',
                'truck_id': self.truck.truck_id,
                'time': current_time,
                'reason': str(e)
            })
    
    def _check_fuel_level(self, current_time: float):
        """
        Check fuel level and handle refueling with realistic time delays.
        
        Realistic refueling model:
        - Calculate refuel time based on tank capacity and rate (40 L/min)
        - Truck remains stationary during refueling
        - Logs refuel start and completion events
        
        Args:
            current_time: Current simulation time
        """
        # Check if fuel depleted - need to refuel
        if self.truck.current_fuel_liters <= 0 and not self.is_refueling:
            # Calculate refueling time based on tank capacity
            refuel_rate = self.config.get('refueling', {}).get('rate_liters_per_minute', 40.0)
            setup_time = self.config.get('refueling', {}).get('setup_time_minutes', 0.5)
            
            liters_needed = self.truck.truck_type.fuel_tank_liters
            refuel_time = (liters_needed / refuel_rate) + setup_time
            
            # Enter refuel state
            self.is_refueling = True
            self.refuel_remaining_time = refuel_time
            
            # Log refuel start
            self.events_to_publish.append({
                'type': 'truck_refuel_start',
                'truck_id': self.truck.truck_id,
                'time': current_time,
                'location': self.truck.current_location,
                'current_fuel_liters': self.truck.current_fuel_liters,
                'liters_to_add': liters_needed,
                'estimated_duration_minutes': refuel_time,
                'reason': 'fuel_depleted'
            })
            
            logger.info(f"[REFUEL] Truck {self.truck.truck_id} refueling at t={current_time:.1f}min "
                       f"(+{liters_needed:.1f}L, {refuel_time:.1f}min)")
            return
        
        # Warn if fuel low but not depleted
        if not self.is_refueling:
            fuel_pct = self.truck.get_fuel_percentage()
            low_fuel_threshold = self.config.get('refueling', {}).get('low_fuel_threshold_percent', 20.0)
            
            if fuel_pct < low_fuel_threshold and fuel_pct > 0:
                self.events_to_publish.append({
                    'type': 'truck_low_fuel_warning',
                    'truck_id': self.truck.truck_id,
                    'time': current_time,
                    'fuel_percentage': fuel_pct,
                    'fuel_liters': self.truck.current_fuel_liters
                })
    
    def _check_truck_accident(self, current_time: float, segment) -> bool:
        """
        Check if truck is involved in an accident (total loss).
        
        Accident probability based on:
        - Driver fatigue
        - Weather conditions
        - Traffic density
        - Road type
        
        Args:
            current_time: Current simulation time
            segment: Current road segment
            
        Returns:
            True if truck destroyed in accident, False otherwise
        """
        import random
        
        # Base accident rate per km (very low)
        base_rate = 0.00001  # 1 in 100,000 km
        
        # Fatigue multiplier
        fatigue_hours = self.driver.accumulated_fatigue / 60.0
        if fatigue_hours > 10:
            fatigue_mult = 4.0
        elif fatigue_hours > 8:
            fatigue_mult = 2.5
        elif fatigue_hours > 6:
            fatigue_mult = 1.5
        else:
            fatigue_mult = 1.0
        
        # Weather multiplier (validate and use actual current weather)
        VALID_WEATHER_MULTIPLIERS = {
            'clear': 1.0,
            'light_rain': 1.5,   # 50% more dangerous
            'rain': 2.0,          # 2x more dangerous
            'heavy_rain': 3.0,    # 3x more dangerous!
            'fog': 2.5            # 2.5x more dangerous
        }
        
        weather_mult = VALID_WEATHER_MULTIPLIERS.get(self.current_weather, None)
        if weather_mult is None:
            logger.warning(f"[WEATHER] Unknown weather state '{self.current_weather}' for truck {self.truck.truck_id} - defaulting to 'clear' (1.0x)")
            weather_mult = 1.0
        

        # Speed multiplier (higher speed = higher risk)
        speed_mult = 1.0 + (max(0, self.current_speed_kmh - 80) / 100.0)
        
        # Road type multiplier
        road_mult = {
            'primary': 0.8,
            'secondary': 1.0,
            'tertiary': 1.2,
            'residential': 1.1,
            'unpaved': 2.0,
            'dirt': 3.0
        }.get(getattr(segment, 'road_type', 'secondary'), 1.0)
        
        # Calculate total probability
        accident_prob = base_rate * fatigue_mult * weather_mult * speed_mult * road_mult
        
        # Check if accident occurs
        if random.random() < accident_prob:
            self._handle_truck_destruction(current_time, segment)
            return True
        
        return False
    
    def _handle_truck_destruction(self, current_time: float, segment):
        """
        Handle complete truck destruction from accident.
        
        Total loss scenario:
        - Truck permanently destroyed
        - All cargo lost
        - Order marked as failed
        - Retailer must reorder
        - Truck removed from warehouse fleet
        
        Args:
            current_time: Current simulation time
            segment: Road segment where accident occurred
        """
        # Mark truck as destroyed
        self.truck.status = 'destroyed'
        
        # Log catastrophic accident event
        self.events_to_publish.append({
            'type': 'truck_accident_total_loss',
            'truck_id': self.truck.truck_id,
            'time': current_time,
            'location': self.truck.current_location,
            'segment_id': getattr(segment, 'segment_id', 'unknown'),
            'cargo_lost_kg': self.truck.current_cargo_kg,
            'batches_destroyed': len(self.truck.cargo_batches),
            'assigned_order_id': getattr(self.truck, 'assigned_order_id', None),
            'driver_fatigue_hours': self.driver.accumulated_fatigue / 60.0,
            'speed_kmh': self.current_speed_kmh
        })
        
        logger.critical(f"[ACCIDENT] Truck {self.truck.truck_id} DESTROYED at t={current_time:.1f}min - "
                       f"Total loss! Cargo: {self.truck.current_cargo_kg:.1f}kg lost")
        
        # Cargo is completely destroyed - will trigger reorder from retailer/warehouse
        self.truck.cargo_batches = []
        self.truck.current_cargo_kg = 0.0
    
    def _handle_arrival(self, current_time: float):
        """
        Handle truck arrival at destination (retailer).
        
        The truck has arrived at the retailer. The warehouse will handle
        the actual delivery when it detects the truck has arrived.
        
        Args:
            current_time: Current simulation time
        """
        self.truck.status = "arrived"
        
        self.events_to_publish.append({
            'type': 'truck_arrival',
            'truck_id': self.truck.truck_id,
            'time': current_time,
            'destination': self.truck.destination_node,
            'cargo_kg': self.truck.current_load_kg,
            'fuel_remaining': self.truck.current_fuel_liters,
            'order_id': self.truck.assigned_order_id
        })
    
    def _publish_telemetry(self, current_time: float):
        """
        Publish telemetry data for active truck.
        
        Args:
            current_time: Current simulation time
        """
        # Calculate average RSL of cargo
        avg_rsl = 0.0
        if self.truck.cargo_batches:
            avg_rsl = sum(b.current_rsl for b in self.truck.cargo_batches) / len(self.truck.cargo_batches)
        
        # IoT Layer: Read from sensors
        gps_location = self.sensors['gps'].read(self.truck.current_location, current_time)
        # If GPS fails, we might publish None or old location, but for visualizer 
        # we might want to just skip or keep last known. 
        # For now, if None, we just don't update location (use actual as fallback or hold last?)
        # Let's fallback to actual with a "FAULT" flag if needed, but for now assuming it works mostly.
        if gps_location is None:
            gps_location = self.truck.current_location # Fallback
            
        # Canvas trucks: use ambient temperature for telemetry
        temp_reading = self.sensors['temp'].read(self.last_ambient_temperature, current_time)
        if temp_reading is None:
            temp_reading = self.last_ambient_temperature
            
        cargo_reading = self.sensors['stock'].read(self.truck.current_load_kg, current_time)
        
        self.events_to_publish.append({
            'type': 'telemetry',
            'truck_id': self.truck.truck_id,
            'time': current_time,
            'location': gps_location,  # Noisy location
            'location_true': self.truck.current_location, # Ground Truth (for debugging/comparison)
            'speed_kmh': self.current_speed_kmh,
            'fuel_liters': self.truck.current_fuel_liters,
            'fuel_percent': self.truck.get_fuel_percentage(),
            'cargo_kg': cargo_reading, # Noisy stock
            'cargo_rsl': avg_rsl,
            'temperature_celsius': temp_reading, # Noisy ambient temp
            'temperature_true': self.last_ambient_temperature, # Ground Truth (ambient)
            'driver_fatigue': self.driver.fatigue_level,
            'driver_status': "Break" if self.driver.is_on_break else "Driving",
            'status': self.truck.status,
            'source': 'iot' # Tag as IoT data
        })
    
    def assign_delivery(self, destination_node: int, order_id: str, 
                       batches: List[OrangeBatch], current_time: float) -> bool:
        """
        Assign a delivery to this truck.
        
        Args:
            destination_node: Destination node ID
            order_id: Order ID
            batches: List of OrangeBatch objects to deliver
            current_time: Current simulation time
            
        Returns:
            True if assignment successful, False otherwise
        """
        # Check capacity
        if not self.truck.load_cargo(batches):
            logger.warning(f"[ASSIGNMENT FAILED] Truck {self.truck.truck_id}: Cargo exceeds capacity "
                          f"(Need: {sum(b.quantity for b in batches):.1f}kg, "
                          f"Available: {self.truck.truck_type.capacity_kg - self.truck.current_load_kg:.1f}kg)")
            return False
        
        # Calculate route
        try:
            # Convert TruckType to dict for router
            truck_type_dict = {
                'capacity_kg': self.truck.truck_type.capacity_kg,
                'fuel_consumption_empty_l_per_100km': self.truck.truck_type.fuel_consumption_empty_l_per_100km,
                'fuel_consumption_full_l_per_100km': self.truck.truck_type.fuel_consumption_full_l_per_100km,
                'fuel_efficiency_by_speed': self.truck.truck_type.fuel_efficiency_by_speed
            }
            
            route = self.router.find_path(
                self.truck.current_node,
                destination_node,
                truck_type_config=truck_type_dict,
                load_fraction=self.truck.get_load_factor(),
                avoid_blocked=True,
                current_time=current_time
            )
            
            if not route:
                # Unload cargo if routing failed
                self.truck.unload_cargo()
                logger.warning(f"[ASSIGNMENT FAILED] Truck {self.truck.truck_id}: No route found from node "
                              f"{self.truck.current_node} to {destination_node} (Order: {order_id})")
                return False
            
            # Assign route and destination
            self.truck.current_route = route
            self.truck.route_progress = 0
            self.truck.segment_distance_traveled = 0.0
            self.truck.destination_node = destination_node
            self.truck.assigned_order_id = order_id
            
            # Start Loading Process
            load_kg_tons = self.truck.current_load_kg / 1000.0
            load_rate = self.truck.truck_type.loading_time_per_ton_minutes
            loading_time = max(10.0, load_kg_tons * load_rate) # Minimum 10 mins loading
            
            self.truck.status = "loading"
            self.current_task_remaining_min = loading_time
            
            self.events_to_publish.append({
                'type': 'loading_started',
                'truck_id': self.truck.truck_id,
                'time': current_time,
                'order_id': order_id,
                'duration_minutes': loading_time,
                'cargo_kg': self.truck.current_load_kg
            })
            
            logger.info(f"[LOADING] Truck {self.truck.truck_id} loading {self.truck.current_load_kg:.1f}kg "
                       f"for order {order_id} to node {destination_node} (Duration: {loading_time:.1f}min)")
            
            # Note: Removal of immediate 'truck_departure' event. 
            # It will now be fired when loading completes.
            

            
            return True
            
        except Exception as e:
            # Routing failed, unload cargo
            self.truck.unload_cargo()
            logger.error(f"[ASSIGNMENT FAILED] Truck {self.truck.truck_id}: Exception during assignment - {type(e).__name__}: {str(e)} "
                        f"(Order: {order_id}, Destination: {destination_node})")
            return False
    
    def start_unloading(self, current_time: float):
        """
        Transition truck to unloading state.
        
        Args:
            current_time: Current simulation time
        """
        if self.truck.status != "arrived":
            return
            
        load_kg_tons = self.truck.current_load_kg / 1000.0
        unload_rate = self.truck.truck_type.unloading_time_per_ton_minutes
        unloading_time = max(10.0, load_kg_tons * unload_rate) # Minimum 10 mins unloading
        
        self.truck.status = "unloading"
        self.current_task_remaining_min = unloading_time
        
        event = {
            'type': 'unloading_started',
            'truck_id': self.truck.truck_id,
            'time': current_time,
            'order_id': self.truck.assigned_order_id,
            'duration_minutes': unloading_time
        }
        self.events_to_publish.append(event)
        return event
    
    def get_state(self) -> Dict:
        """
        Get current truck state for snapshot logging.
        
        Returns:
            Dictionary with truck state including GPS, sensors, cargo data
        """
        # Get sensor readings
        gps_data = self.sensors['gps'].read(self.truck.current_location, current_time) if 'gps' in self.sensors else {'lat': 0, 'lon': 0}
        if gps_data is None:
            gps_data = {'lat': self.truck.current_location[0], 'lon': self.truck.current_location[1]}
            
        temp_data = self.sensors['temp'].read(self.last_ambient_temperature, current_time) if 'temp' in self.sensors else 25.0
        if temp_data is None:
            temp_data = self.last_ambient_temperature
        
        return {
            'truck_id': self.truck.truck_id,
            'warehouse_id': self.truck.warehouse_id,
            'truck_type': self.truck.truck_type.name,
            'status': self.truck.status,
            'location': gps_data if isinstance(gps_data, dict) else {'lat': gps_data[0] if isinstance(gps_data, tuple) else 0, 'lon': gps_data[1] if isinstance(gps_data, tuple) else 0},
            'current_node': self.truck.current_node,
            'destination_node': self.truck.destination_node,
            'fuel_level_percent': round((self.truck.current_fuel_liters / self.truck.truck_type.fuel_tank_liters) * 100, 2) if self.truck.truck_type.fuel_tank_liters > 0 else 0,
            'current_load_kg': round(self.truck.current_load_kg, 2),
            'capacity_kg': self.truck.truck_type.capacity_kg,
            'load_percent': round((self.truck.current_load_kg / self.truck.truck_type.capacity_kg) * 100, 2) if self.truck.truck_type.capacity_kg > 0 else 0,
            'cargo_temperature': temp_data if isinstance(temp_data, (int, float)) else 25.0,
            'assigned_order_id': self.truck.assigned_order_id,
            'total_km_driven': round(self.truck.total_km_driven, 2) if hasattr(self.truck, 'total_km_driven') else 0
        }
    
    def __repr__(self) -> str:
        return f"TruckAgent({self.truck})"
