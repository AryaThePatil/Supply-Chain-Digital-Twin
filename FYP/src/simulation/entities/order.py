"""Order entity for tracking delivery requests."""

from typing import Optional
from datetime import datetime


class Order:
    """Order entity representing a retailer's delivery request."""
    
    def __init__(self, order_id: str, retailer_id: str, warehouse_id: str,
                 quantity_kg: float, timestamp: float, priority: float = 1.0,
                 retailer_node_id: int = None):
        """
        Initialize an Order.
        
        Args:
            order_id: Unique identifier
            retailer_id: ID of requesting retailer
            warehouse_id: ID of fulfilling warehouse
            quantity_kg: Quantity requested in kg
            timestamp: Simulation time when order was placed
            priority: Priority level (higher = more urgent)
            retailer_node_id: Road network node ID of retailer (for routing)
        """
        self.order_id = order_id
        self.retailer_id = retailer_id
        self.warehouse_id = warehouse_id
        self.quantity_kg = quantity_kg
        self.timestamp = timestamp
        self.priority = priority
        self.retailer_node_id = retailer_node_id  # For routing
        
        # Status tracking
        self.status = "pending"  # pending, assigned, in_transit, delivered, cancelled
        self.assigned_truck_id: Optional[str] = None
        self.assigned_time: Optional[float] = None
        self.departure_time: Optional[float] = None
        self.delivery_time: Optional[float] = None
        
        # Batch tracking
        self.batch_ids = []  # List of OrangeBatch IDs assigned to this order
        
    def assign_truck(self, truck_id: str, current_time: float):
        """Assign a truck to this order."""
        self.assigned_truck_id = truck_id
        self.assigned_time = current_time
        self.status = "assigned"
    
    def mark_departed(self, current_time: float):
        """Mark order as departed from warehouse."""
        self.departure_time = current_time
        self.status = "in_transit"
    
    def mark_delivered(self, current_time: float):
        """Mark order as delivered."""
        self.delivery_time = current_time
        self.status = "delivered"
    
    def mark_cancelled(self):
        """Mark order as cancelled."""
        self.status = "cancelled"
    
    def get_wait_time(self, current_time: float) -> float:
        """
        Get time order has been waiting.
        
        Args:
            current_time: Current simulation time
            
        Returns:
            Wait time in minutes
        """
        if self.status == "pending":
            return current_time - self.timestamp
        elif self.assigned_time:
            return self.assigned_time - self.timestamp
        return 0.0
    
    def get_delivery_time(self) -> Optional[float]:
        """
        Get total time from order to delivery.
        
        Returns:
            Delivery time in minutes, or None if not delivered
        """
        if self.delivery_time:
            return self.delivery_time - self.timestamp
        return None
    
    def __repr__(self) -> str:
        return (f"Order(id={self.order_id}, retailer={self.retailer_id}, "
                f"qty={self.quantity_kg:.0f}kg, status={self.status})")
