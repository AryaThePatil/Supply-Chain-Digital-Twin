"""
Priority queue for managing discrete events in the simulation.

Events are scheduled at specific simulation times and executed in chronological order.
"""

import heapq
from typing import List, Optional
from .event_types import Event


class EventQueue:
    """
    Priority queue for scheduling and executing discrete events.
    
    Uses a min-heap to efficiently retrieve events in chronological order.
    """
    
    def __init__(self):
        """Initialize empty event queue."""
        self._heap: List[tuple] = []  # List of (time, counter, event) tuples
        self._counter = 0  # Ensures FIFO order for events at same time
    
    def schedule(self, event: Event):
        """
        Schedule an event to occur at a specific time.
        
        Args:
            event: Event instance with time attribute
        """
        # Use counter to ensure FIFO order for events at same time
        heapq.heappush(self._heap, (event.time, self._counter, event))
        self._counter += 1
    
    def get_events_at(self, time: float, tolerance: float = 0.001) -> List[Event]:
        """
        Get all events scheduled for times up to and including the current time.
        
        Args:
            time: Current simulation time
            tolerance: No longer used (kept for API compatibility)
        
        Returns:
            List of events scheduled at or before this time
        """
        events = []
        
        # Get all events scheduled at or before current time
        while self._heap and self._heap[0][0] <= time:
            _, _, event = heapq.heappop(self._heap)
            events.append(event)
        
        return events
    
    def peek(self) -> Optional[Event]:
        """
        Get the next scheduled event without removing it.
        
        Returns:
            Next event, or None if queue is empty
        """
        if self._heap:
            return self._heap[0][2]  # Return event (third element of tuple)
        return None
    
    def peek_next_time(self) -> Optional[float]:
        """
        Get the time of the next scheduled event without removing it.
        
        Returns:
            Time of next event, or None if queue is empty
        """
        if self._heap:
            return self._heap[0][0]
        return None
    
    def is_empty(self) -> bool:
        """Check if queue has no events."""
        return len(self._heap) == 0
    
    def size(self) -> int:
        """Get number of events in queue."""
        return len(self._heap)
    
    def clear(self):
        """Remove all events from queue."""
        self._heap.clear()
        self._counter = 0
    
    def __len__(self) -> int:
        """Get number of events in queue."""
        return len(self._heap)
    
    def __repr__(self) -> str:
        return f"EventQueue(size={len(self._heap)}, next_time={self.peek_next_time()})"
