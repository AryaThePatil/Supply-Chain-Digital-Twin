"""RetailerAgent - Autonomous agent for retail operations."""

import logging
import random
from typing import Optional, List, Dict, Tuple
from .warehouse_agent import WarehouseAgent
from ..models.demand_model import DemandModel
from ..models.inventory_model import InventoryModel
from ..entities.order import Order

# Module-level logger
logger = logging.getLogger(__name__)


class RetailerAgent:
    """
    Autonomous agent managing retail operations.
    
    Responsibilities:
    - Simulate customer demand (time-varying arrivals)
    - Manage inventory with (s,S) policy
    - Place orders when inventory low
    - Track sales and stockouts
    """
    
    def __init__(self, retailer_id: str, location: Tuple[float, float],
                 initial_inventory_kg: float, warehouse_ids: List[str],
                 demand_config: Dict, inventory_config: Dict, road_network, config: Dict):
        """
        Initialize RetailerAgent.
        
        Args:
            retailer_id: Unique identifier
            location: (lat, lon) position
            initial_inventory_kg: Starting inventory
            warehouse_ids: List of warehouse IDs this retailer subscribes to
            demand_config: Demand model configuration
            inventory_config: Inventory model configuration
            road_network: RoadNetwork instance
            config: Full configuration dict (for selection weights)
        """
        self.retailer_id = retailer_id
        self.location = location
        self.warehouse_ids = warehouse_ids  # List, not single ID
        self.road_network = road_network
        self.current_inventory_kg = initial_inventory_kg
        
        # Store warehouse selection weights
        self.selection_weights = config.get('agent_generation', {}).get(
            'retailer_warehouse_subscription', {}
        ).get('selection_criteria', {'distance_weight': 0.4, 'load_weight': 0.6})
        
        # Find retailer node in road network
        self.node_id = road_network.get_nearest_node(location[0], location[1])
        
        # Initialize models
        self.demand_model = DemandModel(demand_config)
        self.inventory_model = InventoryModel(inventory_config)
        
        # Order tracking
        self.pending_order: Optional[Order] = None
        self.order_counter = 0
        self.last_inventory_check = 0
        self.inventory_check_interval = inventory_config['review_period_hours'] * 60  # minutes
        
        # Metrics
        self.total_customers_served = 0
        self.total_kg_sold = 0.0
        self.stockout_count = 0
        self.stockout_duration = 0.0  # Total time spent in stockout
        self.last_stockout_start: Optional[float] = None
    
    def select_warehouse(self, warehouses: List) -> Optional:
        """
        Select best warehouse from subscribed list based on distance and load.
        
        Args:
            warehouses: List of all WarehouseAgent instances
            
        Returns:
            Selected WarehouseAgent or None if no suitable warehouse
        """
        # Filter to subscribed warehouses only
        subscribed = [wh for wh in warehouses if wh.warehouse_id in self.warehouse_ids]
        
        if not subscribed:
            logger.warning(f"{self.retailer_id}: No subscribed warehouses available")
            return None
        
        # Score each warehouse (lower is better)
        scores = []
        for wh in subscribed:
            # Distance score (normalized 0-1)
            distance = self.road_network._haversine_distance(
                self.location[0], self.location[1],
                wh.location[0], wh.location[1]
            )
            
            # Get max distance for normalization
            max_distance = max(
                self.road_network._haversine_distance(
                    self.location[0], self.location[1],
                    w.location[0], w.location[1]
                ) for w in subscribed
            )
            
            distance_score = distance / max_distance if max_distance > 0 else 0
            
            # Load score (normalized 0-1) - pending orders
            max_orders = max(len(w.pending_orders) for w in subscribed)
            load_score = len(wh.pending_orders) / max_orders if max_orders > 0 else 0
            
            # Combined score (lower is better)
            total_score = (
                distance_score * self.selection_weights['distance_weight'] +
                load_score * self.selection_weights['load_weight']
            )
            
            scores.append((total_score, wh))
        
        # Return warehouse with lowest score
        selected = min(scores, key=lambda x: x[0])[1]
        logger.debug(f"{self.retailer_id}: Selected warehouse {selected.warehouse_id}")
        return selected
    

    def update(self, current_time: float, time_step: float, 
              day_of_week: int, month: int, weather: str = "clear",
              temperature_celsius: float = 25.0, humidity_percent: float = 50.0,
              engine=None) -> List[Dict]:
        """
        Update retailer state for one time step.
        
        Args:
            current_time: Current simulation time in minutes
            time_step: Time step duration in minutes
            day_of_week: Day of week (0=Sunday, 6=Saturday)
            month: Month (1=January, 12=December)
            weather: Weather condition
            temperature_celsius: Current temperature
            humidity_percent: Current relative humidity (%)
            engine: SimulationEngine instance (for scheduling events)
            
        Returns:
            List of events generated during update
        """
        events = []
        
        # Generate customer arrivals and process sales
        sales_events = self._process_customer_demand(
            current_time, time_step, day_of_week, month, weather, temperature_celsius
        )
        events.extend(sales_events)
        
        # Check inventory and place order if needed
        if current_time - self.last_inventory_check >= self.inventory_check_interval:
            order_event = self._check_inventory(current_time, engine)
            if order_event:
                events.append(order_event)
            self.last_inventory_check = current_time
        
        # Track stockout duration
        if self.current_inventory_kg <= 0:
            if self.last_stockout_start is None:
                self.last_stockout_start = current_time
        else:
            if self.last_stockout_start is not None:
                self.stockout_duration += current_time - self.last_stockout_start
                self.last_stockout_start = None
        
        return events
    
    def _process_customer_demand(self, current_time: float, time_step: float,
                                 day_of_week: int, month: int, weather: str,
                                 temperature_celsius: float) -> List[Dict]:
        """
        Generate customer arrivals and process sales.
        
        Args:
            current_time: Current simulation time
            time_step: Time step duration
            day_of_week: Day of week
            month: Month
            weather: Weather condition
            temperature_celsius: Temperature
            
        Returns:
            List of events
        """
        events = []
        
        # Generate number of customer arrivals
        num_customers = self.demand_model.generate_customer_arrivals(
            current_time, time_step, day_of_week, month, weather, temperature_celsius
        )
        
        if num_customers == 0:
            return events
        
        # Process each customer
        for _ in range(num_customers):
            # Generate purchase quantity
            purchase_qty = self.demand_model.generate_purchase_quantity()
            
            # Record demand for forecasting
            self.inventory_model.record_demand(current_time, purchase_qty)
            
            # Check if we can fulfill
            if self.current_inventory_kg >= purchase_qty:
                # Successful sale
                self.current_inventory_kg -= purchase_qty
                self.total_customers_served += 1
                self.total_kg_sold += purchase_qty
                
                events.append({
                    'type': 'sale',
                    'retailer_id': self.retailer_id,
                    'time': current_time,
                    'quantity_kg': purchase_qty,
                    'remaining_inventory_kg': self.current_inventory_kg
                })
            else:
                # Stockout - lost sale
                self.stockout_count += 1
                
                events.append({
                    'type': 'stockout',
                    'retailer_id': self.retailer_id,
                    'time': current_time,
                    'lost_sale_kg': purchase_qty,
                    'inventory_kg': self.current_inventory_kg
                })
        
        return events
    
    def _check_inventory(self, current_time: float, engine=None) -> Optional[Dict]:
        """
        Check inventory level and place order if needed.
        
        Uses (s,S) policy:
        - If inventory <= s (reorder point), order up to S
        
        Args:
            current_time: Current simulation time
            engine: SimulationEngine instance (for scheduling events)
            
        Returns:
            Order event dict if order placed, None otherwise
        """
        # Don't place new order if one is already pending
        if self.pending_order and self.pending_order.status in ["pending", "assigned", "in_transit"]:
            return None
        
        # Check if should reorder
        if self.inventory_model.should_reorder(self.current_inventory_kg):
            # Calculate order quantity
            order_qty = self.inventory_model.calculate_order_quantity(self.current_inventory_kg)
            
            if order_qty > 0:
                # Select best warehouse dynamically
                selected_warehouse = self.select_warehouse(engine.warehouses) if engine else None
                
                if not selected_warehouse:
                    logger.warning(f"{self.retailer_id}: No suitable warehouse available for order")
                    return None
                
                warehouse_id = selected_warehouse.warehouse_id
                
                # Create order
                order_id = f"{self.retailer_id}_order_{self.order_counter:04d}"
                self.order_counter += 1
                
                # Calculate priority based on inventory level
                # Lower inventory = higher priority
                reorder_point = self.inventory_model.calculate_reorder_point()
                if reorder_point > 0:
                    priority = 1.0 + (1.0 - self.current_inventory_kg / reorder_point)
                else:
                    priority = 2.0  # High priority if reorder point is 0
                
                order = Order(
                    order_id, self.retailer_id, warehouse_id,
                    order_qty, current_time, priority,
                    retailer_node_id=self.node_id
                )
                
                self.pending_order = order
                
                # Schedule OrderPlacedEvent to send order to warehouse
                if engine:
                    from ..events.event_types import OrderPlacedEvent
                    event = OrderPlacedEvent(
                        time=current_time,
                        order_id=order_id,
                        retailer_id=self.retailer_id,
                        warehouse_id=warehouse_id,
                        quantity_kg=order_qty,
                        order_obj=order
                    )
                    engine.event_queue.schedule(event)
                
                logger.info(f"[ORDER] {self.retailer_id} ordering {order_qty:.1f}kg from {warehouse_id} "
                           f"(Order: {order_id}, Priority: {priority:.2f}, Current Inventory: {self.current_inventory_kg:.1f}kg)")
                
                return {
                    'type': 'order_placed',
                    'retailer_id': self.retailer_id,
                    'warehouse_id': warehouse_id,
                    'order_id': order_id,
                    'time': current_time,
                    'quantity_kg': order_qty,
                    'priority': priority,
                    'current_inventory_kg': self.current_inventory_kg,
                    'reorder_point': reorder_point
                }
        
        return None
    
    def receive_delivery(self, quantity_kg: float, current_time: float) -> Dict:
        """
        Receive delivery from warehouse.
        
        Args:
            quantity_kg: Quantity delivered
            current_time: Current simulation time
            
        Returns:
            Event dict
        """
        self.current_inventory_kg += quantity_kg
        
        # Mark pending order as delivered
        if self.pending_order:
            self.pending_order.mark_delivered(current_time)
            self.pending_order = None
        
        return {
            'type': 'delivery_received',
            'retailer_id': self.retailer_id,
            'time': current_time,
            'quantity_kg': quantity_kg,
            'new_inventory_kg': self.current_inventory_kg
        }
    
    def get_service_level(self) -> float:
        """
        Calculate service level (percentage of customers served).
        
        Returns:
            Service level as percentage (0-100)
        """
        total_demand = self.total_customers_served + self.stockout_count
        if total_demand > 0:
            return (self.total_customers_served / total_demand) * 100.0
        return 100.0
    
    def get_inventory_turnover(self, simulation_duration_days: float) -> float:
        """
        Calculate inventory turnover rate.
        
        Args:
            simulation_duration_days: Total simulation duration
            
        Returns:
            Turnover rate (times per year)
        """
        if self.current_inventory_kg > 0 and simulation_duration_days > 0:
            avg_inventory = self.current_inventory_kg  # Simplified
            annual_sales = self.total_kg_sold * (365.0 / simulation_duration_days)
            return annual_sales / avg_inventory
        return 0.0
    
    def trigger_emergency_reorder(self, quantity_kg: float, current_time: float, engine=None):
        """
        Trigger emergency reorder when delivery fails quality check.
        
        Places immediate order to warehouse to replace rejected cargo.
        
        Args:
            quantity_kg: Quantity to reorder
            current_time: Current simulation time
            engine: SimulationEngine instance
        """
        # Create emergency order
        order = Order(
            order_id=f"ORD_EMERGENCY_{self.retailer_id}_{int(current_time)}",
            retailer_id=self.retailer_id,
            warehouse_id=self.warehouse_ids[0],  # Use first subscribed warehouse for emergency
            quantity_kg=quantity_kg,
            order_time=current_time,
            priority=10  # High priority for emergency
        )
        
        # Find warehouse and submit order
        if engine:
            for warehouse in engine.warehouses:
                if warehouse.warehouse_id == self.warehouse_ids[0]:  # Use first subscribed
                    warehouse.receive_order(order)
                    logger.warning(f"[EMERGENCY] {self.retailer_id} reordered {quantity_kg:.1f}kg due to quality rejection")
                    break
    
    def get_state(self) -> Dict:
        """
        Get current retailer state for snapshot logging.
        
        Returns:
            Dictionary with retailer state data
        """
        return {
            'retailer_id': self.retailer_id,
            'location': {'lat': self.location[0], 'lon': self.location[1]},
            'warehouse_ids': self.warehouse_ids,  # List of subscribed warehouses
            'current_inventory_kg': round(self.current_inventory_kg, 2),
            'reorder_point_kg': round(self.inventory_model.calculate_reorder_point(), 2),
            'target_level_kg': round(self.inventory_model.calculate_order_up_to_level(), 2),
            'total_sales_kg': round(self.total_kg_sold, 2),
           'customers_served': self.total_customers_served,
            'customers_lost': self.stockout_count,
            'service_level_percent': round(self.get_service_level(), 2),
            'pending_order': self.pending_order is not None
        }
    
    def __repr__(self) -> str:
        return (f"RetailerAgent(id={self.retailer_id}, "
                f"inventory={self.current_inventory_kg:.0f}kg, "
                f"service_level={self.get_service_level():.1f}%)")
