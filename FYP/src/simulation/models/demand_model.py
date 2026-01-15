"""Demand model for time-varying customer arrivals."""

import random
import math
import numpy as np
from typing import Dict, List


class DemandModel:
    """
    Stochastic demand model using Poisson process with time-varying arrival rates.
    
    Models realistic customer arrivals with:
    - Time-of-day patterns (lunch and evening peaks)
    - Day-of-week patterns (higher on weekends)
    - Seasonal patterns (monthly variations)
    - Weather effects
    - Temperature effects
    """
    
    def __init__(self, config: Dict):
        """
        Initialize DemandModel.
        
        Args:
            config: Demand configuration from simulation_config.yaml
        """
        self.base_arrival_rate = config['base_arrival_rate_per_hour']
        self.time_of_day_multipliers = config['time_of_day_multipliers']
        self.day_of_week_multipliers = config['day_of_week_multipliers']
        self.seasonal_multipliers = config['seasonal_multipliers']
        
        # Purchase quantity parameters
        self.purchase_mean = config['purchase_quantity_mean']
        self.purchase_std = config['purchase_quantity_std']
        self.purchase_min = config['purchase_quantity_min']
        self.purchase_max = config['purchase_quantity_max']
        
        # Weather and temperature effects
        self.weather_multipliers = config.get('weather_demand_multipliers', {})
        self.temp_effect_enabled = config.get('temperature_demand_effect', {}).get('enabled', False)
        self.base_temperature = config.get('temperature_demand_effect', {}).get('base_temperature_celsius', 25)
        self.temp_multiplier_per_degree = config.get('temperature_demand_effect', {}).get('multiplier_per_degree', 0.02)
        self.max_temp_multiplier = config.get('temperature_demand_effect', {}).get('max_multiplier', 1.3)
        
    def get_arrival_rate(self, current_time: float, day_of_week: int, 
                        month: int, weather: str = "clear", 
                        temperature_celsius: float = 25.0) -> float:
        """
        Calculate time-varying customer arrival rate (customers per hour).
        
        Args:
            current_time: Current simulation time in minutes
            day_of_week: Day of week (0=Sunday, 6=Saturday)
            month: Month (1=January, 12=December)
            weather: Weather condition
            temperature_celsius: Current temperature
            
        Returns:
            Arrival rate in customers per hour
        """
        # Get hour of day (0-23)
        hour = int((current_time / 60) % 24)
        
        # Base rate
        rate = self.base_arrival_rate
        
        # Apply time-of-day multiplier
        rate *= self.time_of_day_multipliers[hour]
        
        # Apply day-of-week multiplier
        rate *= self.day_of_week_multipliers[day_of_week]
        
        # Apply seasonal multiplier
        rate *= self.seasonal_multipliers[month - 1]
        
        # Apply weather multiplier
        if weather in self.weather_multipliers:
            rate *= self.weather_multipliers[weather]
        
        # Apply temperature effect
        if self.temp_effect_enabled:
            temp_diff = temperature_celsius - self.base_temperature
            temp_mult = 1.0 + (temp_diff * self.temp_multiplier_per_degree)
            temp_mult = min(self.max_temp_multiplier, max(0.7, temp_mult))
            rate *= temp_mult
        
        return max(0.0, rate)
    
    def generate_customer_arrivals(self, current_time: float, time_step: float,
                                   day_of_week: int, month: int,
                                   weather: str = "clear",
                                   temperature_celsius: float = 25.0) -> int:
        """
        Generate number of customer arrivals in time step using Poisson process.
        
        Args:
            current_time: Current simulation time in minutes
            time_step: Time step duration in minutes
            day_of_week: Day of week (0=Sunday, 6=Saturday)
            month: Month (1=January, 12=December)
            weather: Weather condition
            temperature_celsius: Current temperature
            
        Returns:
            Number of customers arriving in this time step
        """
        # Get arrival rate (customers per hour)
        rate_per_hour = self.get_arrival_rate(
            current_time, day_of_week, month, weather, temperature_celsius
        )
        
        # Convert to rate per time step
        rate_per_step = rate_per_hour * (time_step / 60.0)
        
        # Generate Poisson random variable
        if rate_per_step > 0:
            return np.random.poisson(rate_per_step)
        return 0
    
    def generate_purchase_quantity(self) -> float:
        """
        Generate random purchase quantity for a customer.
        
        Uses normal distribution with configured mean and std,
        clamped to min/max bounds.
        
        Returns:
            Purchase quantity in kg
        """
        quantity = random.gauss(self.purchase_mean, self.purchase_std)
        return max(self.purchase_min, min(self.purchase_max, quantity))
    
    def __repr__(self) -> str:
        return f"DemandModel(base_rate={self.base_arrival_rate} customers/hour)"
