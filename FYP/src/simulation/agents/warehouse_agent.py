"""WarehouseAgent - Autonomous agent for warehouse operations."""

import logging
from typing import List, Dict, Optional, Tuple
from ..entities.truck import Truck, TruckType
from ..entities.order import Order
from ..entities.orange_batch import OrangeBatch
from .truck_agent import TruckAgent

# Module-level logger
logger = logging.getLogger(__name__)


class WarehouseAgent:
    """
    Autonomous agent managing warehouse operations.
    
    Responsibilities:
    - Manage inventory of oranges
    - Own and allocate heterogeneous truck fleet
    - Prioritize and fulfill orders
    - Handle periodic restocking
    - Track warehouse metrics
    """
    
    def __init__(self, warehouse_id: str, location: Tuple[float, float],
                 initial_inventory_kg: float, fleet_config: List[Dict],
                 truck_types: Dict[str, TruckType], road_network, router, config: Dict,
                 restock_schedule: Dict = None):
        """
        Initialize WarehouseAgent.
        
        Args:
            warehouse_id: Unique identifier
            location: (lat, lon) position
            initial_inventory_kg: Starting inventory
            fleet_config: List of {type: str, count: int} for fleet composition
            truck_types: Dict mapping type name to TruckType
            road_network: RoadNetwork instance
            router: Router instance
            config: Configuration dict
            restock_schedule: Optional dict with restock schedule (day_of_week, time_of_day, quantity_kg)
        """
        self.warehouse_id = warehouse_id
        self.location = location
        self.current_inventory_kg = initial_inventory_kg
        self.restock_schedule = restock_schedule  # Store restock schedule
        self.config = config  # Store config for later use
        
        # Find warehouse node in road network
        self.node_id = road_network.get_nearest_node(location[0], location[1])
        
        # Create heterogeneous truck fleet
        self.trucks: List[Truck] = []
        self.truck_agents: Dict[str, TruckAgent] = {}
        
        truck_counter = 0
        for fleet_spec in fleet_config:
            truck_type_name = fleet_spec['type']
            count = fleet_spec['count']
            truck_type = truck_types[truck_type_name]
            
            for i in range(count):
                truck_id = f"{warehouse_id}_truck_{truck_type_name}_{i:02d}"
                truck = Truck(truck_id, truck_type, warehouse_id, location)
                truck.current_node = self.node_id
                
                # Create agent for this truck
                agent = TruckAgent(truck, road_network, router, config)
                
                self.trucks.append(truck)
                self.truck_agents[truck_id] = agent
                truck_counter += 1
        
        # Order management
        self.pending_orders: List[Order] = []
        self.active_orders: Dict[str, Order] = {}  # order_id -> Order
        self.completed_orders: List[Order] = []
        
        # Batch management
        self.batch_counter = 0
        self.inventory_batches: List[OrangeBatch] = []
        self._initialize_inventory_batches(initial_inventory_kg)
        
        # Metrics
        self.total_orders_fulfilled = 0
        self.total_kg_shipped = 0.0
        self.inventory_shortages = 0

        # Dynamic Restocking (New Logic)
        self.reorder_point = config.get('warehouse', {}).get('reorder_point_kg', 5000.0)
        self.restock_amount = config.get('warehouse', {}).get('restock_amount_kg', 20000.0)
        self.restock_lead_time_minutes = config.get('warehouse', {}).get('restock_lead_time_minutes', 24 * 60) # 24 hours
        self.pending_restock = False
        
        # OPTIMIZATION 8: Event-driven order processing
        self.pending_orders_changed = False  # Flag: new orders added
        self.trucks_changed = False  # Flag: truck returned/became available
        
    def _initialize_inventory_batches(self, total_kg: float):
        """Create initial inventory as batches."""
        import datetime
        # Get batch size from config (moved from hardcoded 1000)
        batch_size = self.config.get('warehouse_operations', {}).get('batch_size_kg', 1000)
        num_batches = int(total_kg / batch_size)
        remainder = total_kg % batch_size
        
        for i in range(num_batches):
            batch = OrangeBatch(
                f"{self.warehouse_id}_batch_{self.batch_counter:04d}",
                batch_size,
                datetime.datetime.now(),
                100.0
            )
            self.inventory_batches.append(batch)
            self.batch_counter += 1
        
        if remainder > 0:
            batch = OrangeBatch(
                f"{self.warehouse_id}_batch_{self.batch_counter:04d}",
                remainder,
                datetime.datetime.now(),
                100.0
            )
            self.inventory_batches.append(batch)
            self.batch_counter += 1
    
    def update(self, current_time: float, time_step: float, ambient_temperature: float = 25.0, ambient_humidity: float = 50.0, current_weather: str = 'clear', engine=None) -> List[Dict]:
        """
        Update warehouse state for one time step.
        
        Args:
            current_time: Current simulation time in minutes
            time_step: Time step duration in minutes
            ambient_temperature: Current ambient temperature in Celsius
            ambient_humidity: Current relative humidity (%)
            current_weather: Current weather state
            engine: SimulationEngine instance (for accessing retailers)
            
        Returns:
            List of events generated during update
        """
        events = []
        
        # CRITICAL FIX: Update RSL for warehouse inventory in cold storage
        # Standard citrus cold storage: 6°C, 85-90% RH
        WAREHOUSE_STORAGE_TEMP = 6.0  # Celsius
        WAREHOUSE_STORAGE_HUMIDITY = 88.0  # Percent
        
        for batch in self.inventory_batches:
            batch.update_rsl(WAREHOUSE_STORAGE_TEMP, WAREHOUSE_STORAGE_HUMIDITY, current_time)
            
            # Check for spoiled batches
            if batch.is_spoiled():
                events.append({
                    'type': 'warehouse_batch_spoiled',
                    'warehouse_id': self.warehouse_id,
                    'batch_id': batch.batch_id,
                    'time': current_time,
                    'quantity_kg': batch.quantity
                })
        
        # Calculate spoilage BEFORE removing from list
        spoiled_kg = sum(b.quantity for b in self.inventory_batches if b.is_spoiled())
        if spoiled_kg > 0:
            self.current_inventory_kg = max(0, self.current_inventory_kg - spoiled_kg)
        
        # Then remove spoiled batches from inventory
        self.inventory_batches = [b for b in self.inventory_batches if not b.is_spoiled()]
        
        # Update all truck agents
        for agent in self.truck_agents.values():
            truck_events = agent.update(current_time, time_step, ambient_temperature, ambient_humidity, current_weather)
            events.extend(truck_events)
            
            # Handle truck arrivals
            # Handle truck arrivals
            if agent.truck.status == "arrived":
                if agent.truck.destination_node == self.node_id:
                    # Truck returned to warehouse
                    self._handle_truck_return(agent.truck, current_time)
                else:
                    # Truck arrived at retailer - START UNLOADING (realistic delay)
                    unloading_event = agent.start_unloading(current_time)
                    if unloading_event:
                        events.append(unloading_event)
            
            # Handle completed unloading
            elif agent.truck.status == "unloading_complete":
                 # Unloading finished - deliver cargo and return
                 delivery_event = self._handle_retailer_delivery(agent.truck, current_time, engine)
                 if delivery_event:
                     events.append(delivery_event)
        
        # OPTIMIZATION 8: Only process pending orders if something changed
        # (new order arrived OR truck became available)
        if self.pending_orders and (self.pending_orders_changed or self.trucks_changed):
            allocation_events = self._allocate_orders(current_time)
            events.extend(allocation_events)
            # Reset flags
            self.pending_orders_changed = False
            self.trucks_changed = False
            
        # Check for dynamic restocking
        if self.current_inventory_kg <= self.reorder_point and not self.pending_restock:
            self.pending_restock = True
            
            # Schedule restocking event
            if engine:
                from ..events.event_types import WarehouseRestockEvent
                restock_time = current_time + self.restock_lead_time_minutes
                event = WarehouseRestockEvent(
                    time=restock_time,
                    warehouse_id=self.warehouse_id,
                    product_type="oranges",
                    quantity_kg=self.restock_amount
                )
                engine.event_queue.schedule(event)
                
                events.append({
                    'type': 'warehouse_reorder_triggered',
                    'warehouse_id': self.warehouse_id,
                    'time': current_time,
                    'current_inventory': self.current_inventory_kg,
                    'restock_amount': self.restock_amount,
                    'eta': restock_time
                })
        
        return events
    
    def receive_order(self, order: Order):
        """
        Receive a new order from a retailer.
        
        Args:
            order: Order object
        """
        self.pending_orders.append(order)
        # Sort by priority (higher priority first)
        self.pending_orders.sort(key=lambda o: o.priority, reverse=True)
        
        # OPTIMIZATION 8: Set flag for event-driven processing
        self.pending_orders_changed = True
        
        logger.info(f"[ORDER] {self.warehouse_id} received order {order.order_id} from {order.retailer_id}: "
                   f"{order.quantity_kg:.1f}kg (Priority: {order.priority:.2f}, Pending Orders: {len(self.pending_orders)})")
    
    def _allocate_orders(self, current_time: float) -> List[Dict]:
        """
        Allocate available trucks to pending orders.
        
        Uses priority-based allocation:
        1. Sort orders by priority (urgency)
        2. For each order, find best available truck
        3. Assign truck and prepare delivery
        
        Args:
            current_time: Current simulation time
            
        Returns:
            List of events generated
        """
        events = []
        
        # Find available trucks (idle status, at warehouse)
        available_trucks = [
            truck for truck in self.trucks
            if truck.status == "idle" and truck.current_node == self.node_id
        ]
        
        if not available_trucks:
            return events
        
        # Process orders in priority order
        orders_to_remove = []
        
        for order in self.pending_orders:
            if not available_trucks:
                break
            
            # Check if we have enough inventory
            if self.current_inventory_kg < order.quantity_kg:
                self.inventory_shortages += 1
                events.append({
                    'type': 'inventory_shortage',
                    'warehouse_id': self.warehouse_id,
                    'order_id': order.order_id,
                    'time': current_time,
                    'required_kg': order.quantity_kg,
                    'available_kg': self.current_inventory_kg
                })
                continue
            
            # Find best truck for this order (smallest truck that can fit the load)
            best_truck = None
            for truck in sorted(available_trucks, key=lambda t: t.truck_type.capacity_kg):
                if truck.truck_type.capacity_kg >= order.quantity_kg:
                    best_truck = truck
                    break
            
            if not best_truck:
                # No truck large enough
                continue
            
            # Allocate batches for this order
            batches = self._allocate_batches(order.quantity_kg)
            if not batches:
                continue
            
            # Get retailer node from order
            retailer_node = order.retailer_node_id
            
            if retailer_node is None:
                # Skip order if no node ID (shouldn't happen)
                continue
            
            # Assign delivery to truck agent
            agent = self.truck_agents[best_truck.truck_id]
            success = agent.assign_delivery(
                retailer_node, order.order_id, batches, current_time
            )
            
            if success:
                # Update order status
                order.assign_truck(best_truck.truck_id, current_time)
                order.mark_departed(current_time)
                
                # Move order to active
                self.active_orders[order.order_id] = order
                orders_to_remove.append(order)
                
                # Remove truck from available list
                available_trucks.remove(best_truck)
                
                # Update metrics
                self.current_inventory_kg -= order.quantity_kg
                self.total_kg_shipped += order.quantity_kg
                
                logger.info(f"[DISPATCH] {self.warehouse_id} assigned order {order.order_id} to truck {best_truck.truck_id}: "
                           f"{order.quantity_kg:.1f}kg → {order.retailer_id} (Inventory: {self.current_inventory_kg:.1f}kg)")
                
                events.append({
                    'type': 'order_assigned',
                    'warehouse_id': self.warehouse_id,
                    'order_id': order.order_id,
                    'truck_id': best_truck.truck_id,
                    'time': current_time,
                    'quantity_kg': order.quantity_kg
                })
            else:
                # Assignment failed, return batches to inventory
                self.inventory_batches.extend(batches)
        
        # Remove allocated orders from pending
        for order in orders_to_remove:
            self.pending_orders.remove(order)
        
        return events
    
    def _allocate_batches(self, quantity_kg: float) -> List[OrangeBatch]:
        """
        Allocate batches from inventory for an order.
        
        Uses FIFO (First In First Out) - oldest batches first.
        
        Args:
            quantity_kg: Quantity needed
            
        Returns:
            List of OrangeBatch objects, or empty list if insufficient inventory
        """
        if self.current_inventory_kg < quantity_kg:
            return []
        
        allocated = []
        remaining = quantity_kg
        
        # Sort batches by harvest date (oldest first)
        self.inventory_batches.sort(key=lambda b: b.harvest_date)
        
        batches_to_remove = []
        for batch in self.inventory_batches:
            if remaining <= 0:
                break
            
            if batch.quantity <= remaining:
                # Take entire batch
                allocated.append(batch)
                if batch not in batches_to_remove:
                    batches_to_remove.append(batch)
                remaining -= batch.quantity
            else:
                # Split batch
                # Create new batch with needed quantity
                import datetime
                new_batch = OrangeBatch(
                    f"{self.warehouse_id}_batch_{self.batch_counter:04d}",
                    remaining,
                    batch.harvest_date,
                    batch.current_rsl
                )
                # Preserve RSL tracking state
                new_batch.last_update_time = batch.last_update_time
                
                self.batch_counter += 1
                allocated.append(new_batch)
                
                # Reduce original batch quantity
                batch.quantity -= remaining
                remaining = 0
        
        # Remove fully allocated batches from inventory
        for batch in batches_to_remove:
            try:
                self.inventory_batches.remove(batch)
            except ValueError:
                # Batch already removed (shouldn't happen but be safe)
                pass
        
        return allocated
    
    def _handle_retailer_delivery(self, truck: Truck, current_time: float, engine) -> Optional[Dict]:
        """
        Handle truck delivering cargo to retailer.
        
        Args:
            truck: Truck that arrived at retailer
            current_time: Current simulation time
            engine: SimulationEngine instance
            
        Returns:
            Delivery event dict
        """
        if not truck.assigned_order_id or not engine:
            return None
        
        # Find the order
        order = self.active_orders.get(truck.assigned_order_id)
        if not order:
            return None
        
        # Find the retailer
        retailer = None
        for r in engine.retailers:
            if r.retailer_id == order.retailer_id:
                retailer = r
                break
        
        if not retailer:
            return None
        
        # NEW: Quality check before delivery (configurable RSL threshold)
        cargo_batches = truck.cargo_batches
        accepted_batches = []
        rejected_batches = []
        
        # Get quality threshold from config
        min_rsl = self.config.get('quality_control', {}).get('min_acceptable_rsl_hours', 72.0)
        
        for batch in cargo_batches:
            if batch.is_acceptable_quality(min_rsl_hours=min_rsl):
                accepted_batches.append(batch)
            else:
                rejected_batches.append(batch)
        
        # If ALL batches rejected, delivery fails
        if rejected_batches and not accepted_batches:
            # Complete delivery failure - reorder needed
            truck.unload_cargo()  # Dispose of rejected cargo
            order.status = 'failed_quality_rejection'
            
            # CLEANUP: Remove failed order from active tracking
            if order.order_id in self.active_orders:
                self.completed_orders.append(order)  # Track as completed (failed)
                del self.active_orders[order.order_id]
            
            # Trigger automatic reorder from retailer
            retailer.trigger_emergency_reorder(order.quantity_kg, current_time, engine)
            
            # Set truck to return to warehouse
            try:
                from .truck_agent import TruckAgent
                agent = self.truck_agents[truck.truck_id]
                
                # Convert TruckType to dict for router
                truck_type_dict = {
                    'capacity_kg': truck.truck_type.capacity_kg,
                    'fuel_consumption_empty_l_per_100km': truck.truck_type.fuel_consumption_empty_l_per_100km,
                    'fuel_consumption_full_l_per_100km': truck.truck_type.fuel_consumption_full_l_per_100km,
                    'fuel_efficiency_by_speed': truck.truck_type.fuel_efficiency_by_speed
                }
                
                return_route = agent.router.find_path(
                    truck.current_node,
                    self.node_id,
                    truck_type_config=truck_type_dict,
                    load_fraction=0.0,  # Empty truck returning
                    avoid_blocked=True,
                    current_time=current_time
                )
                
                if return_route:
                    truck.current_route = return_route
                    truck.route_progress = 0
                    truck.segment_distance_traveled = 0.0
                    truck.destination_node = self.node_id
                    truck.status = "in_transit"
                    
                    logger.info(f"[DELIVERY FAILED] Truck {truck.truck_id} - all batches rejected at {retailer.retailer_id}, returning to {self.warehouse_id}")
            except Exception as e:
                logger.warning(f"Failed to route truck {truck.truck_id} back after rejection: {type(e).__name__}: {e}")
            
            return {
                'type': 'delivery_failed_quality_rejection',
                'truck_id': truck.truck_id,
                'warehouse_id': self.warehouse_id,
                'retailer_id': retailer.retailer_id,
                'order_id': order.order_id,
                'time': current_time,
                'rejected_batches': len(rejected_batches),
                'total_quantity_rejected_kg': sum(b.quantity for b in rejected_batches),
                'reason': 'insufficient_RSL'
            }
        
        # Partial or full acceptance
        if rejected_batches:
            # Log partial rejection
            logger.warning(f"[QUALITY] Partial rejection at {retailer.retailer_id}: "
                          f"{rejected_batches} batches rejected (RSL < 72hrs), {accepted_batches} accepted")
        
        # Deliver only accepted cargo to retailer
        delivery_qty = sum(b.quantity for b in accepted_batches) if accepted_batches else 0
        
        if delivery_qty > 0:
            retailer.receive_delivery(delivery_qty, current_time)
        
        # Unload all cargo (accepted delivered, rejected disposed)
        truck.unload_cargo()
        
        # Mark order status
        if rejected_batches:
            order.status = 'partially_delivered'
            # Retailer may need to reorder shortfall
            shortfall_kg = sum(b.quantity for b in rejected_batches)
            if shortfall_kg > 0:
                retailer.trigger_emergency_reorder(shortfall_kg, current_time, engine)
        else:
            order.mark_delivered(current_time)
        
        # Set truck to return to warehouse
        # Calculate route back to warehouse
        try:
            from .truck_agent import TruckAgent
            agent = self.truck_agents[truck.truck_id]
            
            # Convert TruckType to dict for router
            truck_type_dict = {
                'capacity_kg': truck.truck_type.capacity_kg,
                'fuel_consumption_empty_l_per_100km': truck.truck_type.fuel_consumption_empty_l_per_100km,
                'fuel_consumption_full_l_per_100km': truck.truck_type.fuel_consumption_full_l_per_100km,
                'fuel_efficiency_by_speed': truck.truck_type.fuel_efficiency_by_speed
            }
            
            return_route = agent.router.find_path(
                truck.current_node,
                self.node_id,
                truck_type_config=truck_type_dict,
                load_fraction=0.0,  # Empty truck returning
                avoid_blocked=True,
                current_time=current_time
            )
            
            if return_route:
                truck.current_route = return_route
                truck.route_progress = 0
                truck.segment_distance_traveled = 0.0
                truck.destination_node = self.node_id
                truck.status = "in_transit"
                
                logger.info(f"[DELIVERY] Truck {truck.truck_id} delivered {delivery_qty:.1f}kg to {retailer.retailer_id} "
                           f"(Order: {order.order_id}, Status: {'partial' if rejected_batches else 'complete'})")
                
                return {
                    'type': 'delivery_complete',
                    'truck_id': truck.truck_id,
                    'order_id': order.order_id,
                    'retailer_id': retailer.retailer_id,
                    'time': current_time,
                    'quantity_kg': delivery_qty
                }
        except Exception as e:
            # Routing failed, truck will stay at retailer
            logger.warning(f"[RETURN ROUTE FAILED] Truck {truck.truck_id}: Cannot calculate return route from "
                          f"retailer (Order: {order.order_id}) - {type(e).__name__}: {str(e)}")
        
        return None
    
    def _handle_truck_return(self, truck: Truck, current_time: float):
        """
        Handle truck returning to warehouse after delivery.
        
        Args:
            truck: Truck that returned
            current_time: Current simulation time
        """
        # Unload any remaining cargo (shouldn't be any after delivery)
        truck.unload_cargo()
        
        # Mark order as completed
        if truck.assigned_order_id and truck.assigned_order_id in self.active_orders:
            order = self.active_orders[truck.assigned_order_id]
            order.mark_delivered(current_time)
            self.completed_orders.append(order)
            del self.active_orders[truck.assigned_order_id]
            self.total_orders_fulfilled += 1
            
            logger.info(f"[RETURN] Truck {truck.truck_id} returned to {self.warehouse_id} "
                       f"(Order {truck.assigned_order_id} fulfilled, Total fulfilled: {self.total_orders_fulfilled})")
        
        # Reset truck status
        truck.status = "idle"
        truck.assigned_order_id = None
        truck.current_route = None
        truck.destination_node = None
        truck.route_progress = 0
        truck.segment_distance_traveled = 0.0
        
        # Refuel if needed
        if truck.is_low_fuel():
            truck.refuel()
        
        # OPTIMIZATION 8: Set flag for event-driven processing
        self.trucks_changed = True
    
    def restock(self, quantity_kg: float, current_time: float) -> Dict:
        """
        Receive restocking shipment.
        
        Args:
            quantity_kg: Quantity received
            current_time: Current simulation time
            
        Returns:
            Event dict
        """
        # Check capacity before restocking (NEW - Phase 2)
        if hasattr(self, 'max_capacity_kg'):
            available_capacity = self.max_capacity_kg - self.current_inventory_kg
            if quantity_kg > available_capacity:
                # Can only accept partial shipment
                accepted_qty = available_capacity
                rejected_qty = quantity_kg - available_capacity
                
                logger.warning(f"[CAPACITY] Warehouse {self.warehouse_id} at capacity! "
                              f"Rejecting {rejected_qty:.1f}kg (current: {self.current_inventory_kg:.0f}kg, "
                              f"max: {self.max_capacity_kg:.0f}kg)")
                
                quantity_kg = accepted_qty
                
                if quantity_kg <= 0:
                    return {
                        'type': 'restock_rejected',
                        'warehouse_id': self.warehouse_id,
                        'time': current_time,
                        'reason': 'at_max_capacity',
                        'current_inventory_kg': self.current_inventory_kg,
                        'max_capacity_kg': self.max_capacity_kg
                    }
        
        import datetime
        
        # Create batches for the restock (get from config)
        batch_size_kg = self.config.get('warehouse_operations', {}).get('batch_size_kg', 1000)
        num_batches = int(quantity_kg / batch_size_kg)
        remainder = quantity_kg % batch_size_kg
        
        for i in range(num_batches):
            batch = OrangeBatch(
                f"{self.warehouse_id}_batch_{self.batch_counter:04d}",
                batch_size_kg,  # quantity
                datetime.datetime.now(),  # harvest_date
                100.0  # initial_quality
            )
            self.inventory_batches.append(batch)
            self.batch_counter += 1
        
        # Handle remainder (if any)
        if remainder > 0:
            batch = OrangeBatch(
                f"{self.warehouse_id}_batch_{self.batch_counter:04d}",
                remainder,  # quantity
                datetime.datetime.now(),  # harvest_date
                100.0  # initial_quality
            )
            self.inventory_batches.append(batch)
            self.batch_counter += 1
        
        self.current_inventory_kg += quantity_kg
        self.pending_restock = False # Reset pending flag
        
        return {
            'type': 'warehouse_restock',
            'warehouse_id': self.warehouse_id,
            'time': current_time,
            'quantity_kg': quantity_kg,
            'new_inventory_kg': self.current_inventory_kg
        }
    
    def get_available_truck_count(self) -> int:
        """Get number of trucks currently available for assignment."""
        return sum(1 for truck in self.trucks 
                  if truck.status == "idle" and truck.current_node == self.node_id)
    
    def get_state(self) -> Dict:
        """
        Get current warehouse state for snapshot logging.
        
        Returns:
            Dictionary with warehouse state data
        """
        return {
            'warehouse_id': self.warehouse_id,
            'location': {'lat': self.location[0], 'lon': self.location[1]},
            'current_inventory_kg': round(self.current_inventory_kg, 2),
            'inventory_batches_count': len(self.inventory_batches),
            'total_trucks': len(self.trucks),
            'available_trucks': self.get_available_truck_count(),
            'trucks_in_transit': sum(1 for t in self.trucks if t.status == "in_transit"),
            'trucks_unloading': sum(1 for t in self.trucks if t.status in ["unloading", "unloading_complete"]),
            'pending_orders_count': len(self.pending_orders),
            'active_orders_count': len(self.active_orders),
            'total_orders_fulfilled': self.total_orders_fulfilled,
            'total_kg_shipped': round(self.total_kg_shipped, 2),
            'inventory_shortages': self.inventory_shortages,
            'pending_restock': self.pending_restock
        }
    
    def __repr__(self) -> str:
        return (f"WarehouseAgent(id={self.warehouse_id}, "
                f"inventory={self.current_inventory_kg:.0f}kg, "
                f"trucks={len(self.trucks)}, "
                f"available={self.get_available_truck_count()})")
