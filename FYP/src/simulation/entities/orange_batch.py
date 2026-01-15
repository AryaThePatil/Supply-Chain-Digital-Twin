"""Orange batch entity with quality degradation modeling."""

import math
from datetime import datetime
from typing import Optional


class OrangeBatch:
    """Perishable orange batch with quality degradation based on Arrhenius equation."""
    
    def __init__(self, batch_id: str, quantity: int, 
                 harvest_date: datetime, initial_quality: float = 100.0):
        """
        Initialize an OrangeBatch.
        
        Args:
            batch_id: Unique identifier for the batch
            quantity: Number of units in the batch
            harvest_date: Date when oranges were harvested
            initial_quality: Initial quality percentage (default 100.0)
        """
        self.batch_id = batch_id
        self.quantity = quantity
        self.harvest_date = harvest_date
        self.initial_quality = initial_quality
        self.current_rsl = 100.0  # Remaining Shelf Life percentage
        self.last_update_time = 0  # Last time RSL was updated
        
    def update_rsl(self, temperature_celsius: float, humidity_percent: float, current_time: float):
        """
        Update RSL using Q10 temperature and humidity dependent degradation model.
        
        Q10 model: degradation rate doubles every 10°C increase above optimal.
        Humidity: Low humidity (<85%) accelerates degradation due to moisture loss.
        """
        # Reference temperature (4°C optimal storage for oranges)
        optimal_temp = 4.0
        
        # Q10 coefficient
        Q10 = 2.0
        
        # Temperature difference from optimal
        temp_diff = temperature_celsius - optimal_temp
        
        # Calculate degradation rate multiplier (Temp)
        rate_multiplier = Q10 ** (temp_diff / 10.0)
        
        # Humidity Multiplier (Optimal: 85-95%)
        humidity_multiplier = 1.0
        
        if humidity_percent < 85.0:
            # LOW HUMIDITY: Shriveling/dehydration
            # At 35% humidity (Summer), factor is ~1.25x faster decay
            humidity_multiplier += (85.0 - humidity_percent) * 0.005
        elif humidity_percent > 95.0:
            # HIGH HUMIDITY: Mold/fungal growth risk
            # At 100% humidity, factor is ~1.10x faster decay
            humidity_multiplier += (humidity_percent - 95.0) * 0.02
            
        rate_multiplier *= humidity_multiplier
        
        # Base degradation rate at optimal temp (% per hour)
        base_rate_per_hour = 100.0 / 336.0
        
        # Calculate time elapsed in hours
        time_elapsed_hours = (current_time - self.last_update_time) / 60.0
        
        # Calculate degradation
        degradation = base_rate_per_hour * rate_multiplier * time_elapsed_hours
        
        # Update RSL
        self.current_rsl = max(0, min(100, self.current_rsl - degradation))
        
        # Update last update time
        self.last_update_time = current_time
        
    def is_spoiled(self) -> bool:
        """
        Check if the batch is spoiled.
        
        Returns:
            True if current_rsl <= 0, False otherwise
        """
        return self.current_rsl <= 0
    
    def is_acceptable_quality(self, min_rsl_hours: float = 72.0) -> bool:
        """
        Check if batch quality is acceptable for delivery/sale.
        
        Retailers need minimum RSL to have time to sell before spoilage.
        Default threshold: 72 hours (3 days)
        
        Args:
            min_rsl_hours: Minimum remaining shelf life in hours
            
        Returns:
            True if acceptable, False if should be rejected
        """
        # Convert RSL percentage to hours (assuming 14-day total shelf life)
        total_shelf_life_hours = 14 * 24  # 336 hours
        remaining_hours = (self.current_rsl / 100.0) * total_shelf_life_hours
        
        return remaining_hours >= min_rsl_hours
    
    def __repr__(self) -> str:
        return (f"OrangeBatch(id={self.batch_id}, quantity={self.quantity}, "
                f"rsl={self.current_rsl:.2f}%)")

