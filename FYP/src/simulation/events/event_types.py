"""
Event type definitions for the simulation.

Each event represents a discrete occurrence at a specific simulation time.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Event(ABC):
    """
    Base class for all simulation events.
    
    Events are discrete occurrences that happen at specific simulation times.
    """
    
    def __init__(self, time: float, event_type: str):
        """
        Initialize event.
        
        Args:
            time: Simulation time when event occurs (minutes)
            event_type: String identifier for event type
        """
        self.time = time
        self.event_type = event_type
    
    @abstractmethod
    def execute(self, simulation):
        """
        Execute the event's action.
        
        Args:
            simulation: SimulationEngine instance
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            'time': self.time,
            'event_type': self.event_type
        }
    
    def __lt__(self, other):
        """Compare events by time for priority queue."""
        return self.time < other.time
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(time={self.time})"


class TruckDepartureEvent(Event):
    """Truck departs from warehouse with cargo."""
    
    def __init__(self, time: float, truck_id: str, warehouse_id: str, 
                 destination_id: str, cargo_batch_id: str):
        super().__init__(time, 'truck_departure')
        self.truck_id = truck_id
        self.warehouse_id = warehouse_id
        self.destination_id = destination_id
        self.cargo_batch_id = cargo_batch_id
    
    def execute(self, simulation):
        """Log departure event."""
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'truck_id': self.truck_id,
            'warehouse_id': self.warehouse_id,
            'destination_id': self.destination_id,
            'cargo_batch_id': self.cargo_batch_id
        })
        return data


class TruckArrivalEvent(Event):
    """Truck arrives at destination."""
    
    def __init__(self, time: float, truck_id: str, destination_id: str, 
                 cargo_batch_id: str):
        super().__init__(time, 'truck_arrival')
        self.truck_id = truck_id
        self.destination_id = destination_id
        self.cargo_batch_id = cargo_batch_id
    
    def execute(self, simulation):
        """Log arrival event and update truck status."""
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'truck_id': self.truck_id,
            'destination_id': self.destination_id,
            'cargo_batch_id': self.cargo_batch_id
        })
        return data


class OrderPlacedEvent(Event):
    """Retailer places order with warehouse."""
    
    def __init__(self, time: float, order_id: str, retailer_id: str, 
                 warehouse_id: str, quantity_kg: int, order_obj):
        super().__init__(time, 'order_placed')
        self.order_id = order_id
        self.retailer_id = retailer_id
        self.warehouse_id = warehouse_id
        self.quantity_kg = quantity_kg
        self.order_obj = order_obj  # The actual Order object
    
    def execute(self, simulation):
        """Send order to warehouse and log event."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"[EVENT] OrderPlacedEvent executing: {self.order_id} → {self.warehouse_id}")
        logger.debug(f"[EVENT] Available warehouses: {[w.warehouse_id for w in simulation.warehouses]}")
        
        # Find the warehouse and send the order  
        warehouse_found = False
        for warehouse in simulation.warehouses:
            if warehouse.warehouse_id == self.warehouse_id:
                logger.debug(f"[EVENT] Found warehouse {self.warehouse_id}, calling receive_order()")
                warehouse.receive_order(self.order_obj)
                warehouse_found = True
                break
        
        if not warehouse_found:
            logger.error(f"[EVENT ERROR] Warehouse {self.warehouse_id} NOT FOUND! Order {self.order_id} cannot be delivered!")
        
        # Log the event
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'order_id': self.order_id,
            'retailer_id': self.retailer_id,
            'warehouse_id': self.warehouse_id,
            'quantity_kg': self.quantity_kg
        })
        return data


class AccidentStartEvent(Event):
    """Accident blocks a road segment."""
    
    def __init__(self, time: float, accident_id: str, segment_id: str, 
                 duration_minutes: float, severity: str):
        super().__init__(time, 'accident_start')
        self.accident_id = accident_id
        self.segment_id = segment_id
        self.duration_minutes = duration_minutes
        self.severity = severity
    
    def execute(self, simulation):
        """Block road segment and log event."""
        if simulation.road_network:
            segment = simulation.road_network.get_segment(self.segment_id)
            if segment:
                segment.is_blocked = True
        
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'accident_id': self.accident_id,
            'segment_id': self.segment_id,
            'duration_minutes': self.duration_minutes,
            'severity': self.severity
        })
        return data


class AccidentEndEvent(Event):
    """Accident clears and road segment reopens."""
    
    def __init__(self, time: float, accident_id: str, segment_id: str):
        super().__init__(time, 'accident_end')
        self.accident_id = accident_id
        self.segment_id = segment_id
    
    def execute(self, simulation):
        """Unblock road segment and log event."""
        if simulation.road_network:
            segment = simulation.road_network.get_segment(self.segment_id)
            if segment:
                segment.is_blocked = False
        
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'accident_id': self.accident_id,
            'segment_id': self.segment_id
        })
        return data


class WarehouseRestockEvent(Event):
    """Warehouse receives shipment from factory."""
    
    def __init__(self, time: float, warehouse_id: str, product_type: str, 
                 quantity_kg: int):
        super().__init__(time, 'warehouse_restock')
        self.warehouse_id = warehouse_id
        self.product_type = product_type
        self.quantity_kg = quantity_kg
    
    def execute(self, simulation):
        """Increase warehouse inventory and log event."""
        # Find warehouse and call restock method
        for warehouse in simulation.warehouses:
            if warehouse.warehouse_id == self.warehouse_id:
                if hasattr(warehouse, 'restock'):
                    warehouse.restock(self.quantity_kg, simulation.current_time)
                elif hasattr(warehouse, 'inventory'):
                    # Fallback for simple inventory dict
                    warehouse.inventory[self.product_type] = \
                        warehouse.inventory.get(self.product_type, 0) + self.quantity_kg
                break
        
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'warehouse_id': self.warehouse_id,
            'product_type': self.product_type,
            'quantity_kg': self.quantity_kg
        })
        return data


class CustomerArrivalEvent(Event):
    """Customer arrives at retailer to purchase."""
    
    def __init__(self, time: float, retailer_id: str, quantity_kg: int):
        super().__init__(time, 'customer_arrival')
        self.retailer_id = retailer_id
        self.quantity_kg = quantity_kg
    
    def execute(self, simulation):
        """Process customer purchase."""
        # Will be implemented when RetailerAgent is created
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'retailer_id': self.retailer_id,
            'quantity_kg': self.quantity_kg
        })
        return data


class RouteChangedEvent(Event):
    """Truck changes route due to traffic or accident."""
    
    def __init__(self, time: float, truck_id: str, old_route_length: float, 
                 new_route_length: float, reason: str):
        super().__init__(time, 'route_changed')
        self.truck_id = truck_id
        self.old_route_length = old_route_length
        self.new_route_length = new_route_length
        self.reason = reason
    
    def execute(self, simulation):
        """Log route change event."""
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'truck_id': self.truck_id,
            'old_route_length': self.old_route_length,
            'new_route_length': self.new_route_length,
            'reason': self.reason
        })
        return data


class LowFuelWarningEvent(Event):
    """Truck fuel drops below warning threshold."""
    
    def __init__(self, time: float, truck_id: str, fuel_liters: float, 
                 fuel_percent: float):
        super().__init__(time, 'low_fuel_warning')
        self.truck_id = truck_id
        self.fuel_liters = fuel_liters
        self.fuel_percent = fuel_percent
    
    def execute(self, simulation):
        """Log low fuel warning."""
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'truck_id': self.truck_id,
            'fuel_liters': self.fuel_liters,
            'fuel_percent': self.fuel_percent
        })
        return data


class CargoSpoiledEvent(Event):
    """Cargo RSL reaches zero (spoiled)."""
    
    def __init__(self, time: float, truck_id: str, cargo_batch_id: str, 
                 final_rsl: float):
        super().__init__(time, 'cargo_spoiled')
        self.truck_id = truck_id
        self.cargo_batch_id = cargo_batch_id
        self.final_rsl = final_rsl
    
    def execute(self, simulation):
        """Log spoilage event."""
        simulation.log_event(self.event_type, self.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            'truck_id': self.truck_id,
            'cargo_batch_id': self.cargo_batch_id,
            'final_rsl': self.final_rsl
        })
        return data
