"""Inventory management model with (s,S) policy and EOQ."""

import math
from typing import List, Tuple, Dict
from scipy import stats


class InventoryModel:
    """
    Research-backed inventory management using (s,S) continuous review policy.
    
    Key features:
    - Dynamic reorder point (s) based on demand variability
    - Order-up-to level (S) using EOQ or fixed days method
    - Safety stock calculation with service level
    - Exponential smoothing for demand forecasting
    """
    
    def __init__(self, config: Dict):
        """
        Initialize InventoryModel.
        
        Args:
            config: Inventory configuration from simulation_config.yaml
        """
        self.service_level = config['service_level']
        self.lead_time_mean = config['lead_time_days_mean'] * 24 * 60  # Convert to minutes
        self.lead_time_std = config['lead_time_days_std'] * 24 * 60
        self.review_period = config['review_period_hours'] * 60  # Convert to minutes
        
        # Order quantity method
        self.order_method = config['order_quantity_method']
        self.holding_cost = config.get('holding_cost_per_kg_per_day', 0.05)
        self.ordering_cost = config.get('ordering_cost_per_order', 50)
        self.order_up_to_days = config.get('order_up_to_days', 7)
        
        # Demand forecasting
        self.forecast_window = config['demand_forecast_window_days'] * 24 * 60  # Minutes
        self.smoothing_alpha = config['demand_smoothing_alpha']
        
        # Constraints
        self.min_order_qty = config['min_order_quantity_kg']
        self.max_order_qty = config['max_order_quantity_kg']
        
        # State tracking
        self.demand_history: List[Tuple[float, float]] = []  # (time, quantity)
        self.forecasted_demand_rate = 0.0  # kg per minute
        self.demand_std = 0.0  # Standard deviation of demand
        
        # Z-score for service level (e.g., 95% -> 1.65)
        self.z_score = stats.norm.ppf(self.service_level)
        
    def record_demand(self, time: float, quantity: float):
        """
        Record a demand occurrence for forecasting.
        
        Args:
            time: Simulation time
            quantity: Quantity demanded in kg
        """
        self.demand_history.append((time, quantity))
        
        # Keep only recent history (within forecast window)
        cutoff_time = time - self.forecast_window
        self.demand_history = [
            (t, q) for t, q in self.demand_history if t >= cutoff_time
        ]
        
        # Update forecast
        self._update_forecast()
    
    def _update_forecast(self):
        """Update demand forecast using exponential smoothing."""
        if len(self.demand_history) < 2:
            return
        
        # Calculate demand rate (kg per minute) from recent history
        if len(self.demand_history) > 0:
            total_quantity = sum(q for _, q in self.demand_history)
            time_span = self.demand_history[-1][0] - self.demand_history[0][0]
            
            if time_span > 0:
                observed_rate = total_quantity / time_span
                
                # Exponential smoothing
                if self.forecasted_demand_rate == 0:
                    self.forecasted_demand_rate = observed_rate
                else:
                    self.forecasted_demand_rate = (
                        self.smoothing_alpha * observed_rate +
                        (1 - self.smoothing_alpha) * self.forecasted_demand_rate
                    )
        
        # Calculate standard deviation of demand
        if len(self.demand_history) >= 10:
            quantities = [q for _, q in self.demand_history]
            self.demand_std = math.sqrt(sum((q - sum(quantities)/len(quantities))**2 
                                           for q in quantities) / len(quantities))
    
    def calculate_reorder_point(self) -> float:
        """
        Calculate reorder point (s) based on lead time and demand variability.
        
        Formula: s = demand_during_lead_time + safety_stock
        where safety_stock = z * std_demand * sqrt(lead_time + review_period)
        
        Returns:
            Reorder point in kg
        """
        # Expected demand during lead time
        demand_during_lead_time = self.forecasted_demand_rate * self.lead_time_mean
        
        # Safety stock calculation
        # Accounts for demand variability during lead time + review period
        protection_period = self.lead_time_mean + self.review_period
        
        if self.demand_std > 0:
            safety_stock = self.z_score * self.demand_std * math.sqrt(protection_period / 60)
        else:
            # If no variability data, use 20% of expected demand as safety stock
            safety_stock = 0.2 * demand_during_lead_time
        
        reorder_point = demand_during_lead_time + safety_stock
        
        return max(self.min_order_qty, reorder_point)
    
    def calculate_order_up_to_level(self) -> float:
        """
        Calculate order-up-to level (S) using EOQ or fixed days method.
        
        Returns:
            Order-up-to level in kg
        """
        if self.order_method == "EOQ":
            return self._calculate_eoq_order_level()
        else:
            return self._calculate_fixed_days_order_level()
    
    def _calculate_eoq_order_level(self) -> float:
        """
        Calculate order-up-to level using Economic Order Quantity.
        
        EOQ formula: sqrt((2 * D * K) / h)
        where D = annual demand, K = ordering cost, h = holding cost
        
        S = s + EOQ
        """
        # Convert demand rate to annual (kg per year)
        annual_demand = self.forecasted_demand_rate * 365 * 24 * 60
        
        if annual_demand > 0 and self.holding_cost > 0:
            # EOQ calculation
            eoq = math.sqrt(
                (2 * annual_demand * self.ordering_cost) / 
                (self.holding_cost * 365)
            )
            
            # S = reorder point + EOQ
            s = self.calculate_reorder_point()
            order_up_to = s + eoq
        else:
            # Fallback to fixed days method
            order_up_to = self._calculate_fixed_days_order_level()
        
        # Apply constraints
        return max(self.min_order_qty, min(self.max_order_qty, order_up_to))
    
    def _calculate_fixed_days_order_level(self) -> float:
        """
        Calculate order-up-to level based on fixed days of demand.
        
        S = demand for order_up_to_days + safety_stock
        """
        # Demand for specified days
        demand_for_period = self.forecasted_demand_rate * self.order_up_to_days * 24 * 60
        
        # Add safety stock
        protection_period = self.lead_time_mean + self.review_period
        if self.demand_std > 0:
            safety_stock = self.z_score * self.demand_std * math.sqrt(protection_period / 60)
        else:
            safety_stock = 0.2 * demand_for_period
        
        order_up_to = demand_for_period + safety_stock
        
        # Apply constraints
        return max(self.min_order_qty, min(self.max_order_qty, order_up_to))
    
    def should_reorder(self, current_inventory: float) -> bool:
        """
        Check if inventory has fallen below reorder point.
        
        Args:
            current_inventory: Current inventory level in kg
            
        Returns:
            True if should place order, False otherwise
        """
        reorder_point = self.calculate_reorder_point()
        return current_inventory <= reorder_point
    
    def calculate_order_quantity(self, current_inventory: float) -> float:
        """
        Calculate order quantity to bring inventory up to S.
        
        Args:
            current_inventory: Current inventory level in kg
            
        Returns:
            Order quantity in kg
        """
        order_up_to = self.calculate_order_up_to_level()
        order_qty = order_up_to - current_inventory
        
        # Apply constraints
        if order_qty < self.min_order_qty:
            return 0.0  # Don't order if below minimum
        
        return min(self.max_order_qty, order_qty)
    
    def __repr__(self) -> str:
        return (f"InventoryModel(method={self.order_method}, "
                f"service_level={self.service_level:.0%}, "
                f"forecast_rate={self.forecasted_demand_rate:.2f} kg/min)")
