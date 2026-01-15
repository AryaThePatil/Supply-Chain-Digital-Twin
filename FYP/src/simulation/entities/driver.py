"""Driver entity for modeling human factors in supply chain."""

import logging
import random
from typing import Dict, Any

# Module-level logger
logger = logging.getLogger(__name__)

class Driver:
    """
    Models a truck driver with fatigue, skill levels, and break requirements.
    
    Features:
    - Skill levels (Novice, Experienced, Expert) affecting efficiency
    - Fatigue accumulation based on driving time
    - Mandatory break enforcement
    - Sleep requirements after long shifts
    - Speed penalties for fatigue
    """
    
    def __init__(self, driver_id: str, config: Dict[str, Any]):
        """
        Initialize Driver.
        
        Args:
            driver_id: Unique identifier
            config: Driver configuration from simulation_config.yaml
        """
        self.driver_id = driver_id
        self.config = config
        
        # Skill level
        self.skill_level = self._assign_skill_level()
        
        # State
        self.driving_time_since_break = 0.0  # minutes
        self.total_shift_time = 0.0  # minutes
        self.accumulated_fatigue = 0.0  # Total fatigue in minutes (NEW)
        self.is_on_break = False
        self.is_sleeping = False  # NEW
        self.break_remaining_time = 0.0  # minutes
        self.sleep_remaining_time = 0.0  # NEW
        self.fatigue_level = 0.0  # 0.0 to 1.0
        
        # Limits
        self.max_continuous_driving = config.get('mandatory_break_after_hours', 4.5) * 60
        self.break_duration = config.get('break_duration_minutes', 45)
        self.shift_duration = config.get('shift_duration_hours', 10) * 60
        self.sleep_duration = 8 * 60  # 8 hours sleep required (NEW)
        self.max_fatigue_before_sleep = 10 * 60  # 10 hours driving requires sleep (NEW)
        
    def _assign_skill_level(self) -> str:
        """Assign skill level based on configured distribution."""
        dist = self.config.get('skill_distribution', {'experienced': 1.0})
        levels = list(dist.keys())
        weights = list(dist.values())
        return random.choices(levels, weights=weights)[0]
    
    def update(self, time_step_minutes: float, is_driving: bool):
        """
        Update driver state.
        
        Args:
            time_step_minutes: Simulation time step
            is_driving: Whether the truck is currently moving
        """
        # Handle sleep (NEW)
        if self.is_sleeping:
            self.sleep_remaining_time -= time_step_minutes
            if self.sleep_remaining_time <= 0:
                self._wake_up()
            return
        
        # Handle break
        if self.is_on_break:
            self.break_remaining_time -= time_step_minutes
            if self.break_remaining_time <= 0:
                self._end_break()
            return

        if is_driving:
            self.driving_time_since_break += time_step_minutes
            self.total_shift_time += time_step_minutes
            self.accumulated_fatigue += time_step_minutes  # NEW
            
            # Increase fatigue
            # Simple model: linear increase over shift
            self.fatigue_level = min(1.0, self.total_shift_time / self.shift_duration)
            
            # Check for mandatory sleep (NEW)
            if self.accumulated_fatigue >= self.max_fatigue_before_sleep:
                self.go_to_sleep()
                return
            
            # Check for mandatory break
            if self.driving_time_since_break >= self.max_continuous_driving:
                self.take_break()
                
    def take_break(self):
        """Start a mandatory break."""
        self.is_on_break = True
        self.break_remaining_time = self.break_duration
        self.driving_time_since_break = 0.0
        # Fatigue recovers slightly on break
        self.accumulated_fatigue = max(0.0, self.accumulated_fatigue - (self.break_duration * 0.3))
        
    def _end_break(self):
        """End the current break."""
        self.is_on_break = False
    
    def go_to_sleep(self):
        """Start mandatory sleep period (NEW)."""
        self.is_sleeping = True
        self.sleep_remaining_time = self.sleep_duration
        logger.info(f"[DRIVER] {self.driver_id} going to sleep - exhausted after {self.accumulated_fatigue/60:.1f}hrs")
    
    def _wake_up(self):
        """Wake up after sleep (NEW)."""
        self.is_sleeping = False
        self.accumulated_fatigue = 0.0  # Fully rested
        self.total_shift_time = 0.0
        self.fatigue_level = 0.0
        logger.info(f"[DRIVER] {self.driver_id} woken up - fully rested")
        
    def get_speed_multiplier(self) -> float:
        """
        Get speed multiplier based on skill and fatigue.
        
        Fatigue now has stronger effect on speed (NEW).
        """
        # Skill effect
        skill_mult = {
            'novice': 0.95,
            'experienced': 1.0,
            'expert': 1.05
        }.get(self.skill_level, 1.0)
        
        # Fatigue effect (stronger penalties - NEW)
        fatigue_hours = self.accumulated_fatigue / 60.0
        if fatigue_hours > 10:
            fatigue_penalty = 0.25  # 25% slower when exhausted
        elif fatigue_hours > 8:
            fatigue_penalty = 0.15  # 15% slower when very tired
        elif fatigue_hours > 6:
            fatigue_penalty = 0.08  # 8% slower when tired
        else:
            fatigue_penalty = 0.0
        
        return skill_mult * (1.0 - fatigue_penalty)
    
    def is_exhausted(self) -> bool:
        """Check if driver is dangerously exhausted (NEW)."""
        return self.accumulated_fatigue / 60.0 > 8.0
        
    def get_fuel_efficiency_multiplier(self) -> float:
        """Get fuel efficiency multiplier (1.0 = normal, >1.0 = worse)."""
        # Skill effect
        skill_mult = {
            'novice': 1.10,      # 10% more fuel
            'experienced': 1.0,
            'expert': 0.95       # 5% less fuel
        }.get(self.skill_level, 1.0)
        
        return skill_mult

    def __repr__(self) -> str:
        if self.is_sleeping:
            status = "Sleeping"
        elif self.is_on_break:
            status = "Break"
        else:
            status = "Driving"
        return (f"Driver({self.driver_id}, {self.skill_level}, {status}, "
                f"Fatigue: {self.accumulated_fatigue/60:.1f}hrs)")

