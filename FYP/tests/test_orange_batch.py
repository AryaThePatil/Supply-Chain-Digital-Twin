"""Unit tests for OrangeBatch spoilage model."""

import pytest
import math
from datetime import datetime
from src.simulation.entities.orange_batch import OrangeBatch


class TestOrangeBatch:
    """Test OrangeBatch entity and spoilage modeling."""
    
    def test_orange_batch_initialization(self):
        """Test OrangeBatch is initialized with correct attributes."""
        harvest_date = datetime(2024, 1, 1)
        
        batch = OrangeBatch(
            batch_id="batch-001",
            quantity=100,
            harvest_date=harvest_date,
            initial_quality=100.0
        )
        
        assert batch.batch_id == "batch-001"
        assert batch.quantity == 100
        assert batch.harvest_date == harvest_date
        assert batch.initial_quality == 100.0
        assert batch.current_rsl == 100.0
        assert batch.last_update_time == 0
    
    def test_arrhenius_equation_calculation(self):
        """Test Arrhenius equation calculation with known temperature."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        # Test at 4°C (refrigerated temperature)
        temperature_celsius = 4.0
        temperature_kelvin = temperature_celsius + 273.15  # 277.15 K
        
        # Expected degradation rate: k = 1.4e9 * exp(-7456/T)
        expected_k = 1.4e9 * math.exp(-7456 / temperature_kelvin)
        
        # Update RSL for 1 time unit
        batch.update_rsl(temperature_celsius, 1.0)
        
        # Expected RSL after 1 time unit
        expected_rsl = 100.0 - expected_k * 1.0
        
        assert abs(batch.current_rsl - expected_rsl) < 0.01
        assert batch.last_update_time == 1.0
    
    def test_rsl_degradation_over_time(self):
        """Test RSL degrades over time at constant temperature."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        temperature = 4.0  # Refrigerated temperature
        
        # Update RSL multiple times
        batch.update_rsl(temperature, 10.0)
        rsl_after_10 = batch.current_rsl
        
        batch.update_rsl(temperature, 20.0)
        rsl_after_20 = batch.current_rsl
        
        batch.update_rsl(temperature, 30.0)
        rsl_after_30 = batch.current_rsl
        
        # RSL should decrease over time
        assert rsl_after_10 < 100.0
        assert rsl_after_20 < rsl_after_10
        assert rsl_after_30 < rsl_after_20
    
    def test_higher_temperature_faster_degradation(self):
        """Test that higher temperature causes faster degradation."""
        harvest_date = datetime(2024, 1, 1)
        
        # Create two batches
        batch_cold = OrangeBatch("batch-cold", 100, harvest_date)
        batch_warm = OrangeBatch("batch-warm", 100, harvest_date)
        
        # Update at different temperatures for same duration
        batch_cold.update_rsl(4.0, 100.0)  # Refrigerated
        batch_warm.update_rsl(20.0, 100.0)  # Room temperature
        
        # Warmer batch should have lower RSL
        assert batch_warm.current_rsl < batch_cold.current_rsl
    
    def test_rsl_clamped_to_zero(self):
        """Test RSL is clamped to 0 (cannot go negative)."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        # Set RSL to very low value
        batch.current_rsl = 0.5
        batch.last_update_time = 0
        
        # Update with high temperature for long time to force negative
        batch.update_rsl(30.0, 10000.0)
        
        # RSL should be clamped to 0
        assert batch.current_rsl == 0.0
        assert batch.current_rsl >= 0.0
    
    def test_rsl_clamped_to_hundred(self):
        """Test RSL is clamped to 100 (cannot exceed initial)."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        # Manually set RSL above 100 (shouldn't happen in practice)
        batch.current_rsl = 105.0
        batch.last_update_time = 0
        
        # Update with very low temperature (minimal degradation)
        batch.update_rsl(-10.0, 0.1)
        
        # RSL should be clamped to 100
        assert batch.current_rsl <= 100.0
    
    def test_spoilage_detection_threshold(self):
        """Test spoilage detection when RSL reaches 0."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        # Fresh batch should not be spoiled
        assert not batch.is_spoiled()
        
        # Set RSL to 0
        batch.current_rsl = 0.0
        assert batch.is_spoiled()
        
        # Set RSL to slightly above 0
        batch.current_rsl = 0.1
        assert not batch.is_spoiled()
    
    def test_multiple_updates_accumulate(self):
        """Test that multiple RSL updates accumulate correctly."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        temperature = 4.0
        
        # Update in small increments
        batch.update_rsl(temperature, 10.0)
        batch.update_rsl(temperature, 20.0)
        batch.update_rsl(temperature, 30.0)
        
        rsl_incremental = batch.current_rsl
        
        # Create new batch and update in one go
        batch2 = OrangeBatch("batch-002", 100, harvest_date)
        batch2.update_rsl(temperature, 30.0)
        
        rsl_single = batch2.current_rsl
        
        # Results should be approximately equal
        assert abs(rsl_incremental - rsl_single) < 0.01
    
    def test_zero_time_elapsed_no_degradation(self):
        """Test that no degradation occurs when time elapsed is zero."""
        harvest_date = datetime(2024, 1, 1)
        batch = OrangeBatch("batch-001", 100, harvest_date)
        
        # Update at time 0 (no time elapsed)
        batch.update_rsl(4.0, 0.0)
        
        # RSL should remain at 100
        assert batch.current_rsl == 100.0
