"""Disruption model for generating accidents probabilistically."""

import random
import numpy as np
from typing import Dict, Any, List
from ..entities.accident import Accident


class DisruptionModel:
    """
    Generates traffic accidents probabilistically based on research-backed rates.
    
    Accident probability depends on:
    - Road type (residential roads more dangerous than motorways)
    - Time of day (night is more dangerous)
    - Weather (rain increases accidents)
    - Traffic density (more vehicles = more accidents)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize DisruptionModel.
        
        Args:
            config: Configuration dictionary with disruption parameters
        """
        self.config = config
        accident_config = config.get('disruptions', {}).get('accidents', {})
        
        # Base accident rates per million vehicle-kilometers by road type
        self.base_rates = accident_config.get('base_rate_per_million_vkm', {})
        
        # Time-of-day multipliers
        self.time_multipliers = accident_config.get('time_multipliers', {})
        
        # Weather multipliers
        self.weather_multipliers = accident_config.get('weather_multipliers', {})
        
        # Density effect
        self.density_effect_enabled = accident_config.get('density_effect_enabled', True)
        
        # Duration parameters
        self.duration_mean = accident_config.get('duration_mean', 45)
        self.duration_std = accident_config.get('duration_std', 20)
        self.duration_min = accident_config.get('duration_min', 15)
        self.duration_max = accident_config.get('duration_max', 180)
        
        # Severity distribution
        severity_dist = accident_config.get('severity_distribution', {})
        self.severity_probs = {
            'minor': severity_dist.get('minor', 0.70),
            'moderate': severity_dist.get('moderate', 0.25),
            'severe': severity_dist.get('severe', 0.05)
        }
        
        # Severity duration multipliers
        self.severity_duration_mult = accident_config.get('severity_duration_multiplier', {})
        
        # Counter for unique IDs
        self.accident_counter = 0
        
        print(f"🚨 DisruptionModel initialized")
        print(f"   Base rates: {len(self.base_rates)} road types")
        print(f"   Severity distribution: {self.severity_probs}")
    
    def generate_accidents(self, current_time: float, road_network, 
                          weather: str = 'clear', 
                          time_step_minutes: float = 1.0,
                          active_truck_segments: set = None) -> List[Accident]:
        """
        Generate accidents probabilistically for current time step.
        
        Args:
            current_time: Current simulation time in minutes
            road_network: RoadNetwork instance
            weather: Current weather state
            time_step_minutes: Duration of time step
            active_truck_segments: Optional set of segment IDs where trucks are traveling
                                  If provided, only these segments are checked for accidents
                                  If None, all segments are checked (backward compatibility)
            
        Returns:
            List of new Accident objects
        """
        accidents = []
        
        # Get time of day category
        hour = int((current_time / 60) % 24)
        if 6 <= hour < 18:
            time_category = 'day'
        elif 18 <= hour < 22:
            time_category = 'evening'
        else:
            time_category = 'night'
        
        time_mult = self.time_multipliers.get(time_category, 1.0)
        weather_mult = self.weather_multipliers.get(weather, 1.0)
        
        # Only check segments with active truck traffic (if provided)
        if active_truck_segments:
            # Filter to only segments where trucks are currently traveling
            segments_to_check = [
                road_network.get_segment(seg_id) 
                for seg_id in active_truck_segments 
                if seg_id and road_network.get_segment(seg_id) is not None
            ]
        else:
            # Fallback: check all segments (backward compatibility)
            segments_to_check = road_network.segments.values()
        
        # Check each segment for potential accident
        for segment in segments_to_check:
            # Skip if segment is None or already blocked
            if segment is None or segment.is_blocked:
                continue
            
            # Calculate accident probability for this segment
            prob = self._calculate_accident_probability(
                segment, time_mult, weather_mult, time_step_minutes
            )
            
            # Generate random number to determine if accident occurs
            if random.random() < prob:
                # Create accident
                accident = self._create_accident(segment, current_time)
                accidents.append(accident)
        
        return accidents
    
    def _calculate_accident_probability(self, segment, time_mult: float, 
                                       weather_mult: float, 
                                       time_step_minutes: float) -> float:
        """
        Calculate probability of accident on segment during time step.
        
        Args:
            segment: RoadSegment instance
            time_mult: Time-of-day multiplier
            weather_mult: Weather multiplier
            time_step_minutes: Duration of time step
            
        Returns:
            Probability (0.0 to 1.0)
        """
        # Get base rate for road type (accidents per million vehicle-km)
        base_rate = self.base_rates.get(segment.road_type, 1.5)
        
        # Apply time and weather multipliers
        rate = base_rate * time_mult * weather_mult
        
        # Apply density effect if enabled
        if self.density_effect_enabled and segment.current_traffic_density > 0:
            # Get jam density for this road type
            jam_density = self.config.get('traffic', {}).get('jam_density_per_lane', {}).get(
                segment.road_type, 100
            )
            
            # Density ratio
            density_ratio = segment.current_traffic_density / jam_density if jam_density > 0 else 0
            
            # accident_multiplier = 0.5 + 1.5 * density_ratio
            # Low density (0.2): 0.8x, Medium (0.5): 1.25x, High (0.8): 1.7x
            density_mult = 0.5 + 1.5 * density_ratio
            rate *= density_mult
        
        # Calculate vehicle-kilometers in this time step
        # Assume average traffic flow = density * speed * lanes * length * time
        if segment.current_speed_kmh > 0:
            # Flow = density (veh/km/lane) * speed (km/h) * lanes * length (km) * time (hours)
            time_hours = time_step_minutes / 60.0
            vehicle_km = (segment.current_traffic_density * segment.current_speed_kmh * 
                         segment.lanes * segment.length_km * time_hours)
        else:
            vehicle_km = 0
        
        # Probability = (rate / 1,000,000) * vehicle_km
        probability = (rate / 1_000_000) * vehicle_km
        
        # Clamp to reasonable range
        return min(0.01, max(0.0, probability))  # Max 1% per time step
    
    def _create_accident(self, segment, current_time: float) -> Accident:
        """
        Create a new accident with random duration and severity.
        
        Args:
            segment: RoadSegment where accident occurs
            current_time: Current simulation time
            
        Returns:
            Accident instance
        """
        # Generate unique ID
        self.accident_counter += 1
        accident_id = f"ACC{self.accident_counter:04d}"
        
        # Determine severity
        severity = self._sample_severity()
        
        # Generate duration
        base_duration = np.random.normal(self.duration_mean, self.duration_std)
        base_duration = max(self.duration_min, min(self.duration_max, base_duration))
        
        # Apply severity multiplier
        severity_mult = self.severity_duration_mult.get(severity, 1.0)
        duration = base_duration * severity_mult
        
        # Create accident
        accident = Accident(
            accident_id=accident_id,
            segment_id=segment.segment_id,
            start_time=current_time,
            duration_minutes=duration,
            severity=severity
        )
        
        return accident
    
    def _sample_severity(self) -> str:
        """
        Sample accident severity from distribution.
        
        Returns:
            'minor', 'moderate', or 'severe'
        """
        rand = random.random()
        cumulative = 0.0
        
        for severity, prob in self.severity_probs.items():
            cumulative += prob
            if rand < cumulative:
                return severity
        
        return 'minor'  # Fallback
    
    def __repr__(self) -> str:
        return f"DisruptionModel(accidents_generated={self.accident_counter})"
