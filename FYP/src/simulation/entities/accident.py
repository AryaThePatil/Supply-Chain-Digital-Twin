"""Accident entity for traffic disruptions."""

from typing import Optional


class Accident:
    """
    Traffic accident that can block a road segment or involve a truck.
    
    Two types of accidents:
    1. Road accidents: Block segment, slow traffic
    2. Truck accidents: Total loss - truck destroyed, cargo lost
    
    Accidents have:
    - Duration (how long the segment is blocked)
    - Severity (minor, moderate, severe)
    - Location (which segment is affected)
    - Involved truck (if truck-involved accident)
    """
    
    def __init__(self, accident_id: str, segment_id: str, 
                 start_time: float, duration_minutes: float, 
                 severity: str, involved_truck_id: Optional[str] = None):
        """
        Initialize an Accident.
        
        Args:
            accident_id: Unique identifier
            segment_id: ID of affected road segment
            start_time: Simulation time when accident occurs
            duration_minutes: How long segment is blocked
            severity: 'minor', 'moderate', or 'severe'
            involved_truck_id: ID of truck involved (if truck accident)
        """
        self.accident_id = accident_id
        self.segment_id = segment_id
        self.start_time = start_time
        self.duration_minutes = duration_minutes
        self.severity = severity
        self.end_time = start_time + duration_minutes
        self.is_active = False
        
        # Truck involvement (NEW)
        self.involved_truck_id = involved_truck_id
        self.is_truck_accident = involved_truck_id is not None
        
    def activate(self):
        """Mark accident as active (segment is blocked)."""
        self.is_active = True
        
    def clear(self):
        """Mark accident as cleared (segment is unblocked)."""
        self.is_active = False
        
    def __repr__(self) -> str:
        truck_info = f", truck={self.involved_truck_id}" if self.is_truck_accident else ""
        return (f"Accident(id={self.accident_id}, segment={self.segment_id}, "
                f"severity={self.severity}, duration={self.duration_minutes:.0f}min, "
                f"active={self.is_active}{truck_info})")

