"""Simple weather model for Phase 3."""

import random
import math
from typing import Dict, Tuple, Optional, List

class WeatherModel:
    """
    Weather model with Nagpur-specific seasonal temperature and humidity logic.
    
    Weather states: clear, light_rain, rain, heavy_rain, fog
    Temperature/Humidity: Based on month and hour.
    """
    
    # Nagpur Monthly Average Temperatures (Low, High)
    MONTHLY_TEMPS = {
        1:  (13, 28), # Jan
        2:  (15, 32), # Feb
        3:  (20, 36), # Mar
        4:  (24, 40), # Apr
        5:  (28, 42), # May (Peak Summer)
        6:  (26, 38), # Jun (Monsoon starts)
        7:  (24, 32), # Jul
        8:  (23, 30), # Aug
        9:  (22, 31), # Sep
        10: (20, 32), # Oct
        11: (15, 30), # Nov
        12: (12, 28)  # Dec
    }

    # Nagpur Monthly Average Relative Humidity (Afternoon, Morning)
    # Source: IMD Data
    MONTHLY_HUMIDITY = {
        1:  (40, 70), # Jan (Dry afternoon, humid morning)
        2:  (30, 60),
        3:  (20, 45), # Mar (Dry)
        4:  (20, 40), # Apr (Very Dry)
        5:  (25, 45), # May
        6:  (50, 75), # Jun (Monsoon start)
        7:  (75, 90), # Jul (Wet)
        8:  (80, 92), # Aug (Very Wet)
        9:  (70, 90), # Sep
        10: (55, 80), # Oct
        11: (50, 75), # Nov
        12: (45, 75)  # Dec
    }
    
    def __init__(self, config: Dict):
        """
        Initialize WeatherModel.
        
        Args:
            config: Weather configuration from simulation_config.yaml
        """
        self.config = config.get('weather', {})
        
        # Base probabilities (fallback)
        self.default_probs = self.config.get('state_probabilities', {
            'clear': 0.70, 'light_rain': 0.15, 'rain': 0.10, 'heavy_rain': 0.04, 'fog': 0.01
        })
        
        # Average duration for each state (in minutes)
        duration_hours = self.config.get('average_duration_hours', {})
        self.state_durations = {
            state: hours * 60 for state, hours in duration_hours.items()
        }
        
        if not self.state_durations:
            self.state_durations = {
                'clear': 720, 'light_rain': 180, 'rain': 240, 'heavy_rain': 120, 'fog': 180
            }
        
        self.current_state = 'clear'
        self.state_start_time = 0
        self.state_duration = self.state_durations['clear']
        
    def update(self, current_time: float, month: int = 1, hour: float = 12.0) -> List[Dict]:
        """
        Update weather state with seasonal awareness.
        
        Args:
            current_time: Time in minutes
            month: Current month (1-12)
            hour: Current hour (0-24)
            
        Returns:
            List of events (weather_change if state changed)
        """
        events = []
        time_in_state = current_time - self.state_start_time
        
        if time_in_state >= self.state_duration:
            event = self._change_weather(current_time, month, hour)
            if event:
                events.append(event)
        
        return events
    
    def _change_weather(self, current_time: float, month: int, hour: float) -> Optional[Dict]:
        """Determine next weather state based on Season and Time of Day.
        
        Returns:
            Event dict if state changed, None otherwise
        """
        old_state = self.current_state
        
        # 1. Determine Seasonal Probabilities
        probs = self.default_probs.copy()
        
        # MONSOON (Jun-Sep): drastic increase in rain
        if month in [6, 7, 8, 9]:
            probs['clear'] = 0.20
            probs['light_rain'] = 0.30
            probs['rain'] = 0.30
            probs['heavy_rain'] = 0.19
            probs['fog'] = 0.01
            
        # WINTER (Nov-Feb): Fog in mornings
        elif month in [11, 12, 1, 2]:
            probs['clear'] = 0.85
            probs['light_rain'] = 0.05
            probs['rain'] = 0.0
            probs['heavy_rain'] = 0.0
            
            # Fog logic: High chance between 04:00 and 08:00
            if 4 <= hour <= 8:
                probs['fog'] = 0.40
                probs['clear'] = 0.55
            else:
                probs['fog'] = 0.02
        
        # SUMMER (Mar-May): Mostly clear
        elif month in [3, 4, 5]:
             probs['clear'] = 0.95
             probs['light_rain'] = 0.05
             probs['rain'] = 0.0
             probs['heavy_rain'] = 0.0
             probs['fog'] = 0.0

        # CRITICAL FIX: Force state to change (exclude current state)
        # Remove current state from available choices
        available_states = [s for s in probs.keys() if s != old_state]
        available_weights = [probs[s] for s in available_states]
        
        # Renormalize probabilities to sum to 1
        total_weight = sum(available_weights)
        if total_weight > 0:
            normalized_weights = [w / total_weight for w in available_weights]
        else:
            # Fallback: equal probability for all non-current states
            normalized_weights = [1.0 / len(available_states)] * len(available_states)
        
        # Select new state (guaranteed to be different from old_state)
        new_state = random.choices(available_states, weights=normalized_weights)[0]
        
        # Update state
        self.current_state = new_state
        
        # Duration jitter
        base_dur = self.state_durations.get(self.current_state, 180)
        self.state_duration = base_dur * random.uniform(0.7, 1.3)
        self.state_start_time = current_time
        
        # Return event (old_state != new_state is now guaranteed)
        return {
            'type': 'weather_change',
            'time': current_time,
            'old_state': old_state,
            'new_state': new_state,
            'duration_minutes': self.state_duration
        }

    def get_temperature(self, month: int, hour: float) -> float:
        """Calculate temperature (Celsius) based on Month and Hour."""
        # Input validation
        month = max(1, min(12, int(month)))
        hour = max(0.0, min(23.99, float(hour)))
        
        low, high = self.MONTHLY_TEMPS.get(month, (20, 30))
        
        amplitude = (high - low) / 2.0
        avg = (high + low) / 2.0
        
        # Peak at 14:00, Low at 02:00
        diurnal_variation = math.cos((hour - 14) * 2 * math.pi / 24)
        
        # Weather cooling
        cooling = 0.0
        if self.current_state in ['rain', 'light_rain']: cooling = -3.0
        elif self.current_state == 'heavy_rain': cooling = -5.0
        elif self.current_state == 'fog': cooling = -2.0
            
        return avg + (amplitude * diurnal_variation) + cooling

    def get_humidity(self, month: int, hour: float) -> float:
        """
        Calculate Relative Humidity (%) based on Month, Hour, and Weather.
        
        Humidity peaks at pre-dawn (05:00), lowest at afternoon (14:00).
        """
        # Input validation
        month = max(1, min(12, int(month)))
        hour = max(0.0, min(23.99, float(hour)))
        
        min_h, max_h = self.MONTHLY_HUMIDITY.get(month, (40, 70))
        
        avg = (min_h + max_h) / 2.0
        amp = (max_h - min_h) / 2.0
        
        # Peak at 05:00 (pre-dawn), Low at 14:00 (afternoon)
        # -cos(h-17) peaks at h=17-12=5 (05:00)
        diurnal = -math.cos((hour - 17) * 2 * math.pi / 24)
        humidity = avg + (amp * diurnal)
        
        # Weather boosts
        if self.current_state in ['rain', 'light_rain']: 
            humidity += 15
        elif self.current_state == 'heavy_rain': 
            humidity += 25
        elif self.current_state == 'fog': 
            humidity = 95.0  # Fog is saturation
        
        # Clamp to realistic bounds
        return min(100.0, max(10.0, humidity))

    def get_current_state(self) -> str:
        return self.current_state
