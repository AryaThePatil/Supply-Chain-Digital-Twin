"""
Time-stepped simulation engine for Digital Twin supply chain.

This module implements a hybrid time-stepped and event-driven simulation
architecture that replaces the previous SimPy-based approach.
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import random
import os
import logging

from .events import EventQueue, AccidentStartEvent, AccidentEndEvent
from .network import RoadNetwork, Router, TrafficModel
from .models.weather_model import WeatherModel
from .models.disruption_model import DisruptionModel
try:
    from data.mqtt_client import MQTTClientWrapper
    from data.config_loader import ConfigLoader
except ImportError:
    # Fallback for when running as script
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from data.mqtt_client import MQTTClientWrapper
    from data.config_loader import ConfigLoader

# InfluxDB for direct writes
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Module-level logger
logger = logging.getLogger(__name__)


class SimulationEngine:
    """
    Main simulation engine that orchestrates the supply chain digital twin.
    
    Uses a hybrid approach:
    - Time-stepped updates (default 1 minute intervals) for continuous processes
    - Event queue for discrete occurrences (orders, deliveries, accidents)
    """
    
    def __init__(self, config: Dict[str, Any], duration_days: Optional[int] = None,
                 time_step_minutes: Optional[int] = None, random_seed: Optional[int] = None,
                 speed_multiplier: Optional[float] = None, start_date: Optional[str] = None):
        """
        Initialize the simulation engine.
        
        Args:
            config: Configuration dictionary loaded from YAML
            duration_days: Override config duration (1-365 days)
            time_step_minutes: Override config time step (1-60 minutes)
            random_seed: Random seed for reproducibility
            speed_multiplier: Simulation speed (None = max speed)
            start_date: Override config start date (YYYY-MM-DD format)
        """
        self.config = config
        
        # Time management
        self.current_time = 0.0  # minutes since start
        
        # Parse Start Date (for seasonality) - CLI parameter overrides config
        start_date_str = start_date or config.get('simulation', {}).get('start_date', '2023-01-01')
        try:
            self.sim_start_datetime = datetime.strptime(start_date_str, "%Y-%m-%d")
            logger.info(f"Simulation start date: {start_date_str}")
        except ValueError:
            logger.warning(f"Invalid start_date format '{start_date_str}', defaulting to 2023-01-01")
            self.sim_start_datetime = datetime(2023, 1, 1)
            
        self.time_step = time_step_minutes or config.get('simulation', {}).get('time_step_minutes', 1)
        duration_days_config = duration_days or config.get('simulation', {}).get('duration_days', 7)
        self.max_time = duration_days_config * 24 * 60  # convert days to minutes
        
        # Generate unique run ID
        self.run_id = f"sim-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Set random seed for reproducibility
        if random_seed is not None:
            random.seed(random_seed)
            self.random_seed = random_seed
        else:
            self.random_seed = None
        
        # Speed Control
        self.speed_multiplier = speed_multiplier or config.get('simulation', {}).get('speed_multiplier', None)
        
        # Progress logging - track last logged day to avoid missing logs with non-dividing timesteps
        self.last_logged_day = -1
        
        # Components
        self.road_network: Optional[RoadNetwork] = None
        self.router: Optional[Router] = None
        self.traffic_model: Optional[TrafficModel] = None
        self.weather_model: Optional = None  # WeatherModel (Phase 4)
        self.disruption_model: Optional = None  # DisruptionModel (Phase 4)
        self.warehouses: List = []
        self.retailers: List = []
        self.trucks: List = []
        self.event_queue = EventQueue()
        self.active_accidents: List = []  # Track active accidents
        
        # Initialize MQTT client for logging
        mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_client = MQTTClientWrapper(
            broker=mqtt_broker,
            port=mqtt_port,
            client_id=f"sim-engine-{self.run_id}"
        )
        self.mqtt_connected = False
        
        # Initialize InfluxDB client for direct writes
        influx_url = os.getenv('INFLUX_URL', 'http://localhost:8086')
        influx_token = os.getenv('INFLUX_TOKEN', 'my-super-secret-auth-token')
        influx_org = os.getenv('INFLUX_ORG', 'digital-twin')
        influx_bucket = os.getenv('INFLUX_BUCKET', 'supply-chain')
        
        try:
            self.influx_client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
            
            # OPTIMIZATION 3: Async batched writes
            # Use WriteOptions for automatic batching and async I/O
            from influxdb_client.client.write_api import WriteOptions
            write_options = WriteOptions(
                batch_size=100,          # Write in batches of 100 points
                flush_interval=1_000,    # Flush every 1 second
                jitter_interval=0,       # No jitter
                retry_interval=5_000,    # Retry after 5 seconds on failure
                max_retries=3,           # Max 3 retries
                max_retry_delay=30_000,  # Max 30 sec retry delay
                exponential_base=2       # Exponential backoff
            )
            self.influx_write_api = self.influx_client.write_api(write_options=write_options)
            self.influx_bucket = influx_bucket
            self.influx_connected = True
            logger.info(f"InfluxDB connected: {influx_url} (async batched writes enabled)")
        except Exception as e:
            logger.warning(f"InfluxDB connection failed: {e}")
            self.influx_connected = False
        
        # Logging configuration
        # All data flow now syncs with time_step (fully dynamic)
        self.last_snapshot_time = 0
        
        # Heartbeat for simulation liveness detection (real-time based)
        self.heartbeat_interval = config.get('logging', {}).get('heartbeat_interval_seconds', 30)
        self.last_heartbeat_time = 0.0  # Tracks real-time (time.time()), not simulation time
        
        logger.info("SimulationEngine initialized")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"Duration: {duration_days_config} days ({self.max_time} minutes)")
        logger.info(f"Time step: {self.time_step} minute(s)")
        if self.random_seed is not None:
            logger.info(f"Random seed: {self.random_seed}")
    
    def initialize_road_network(self, use_cache: bool = True) -> None:
        """
        Initialize road network from OpenStreetMap.
        
        Args:
            use_cache: If True, use cached OSM data if available
        """
        logger.info("=" * 80)
        logger.info("Initializing Road Network")
        logger.info("=" * 80)
        
        # Create road network
        self.road_network = RoadNetwork(self.config)
        self.road_network.load(use_cache=use_cache)
        
        # Create traffic model
        self.traffic_model = TrafficModel(self.config)
        
        # Initialize traffic state for all segments (one-time at startup)
        logger.info("Initializing traffic state for entire network...")
        self.traffic_model.initialize_network(self.road_network, self.current_time)
        
        # Create router
        self.router = Router(self.road_network, self.config)
        
        # Log network stats
        stats = self.road_network.get_stats()
        logger.info("Network Statistics:")
        logger.info(f"  Nodes: {stats['num_nodes']}")
        logger.info(f"  Segments: {stats['num_segments']}")
        logger.info(f"  Total length: {stats['total_length_km']:.2f} km")
        logger.info(f"  Road types: {stats['road_type_counts']}")
        logger.info("=" * 80)
    
    def initialize_weather_and_disruptions(self) -> None:
        """Initialize weather and disruption models for Phase 4."""
        logger.info("=" * 80)
        logger.info("Initializing Weather & Disruptions")
        logger.info("=" * 80)
        
        # Initialize WeatherModel (Phase 3)
        if 'weather' in self.config:
            self.weather_model = WeatherModel(self.config)
            
            # CRITICAL FIX: Initialize weather with correct season at t=0
            initial_month = self.sim_start_datetime.month
            initial_hour = self.sim_start_datetime.hour + (self.sim_start_datetime.minute / 60.0)
            self.weather_model.update(0, month=initial_month, hour=initial_hour)
            
            logger.info(f"Weather system enabled (Starting: {self.weather_model.current_state}, Month {initial_month})")
        else:
            self.weather_model = None
            logger.info("Weather system disabled")
        
        # Initialize DisruptionModel (Phase 3)
        if 'disruptions' in self.config:
            self.disruption_model = DisruptionModel(self.config)
            logger.info("Disruption system enabled")
        else:
            self.disruption_model = None
            logger.info("Disruption system disabled")
        logger.info("=" * 80)
    
    def schedule_warehouse_restocking(self) -> None:
        """
        Schedule warehouse restocking events based on configuration.
        
        Each warehouse has a restock schedule (day of week, time of day, quantity).
        This method schedules all restock events for the simulation duration.
        """
        from .events.event_types import WarehouseRestockEvent
        
        logger.info("Scheduling warehouse restocking events...")
        
        for warehouse in self.warehouses:
            if not hasattr(warehouse, 'restock_schedule'):
                continue
            
            schedule = warehouse.restock_schedule
            day_of_week = schedule['day_of_week']  # 0=Sunday, 6=Saturday
            time_str = schedule['time_of_day']  # e.g., "06:00"
            quantity_kg = schedule['quantity_kg']
            
            # Parse time
            hour, minute = map(int, time_str.split(':'))
            time_of_day_minutes = hour * 60 + minute
            
            # Schedule restock events for each week in simulation
            current_week = 0
            while True:
                # Calculate restock time
                # Start of week 0 is day 0 (Sunday)
                restock_time = (current_week * 7 + day_of_week) * 24 * 60 + time_of_day_minutes
                
                if restock_time >= self.max_time:
                    break
                
                # Schedule event
                event = WarehouseRestockEvent(
                    time=restock_time,
                    warehouse_id=warehouse.warehouse_id,
                    product_type='oranges',
                    quantity_kg=quantity_kg
                )
                self.event_queue.schedule(event)
                
                current_week += 1
        
        logger.info("Restocking events scheduled")
        
        # OPTIMIZATION 5: Pre-compute common routes
        if self.router and self.warehouses and self.retailers:
            truck_types_config = self.config.get('truck_types', {})
            self.router.precompute_common_routes(
                self.warehouses,
                self.retailers,
                truck_types_config
            )
    
    def run(self):
        """
        Execute the main simulation loop.
        
        Loop structure:
        1. Process scheduled events (if any at current_time)
        2. Update all agents (trucks move, retailers sell, warehouses process)
        3. Update environment (traffic, accidents)
        4. Check for new stochastic events (customer arrivals, accidents)
        5. Log data (events, snapshots, telemetry)
        6. Advance time
        """
        logger.info("=" * 80)
        logger.info(f"Starting simulation: {self.run_id}")
        logger.info("=" * 80)
        
        # Connect to MQTT broker
        try:
            self.mqtt_connected = self.mqtt_client.connect()
        except Exception as e:
            logger.warning("MQTT connection failed. Logging will be disabled.")
            logger.warning("Make sure Docker containers are running (docker-compose up -d)")
            self.mqtt_connected = False
        
        # Log simulation parameters at startup
        self._log_startup_parameters()
        
        # Main simulation loop
        import time
        
        while self.current_time < self.max_time:
            loop_start = time.time()
            
            # 1. Process scheduled events
            if self.event_queue:
                self._process_events()
            
            # 2. Update all agents
            self._update_agents()
            
            # 3. Update environment
            self._update_environment()
            
            # 4. Check for new stochastic events
            self._check_stochastic_events()
            
            # 5. Logging
            self._handle_logging()
            
            # 6. Heartbeat (liveness detection - real-time based)
            self._check_and_write_heartbeat()
            
            # 7. Advance time
            self.current_time += self.time_step
            
            # Progress indicator (every simulated day)
            # Use day boundary check instead of modulo to handle non-dividing timesteps
            current_day = int(self.current_time / (24 * 60))
            if current_day > self.last_logged_day:
                logger.info(f"[Simulation time: Day {current_day}]")
                self.last_logged_day = current_day
            
            # Speed Control: Sleep to maintain target speed
            if self.speed_multiplier:
                # 1 sim minute = 60 sim seconds
                # Targeted real time duration = (time_step_minutes * 60) / speed_multiplier
                target_duration = (self.time_step * 60.0) / self.speed_multiplier
                
                # Calculate how much time we actually spent
                elapsed = time.time() - loop_start
                
                # Sleep if we were too fast
                if elapsed < target_duration:
                    time.sleep(target_duration - elapsed)
        
        # Simulation complete
        logger.info("=" * 80)
        logger.info(f"Simulation complete: {self.run_id}")
        logger.info(f"Total time simulated: {self.current_time / 60 / 24:.2f} days")
        logger.info("=" * 80)
        
        self._cleanup()
    
    def _process_events(self):
        """Process all events scheduled for current time."""
        events = self.event_queue.get_events_at(self.current_time)
        for event in events:
            event.execute(self)
    
    def _update_agents(self):
        """Update all agents' continuous processes."""
        # Calculate time context for agents
        current_dt = self.sim_start_datetime + timedelta(minutes=self.current_time)
        
        # 0=Sunday, 1=Monday... (matching config convention 0=Sunday)
        # Python weekday(): 0=Monday. (0+1)%7 = 1 (Mon). (6+1)%7 = 0 (Sunday).
        day_of_week = (current_dt.weekday() + 1) % 7
        
        month = current_dt.month
        hour = current_dt.hour + (current_dt.minute / 60.0)
        
        weather = self.weather_model.current_state if self.weather_model else "clear"
        
        # Get temperature and humidity from weather model
        if self.weather_model and hasattr(self.weather_model, 'get_temperature'):
            temperature = self.weather_model.get_temperature(month, hour)
            if hasattr(self.weather_model, 'get_humidity'):
                humidity = self.weather_model.get_humidity(month, hour)
            else:
                humidity = self.weather_model.humidity if hasattr(self.weather_model, 'humidity') else 50.0
        else:
            # Fallback to inline defaults if weather model unavailable
            humidity = 50.0  # Default moderate humidity
            temperature = 25.0  # Default comfortable temperature
            # Apply time-of-day variation for realism
            import math
            time_effect = -5.0 * math.cos((hour - 14) * math.pi / 12)
            weather_effect = -2.0 if weather in ['rain', 'light_rain'] else 0.0
            temperature = 25.0 + time_effect + weather_effect
        
        # Retailers: process customers, check inventory
        for retailer in self.retailers:
            if hasattr(retailer, 'update'):
                retailer.update(
                    self.current_time, 
                    self.time_step,
                    day_of_week, 
                    month, 
                    weather, 
                    temperature,
                    humidity,  # Pass humidity for consistency
                    engine=self  # Pass engine so retailers can schedule order events
                )
        
        # Warehouses: process orders, allocate trucks
        for warehouse in self.warehouses:
            if hasattr(warehouse, 'update'):
                events = warehouse.update(
                    self.current_time, 
                    self.time_step, 
                    ambient_temperature=temperature, 
                    ambient_humidity=humidity,
                    current_weather=weather,
                    engine=self
                )
                
                # Log generated events (including telemetry)
                if events:
                    for event in events:
                        if event['type'] == 'telemetry':
                            # Extract truck_id and remove type/truck_id from data
                            t_id = event['truck_id']
                            data = {k: v for k, v in event.items() if k not in ['type', 'truck_id']}
                            self.log_truck_telemetry(t_id, data)
                        else:
                            self.log_event(event['type'], event)
    
    def _update_environment(self):
        """Update environmental conditions (traffic, weather)."""
        # Calculate time context
        current_dt = self.sim_start_datetime + timedelta(minutes=self.current_time)
        month = current_dt.month
        hour = current_dt.hour + (current_dt.minute / 60.0)

        # Update weather state
        if self.weather_model:
            # Capture weather change events
            weather_events = self.weather_model.update(self.current_time, month=month, hour=hour)
            
            # Publish weather events
            for event in weather_events:
                event['month'] = month
                event['hour'] = hour
                if self.mqtt_connected:
                    self.mqtt_client.publish('sim/weather', event)
                
                # Write to InfluxDB for dashboard weather panel
                if self.influx_connected and 'new_state' in event:
                    try:
                        point = Point("weather_transitions") \
                            .tag("run_id", self.run_id) \
                            .tag("from_state", event.get('old_state', 'unknown')) \
                            .tag("to_state", event['new_state']) \
                            .field("state", event['new_state']) \
                            .field("timestamp", float(self.current_time)) \
                            .field("month", month) \
                            .field("hour", hour)
                        self.influx_write_api.write(bucket=self.influx_bucket, record=point)
                        logger.info(f"[WEATHER] Weather transition: {event.get('old_state')} → {event['new_state']}")
                    except Exception as e:
                        logger.warning(f"InfluxDB weather write failed: {e}")
            
            # Update traffic model with current weather
            if self.traffic_model:
                self.traffic_model.set_weather(self.weather_model.current_state)
        
        # Update traffic on road segments (OPTIMIZED: zone-based updates)
        if self.traffic_model and self.road_network:
            # Collect all trucks from warehouses for zone detection
            all_trucks = []
            for warehouse in self.warehouses:
                if hasattr(warehouse, 'trucks'):
                    all_trucks.extend(warehouse.trucks)
            
            # Use smart zone-based update instead of updating all 210K segments
            self.traffic_model.update_smart(self.road_network, all_trucks, self.current_time)
    
    def _get_active_truck_segments(self) -> set:
        """
        Get set of road segment IDs where trucks are currently traveling.
        
        This is used to limit accident generation to only road segments
        with active truck traffic, making accidents more realistic and
        reducing accident frequency from 111/day to 1-3/day.
        
        Returns:
            Set of segment IDs where trucks are in transit
        """
        active_segments = set()
        
        for warehouse in self.warehouses:
            for truck in warehouse.trucks:
                # Only count trucks that are in transit (moving)
                if truck.status != "in_transit":
                    continue
                
                # Get current route and segment
                if not hasattr(truck, 'current_route') or not truck.current_route:
                    continue
                
                route = truck.current_route
                
                # Try to get current segment from route
                segments = route.get('segments', [])
                if not segments:
                    continue
                
                # Get truck's progress through route
                if hasattr(truck, 'route_progress'):
                    idx = truck.route_progress
                elif hasattr(truck, 'current_segment_index'):
                    idx = truck.current_segment_index
                else:
                    idx = 0  # Default to first segment
                
                # Add current segment to active set
                if 0 <= idx < len(segments):
                    segment_id = segments[idx]
                    if segment_id:
                        active_segments.add(segment_id)
        
        return active_segments
    
    def _check_stochastic_events(self):
        """Check for probabilistic events (customer arrivals, accidents)."""
        # Generate accidents probabilistically
        if self.disruption_model and self.road_network and self.weather_model:
            # Get active truck segments to limit accident generation
            # Only check segments where trucks are currently traveling
            active_segments = self._get_active_truck_segments()
            
            new_accidents = self.disruption_model.generate_accidents(
                self.current_time,
                self.road_network,
                weather=self.weather_model.current_state,
                time_step_minutes=self.time_step,
                active_truck_segments=active_segments
            )
            
            # Clear expired accidents
            to_remove = []
            for accident in self.active_accidents:
                if self.current_time >= accident.end_time:
                    # Accident duration expired
                    segment = self.road_network.get_segment(accident.segment_id)
                    if segment:
                        segment.clear_accident()  # Use new method
                    accident.clear()
                    to_remove.append(accident)
                    logger.info(f"✅ Accident {accident.accident_id} cleared on segment {accident.segment_id}")
            
            for accident in to_remove:
                self.active_accidents.remove(accident)

            # Schedule accident events
            for accident in new_accidents:
                # Activate new accidents (apply to road network immediately)
                segment = self.road_network.get_segment(accident.segment_id)
                if segment:
                    # Use new partial blockage method with severity
                    segment.set_accident(severity=accident.severity)
                    accident.activate()
                    self.active_accidents.append(accident)
                    
                    # Log accident
                    logger.warning(f"🚨 ACCIDENT on segment {accident.segment_id} "
                                 f"(severity={accident.severity}, duration={accident.duration_minutes:.0f}min, "
                                 f"speed_reduction={segment.accident_speed_reduction*100:.1f}%)")
                    
                    self.log_event('road_accident', {
                        'accident_id': accident.accident_id,
                        'segment_id': accident.segment_id,
                        'severity': accident.severity,
                        'duration_minutes': accident.duration_minutes,
                        'speed_reduction_percent': segment.accident_speed_reduction * 100
                    })

                # Schedule start event
                start_event = AccidentStartEvent(
                    time=accident.start_time,
                    accident_id=accident.accident_id,
                    segment_id=accident.segment_id,
                    duration_minutes=accident.duration_minutes,
                    severity=accident.severity
                )
                self.event_queue.schedule(start_event)
                
                # Schedule end event
                end_event = AccidentEndEvent(
                    time=accident.end_time,
                    accident_id=accident.accident_id,
                    segment_id=accident.segment_id
                )
                self.event_queue.schedule(end_event)
                
                # Track active accident
                self.active_accidents.append(accident)
                accident.activate()
    
    def _handle_logging(self):
        """Handle 3-tier logging strategy."""
        # Snapshots: every timestep (synchronized with simulation loop)
        if self.current_time - self.last_snapshot_time >= self.time_step:
            self._log_snapshots()
            self.last_snapshot_time = self.current_time
        
        # Telemetry: handled by individual truck agents
        # Events: logged immediately when they occur
    
    def _log_startup_parameters(self):
        """Log simulation parameters at startup."""
        if self.mqtt_connected:
            payload = {
                'run_id': self.run_id,
                'timestamp': self.current_time,
                'event_type': 'simulation_start',
                'duration_days': self.max_time / 60 / 24,
                'time_step_minutes': self.time_step,
                'random_seed': self.random_seed,
                'num_warehouses': len(self.warehouses),
                'num_retailers': len(self.retailers),
                'num_trucks': len(self.trucks)
            }
            self.mqtt_client.publish('iot/simulation/events', payload)
        
        # Write directly to InfluxDB
        if self.influx_connected:
            point = Point("simulation_metadata") \
                .tag("run_id", self.run_id) \
                .tag("event_type", "simulation_start") \
                .field("duration_days", self.max_time / 60 / 24) \
                .field("time_step_minutes", self.time_step) \
                .field("speed", float(self.speed_multiplier) if self.speed_multiplier else 1.0) \
                .field("random_seed", self.random_seed if self.random_seed else 0) \
                .field("num_warehouses", len(self.warehouses)) \
                .field("num_retailers", len(self.retailers)) \
                .field("num_trucks", len(self.trucks))
                # No .time() - let InfluxDB use current wall-clock time
            try:
                self.influx_write_api.write(bucket=self.influx_bucket, record=point)
                logger.debug("InfluxDB: Wrote simulation_start event")
            except Exception as e:
                logger.warning(f"InfluxDB write failed: {e}")
    
    def _log_snapshots(self):
        """Log periodic state snapshots for all agents - writes to InfluxDB in batches."""
        logger.debug(f"Logging snapshots at t={self.current_time} min (synced with timestep={self.time_step})")
        
        # Collect all InfluxDB points for batch write
        influx_points = []
        
        # Warehouse snapshots
        for warehouse in self.warehouses:
            if hasattr(warehouse, 'get_state'):
                state = warehouse.get_state()
                
                # Publish to MQTT (for monitoring/debugging)
                if self.mqtt_connected:
                    mqtt_state = state.copy()
                    mqtt_state['run_id'] = self.run_id
                    mqtt_state['timestamp'] = self.current_time
                    self.mqtt_client.publish('iot/warehouse/state', mqtt_state)
                
                # Create InfluxDB point (don't write yet)
                if self.influx_connected:
                    try:
                        point = Point("warehouse_state") \
                            .tag("run_id", self.run_id) \
                            .tag("warehouse_id", state['warehouse_id'])
                        
                        # Add all fields from state (except location which is complex)
                        for key, value in state.items():
                            if key not in ['warehouse_id', 'location'] and isinstance(value, (int, float, bool)):
                                point = point.field(key, float(value))
                        
                        # Add timestamp field (simulation time in minutes)
                        point = point.field("timestamp", float(self.current_time))
                        
                        # Add location as separate fields
                        if 'location' in state:
                            point = point.field("latitude", float(state['location']['lat']))
                            point = point.field("longitude", float(state['location']['lon']))
                        
                        influx_points.append(point)
                    except Exception as e:
                        logger.warning(f"Failed to create warehouse point: {e}")
        
        # Retailer snapshots
        for retailer in self.retailers:
            if hasattr(retailer, 'get_state'):
                state = retailer.get_state()
                
                # Publish to MQTT
                if self.mqtt_connected:
                    mqtt_state = state.copy()
                    mqtt_state['run_id'] = self.run_id
                    mqtt_state['timestamp'] = self.current_time
                    self.mqtt_client.publish('iot/retailer/state', mqtt_state)
                
                # Create InfluxDB point (don't write yet)
                if self.influx_connected:
                    try:
                        point = Point("retailer_state") \
                            .tag("run_id", self.run_id) \
                            .tag("retailer_id", state['retailer_id']) \
                            .tag("warehouse_id", state.get('warehouse_id', ''))
                        
                        # Add all numeric fields (exclude pending_order which is boolean)
                        for key, value in state.items():
                            if key not in ['retailer_id', 'warehouse_id', 'location', 'pending_order'] and isinstance(value, (int, float)):
                                point = point.field(key, float(value))
                        
                        # Add pending_order as numeric (0 or 1)
                        if 'pending_order' in state:
                            point = point.field("pending_order", 1.0 if state['pending_order'] else 0.0)
                        
                        # Add timestamp field (simulation time in minutes  
                        point = point.field("timestamp", float(self.current_time))
                        
                        # Add location
                        if 'location' in state:
                            point = point.field("latitude", float(state['location']['lat']))
                            point = point.field("longitude", float(state['location']['lon']))
                        
                        influx_points.append(point)
                    except Exception as e:
                        logger.warning(f"Failed to create retailer point: {e}")
        
        # Truck snapshots
        for truck in self.trucks:
            if hasattr(truck, 'get_state'):
                state = truck.get_state()
                
                # Publish to MQTT
                if self.mqtt_connected:
                    mqtt_state = state.copy()
                    mqtt_state['run_id'] = self.run_id
                    mqtt_state['timestamp'] = self.current_time
                    self.mqtt_client.publish('iot/truck/state', mqtt_state)
                
                # Create InfluxDB point (don't write yet)
                if self.influx_connected:
                    try:
                        point = Point("truck_state") \
                            .tag("run_id", self.run_id) \
                            .tag("truck_id", state['truck_id']) \
                            .tag("warehouse_id", state.get('warehouse_id', '')) \
                            .tag("truck_type", state.get('truck_type', ''))
                        
                        # Convert status to numeric enum for InfluxDB compatibility
                        # String fields cause type conflicts in pivot() operations
                        if 'status' in state:
                            status_map = {
                                'idle': 0.0,
                                'in_transit': 1.0,
                                'loading': 2.0,
                                'unloading': 3.0,
                                'refueling': 4.0,
                                'maintenance': 5.0
                            }
                            status_numeric = status_map.get(state['status'], -1.0)
                            point = point.field("status_code", status_numeric)
                        
                        # Add all numeric fields
                        for key, value in state.items():
                            if key not in ['truck_id', 'warehouse_id', 'truck_type', 'status', 'location'] \
                               and isinstance(value, (int, float)):
                                point = point.field(key, float(value))
                        
                        # Add timestamp field (simulation time in minutes)
                        point = point.field("timestamp", float(self.current_time))
                        
                        # Add location
                        if 'location' in state and isinstance(state['location'], dict):
                            point = point.field("latitude", float(state['location'].get('lat', 0)))
                            point = point.field("longitude", float(state['location'].get('lon', 0)))
                        
                        influx_points.append(point)
                    except Exception as e:
                        logger.warning(f"Failed to create truck point: {e}")
        
        # Weather state snapshot (logged every timestep, not just on transitions)
        if self.influx_connected and self.weather_model:
            try:
                # Calculate time context for weather state
                current_dt = self.sim_start_datetime + timedelta(minutes=self.current_time)
                month = current_dt.month
                hour = current_dt.hour + (current_dt.minute / 60.0)
                
                # Get current weather state and environmental data
                weather_state = self.weather_model.current_state
                temperature = self.weather_model.get_temperature(month, hour)
                humidity = self.weather_model.get_humidity(month, hour)
                
                # Create weather snapshot point
                point = Point("weather_state") \
                    .tag("run_id", self.run_id) \
                    .tag("state", weather_state) \
                    .field("temperature_celsius", float(temperature)) \
                    .field("humidity_percent", float(humidity)) \
                    .field("timestamp", float(self.current_time)) \
                    .field("month", int(month)) \
                    .field("hour", float(hour))
                
                influx_points.append(point)
            except (ValueError, TypeError, AttributeError) as e:
                # Data conversion or field access errors
                logger.warning(f"Failed to create weather snapshot point (data error): {e}")
            except Exception as e:
                # Unexpected errors (likely InfluxDB client issues)
                logger.warning(f"Failed to create weather snapshot point (unexpected): {type(e).__name__}: {e}")
        
        # BATCH WRITE: Write all points asynchronously (non-blocking)
        if self.influx_connected and influx_points:
            try:
                # Async write - returns immediately, data buffered and sent in background
                self.influx_write_api.write(bucket=self.influx_bucket, record=influx_points)
                logger.debug(f"Queued {len(influx_points)} snapshot points for async InfluxDB write")
            except (ConnectionError, TimeoutError) as e:
                # Network/connection issues
                logger.warning(f"InfluxDB async write queue failed (connection): {e}")
            except (ValueError, TypeError) as e:
                # Data validation errors
                logger.warning(f"InfluxDB async write queue failed (invalid data): {e}")
            except Exception as e:
                # Unexpected errors
                logger.warning(f"InfluxDB async write queue failed (unexpected): {type(e).__name__}: {e}")
    
    def _cleanup(self):
        """Cleanup resources at end of simulation."""
        # CRITICAL: Write simulation_end event BEFORE closing writer
        if self.mqtt_connected:
            # Log simulation end event
            payload = {
                'run_id': self.run_id,
                'timestamp': self.current_time,
                'event_type': 'simulation_end'
            }
            self.mqtt_client.publish('iot/simulation/events', payload)
            
        # CRITICAL: Write to InfluxDB BEFORE closing writer
        if self.influx_connected and hasattr(self, 'influx_write_api') and self.influx_write_api:
            try:
                point = Point("simulation_metadata") \
                    .tag("run_id", self.run_id) \
                    .tag("event_type", "simulation_end") \
                    .field("final_time_minutes", self.current_time) \
                    .field("completed", True)
                    # No .time() - let InfluxDB use current wall-clock time
                self.influx_write_api.write(bucket=self.influx_bucket, record=point)
                logger.info(f"InfluxDB: Wrote simulation_end event for {self.run_id}")
            except (ConnectionError, TimeoutError) as e:
                # Network/connection issues during cleanup
                logger.warning(f"InfluxDB: Failed to write simulation_end (connection): {e}")
            except Exception as e:
                # Unexpected errors during cleanup (don't fail simulation)
                logger.warning(f"InfluxDB: Failed to write simulation_end (unexpected): {type(e).__name__}: {e}")
        
        # NOW close async InfluxDB writer (after writing simulation_end)
        if hasattr(self, 'influx_write_api') and self.influx_write_api:
            try:
                logger.info("Flushing and closing async InfluxDB writer...")
                self.influx_write_api.close()  # Flushes buffer and shuts down cleanly
                logger.info("InfluxDB writer closed successfully")
            except (ConnectionError, TimeoutError) as e:
                # Network issues during cleanup (expected in some cases)
                logger.warning(f"Error closing InfluxDB writer (connection): {e}")
            except Exception as e:
                # Other errors during cleanup (don't fail simulation)
                logger.warning(f"Error closing InfluxDB writer (unexpected): {type(e).__name__}: {e}")
        
        if self.mqtt_connected:
            # Disconnect MQTT
            self.mqtt_client.disconnect()
    
    def _check_and_write_heartbeat(self) -> None:
        """Write heartbeat to InfluxDB based on real-time (not simulation time)."""
        import time
        current_real_time = time.time()
        if current_real_time - self.last_heartbeat_time >= self.heartbeat_interval:
            self.last_heartbeat_time = current_real_time
            if self.influx_connected:
                try:
                    from influxdb_client import Point
                    heartbeat_point = Point("simulation_metadata") \
                        .tag("run_id", self.run_id) \
                        .tag("event_type", "heartbeat") \
                        .field("simulation_time_minutes", self.current_time) \
                        .field("heartbeat_interval_seconds", self.heartbeat_interval)
                    self.influx_write_api.write(bucket=self.influx_bucket, record=heartbeat_point)
                except (ConnectionError, TimeoutError) as e:
                    # Network issues with heartbeat (suppress after first warning)
                    if not hasattr(self, '_hb_err_count'):
                        self._hb_err_count = 0
                        logger.warning(f"Heartbeat write failed (connection): {e}")
                    self._hb_err_count += 1
                except Exception as e:
                    # Other errors with heartbeat (suppress after first warning)
                    if not hasattr(self, '_hb_err_count'):
                        self._hb_err_count = 0
                        logger.warning(f"Heartbeat write failed (unexpected): {type(e).__name__}: {e}")
                    self._hb_err_count += 1

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log an event immediately (Tier 1: Events).
        
        Events are discrete occurrences like orders, deliveries, accidents.
        They are logged immediately when they happen.
        
        Args:
            event_type: Type of event (e.g., 'truck_departure', 'order_placed')
            data: Event-specific data dictionary
        """
        # Publish to MQTT (for legacy monitoring)
        if self.mqtt_connected:
            payload = {
                'run_id': self.run_id,
                'timestamp': self.current_time,
                'event_type': event_type,
                **data
            }
            self.mqtt_client.publish('iot/events/all', payload)
        
        # Write to InfluxDB (for dashboard)
        if self.influx_connected:
            try:
                point = Point("events") \
                    .tag("run_id", self.run_id) \
                    .tag("event_type", event_type)
                
                # Add data as tags (strings) and fields (numbers)
                for key, value in data.items():
                    if value is None:
                        continue
                    elif isinstance(value, str):
                        point = point.tag(key, value)
                    elif isinstance(value, bool):
                        point = point.field(key, float(1 if value else 0))
                    elif isinstance(value, (int, float)):
                        point = point.field(key, float(value))
                
                # Add timestamp as field for querying
                point = point.field("sim_time", float(self.current_time))
                
                self.influx_write_api.write(bucket=self.influx_bucket, record=point)
                logger.debug(f"InfluxDB: Wrote event {event_type}")
            except (ConnectionError, TimeoutError) as e:
                # Network/connection issues
                logger.warning(f"InfluxDB event write failed (connection) for {event_type}: {e}")
            except (ValueError, TypeError) as e:
                # Data validation errors
                logger.warning(f"InfluxDB event write failed (invalid data) for {event_type}: {e}")
            except Exception as e:
                # Unexpected errors
                logger.warning(f"InfluxDB event write failed (unexpected) for {event_type}: {type(e).__name__}: {e}")
    
    def log_truck_telemetry(self, truck_id: str, telemetry_data: Dict[str, Any]):
        """
        Log truck telemetry data (Tier 3: Telemetry).
        
        Telemetry is high-frequency data from active trucks only.
        Called by truck agents every 5 minutes when in transit.
        
        Args:
            truck_id: Unique truck identifier
            telemetry_data: Telemetry data (position, fuel, speed, cargo temp, etc.)
        """
        # Publish to MQTT (for legacy monitoring)
        if self.mqtt_connected:
            payload = {
                'run_id': self.run_id,
                'timestamp': self.current_time,
                'truck_id': truck_id,
                **telemetry_data
            }
            self.mqtt_client.publish('iot/truck/telemetry', payload)
        
        # Write to InfluxDB (for dashboard)
        if self.influx_connected:
            try:
                point = Point("truck_telemetry") \
                    .tag("run_id", self.run_id) \
                    .tag("truck_id", truck_id)
                
                # Add status as tag if present
                if 'status' in telemetry_data:
                    point = point.tag("status", str(telemetry_data['status']))
                
                # Add telemetry data as fields
                for key, value in telemetry_data.items():
                    if value is None or key in ['location', 'location_true']:
                        continue  # Skip None and complex types
                    elif isinstance(value, str):
                        # Skip string fields except status (already tagged)
                        if key != 'status' and key != 'driver_status' and key != 'source':
                            continue
                    elif isinstance(value, bool):
                        point = point.field(key, float(1 if value else 0))
                    elif isinstance(value, (int, float)):
                        point = point.field(key, float(value))
                
                # Handle location separately (lat/lon as fields)
                if 'location' in telemetry_data and telemetry_data['location']:
                    lat, lon = telemetry_data['location']
                    point = point.field("latitude", float(lat))
                    point = point.field("longitude", float(lon))
                
                if 'location_true' in telemetry_data and telemetry_data['location_true']:
                    lat, lon = telemetry_data['location_true']
                    point = point.field("latitude_true", float(lat))
                    point = point.field("longitude_true", float(lon))
                
                # Add timestamp
                point = point.field("sim_time", float(self.current_time))
                
                self.influx_write_api.write(bucket=self.influx_bucket, record=point)
                logger.debug(f"InfluxDB: Wrote telemetry for {truck_id}")
            except (ConnectionError, TimeoutError) as e:
                # Network/connection issues
                logger.warning(f"InfluxDB telemetry write failed (connection) for {truck_id}: {e}")
            except (ValueError, TypeError) as e:
                # Data validation errors
                logger.warning(f"InfluxDB telemetry write failed (invalid data) for {truck_id}: {e}")
            except Exception as e:
                # Unexpected errors
                logger.warning(f"InfluxDB telemetry write failed (unexpected) for {truck_id}: {type(e).__name__}: {e}")
    
    def _write_snapshot_to_influxdb(self, snapshot_data: Dict[str, Any], current_time: float):
        """
        Write complete simulation snapshot to InfluxDB.
        
        Args:
            snapshot_data: Dictionary containing all snapshot data
            current_time: Current simulation time
        """
        if not self.mqtt_connected:
            logger.warning(f"Cannot write snapshot to InfluxDB at time {current_time:.1f}min - disconnected")
            logger.warning("Data loss risk! Check InfluxDB connection.")
            return
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current state of entire simulation.
        
        Returns:
            Dictionary containing complete simulation state
        """
        return {
            'run_id': self.run_id,
            'current_time': self.current_time,
            'current_time_formatted': self._format_time(self.current_time),
            'warehouses': [w.get_state() for w in self.warehouses if hasattr(w, 'get_state')],
            'retailers': [r.get_state() for r in self.retailers if hasattr(r, 'get_state')],
            'trucks': [t.get_state() for t in self.trucks if hasattr(t, 'get_state')]
        }
    
    def _format_time(self, minutes: float) -> str:
        """Format simulation time as human-readable string."""
        days = int(minutes // (24 * 60))
        hours = int((minutes % (24 * 60)) // 60)
        mins = int(minutes % 60)
        return f"Day {days}, {hours:02d}:{mins:02d}"


def parse_arguments():
    """
    Parse command-line arguments for simulation configuration.
    
    Returns:
        Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Digital Twin Supply Chain Simulation',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/simulation_config.yaml',
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--duration-days',
        type=int,
        default=None,
        help='Simulation duration in days (1-365), overrides config'
    )
    
    parser.add_argument(
        '--time-step',
        type=int,
        default=None,
        help='Time step in minutes (1-60), overrides config'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Simulation start date (YYYY-MM-DD format, e.g. 2023-07-01), overrides config'
    )
    
    parser.add_argument(
        '--speed',
        type=float,
        default=None,
        help='Simulation speed multiplier (e.g. 1.0 = real-time, 10.0 = 10x speed). If not set, runs max speed.'
    )
    
    return parser.parse_args()
