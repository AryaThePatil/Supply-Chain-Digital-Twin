"""Unit tests for OrangeBatch entity.

Tests the remaining shelf life (RSL) degradation model for orange cargo,
including temperature effects, humidity impacts, and spoilage detection.
"""
import pytest
from datetime import datetime, timedelta
from src.simulation.entities.orange_batch import OrangeBatch


@pytest.mark.unit
class TestOrangeBatch:
    """Test suite for OrangeBatch entity."""
    
    def test_batch_initialization(self):
        """Test that batch initializes with correct values."""
        harvest_date = datetime(2024, 11, 15)
        batch = OrangeBatch(
            batch_id='TEST_001',
            quantity=1000.0,
            harvest_date=harvest_date
        )
        
        # Check initial values
        assert batch.batch_id == 'TEST_001'
        assert batch.quantity == 1000.0
        assert batch.harvest_date == harvest_date
        assert batch.current_rsl == 100.0, "RSL should start at 100.0 (100%)"
        assert not batch.is_spoiled(), "Fresh batch should not be spoiled"
    
    def test_rsl_degradation_at_optimal_conditions(self):
        """Test RSL degrades slowly at optimal storage conditions."""
        batch = OrangeBatch(
            batch_id='TEST_OPTIMAL',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        initial_rsl = batch.current_rsl
        
        # Simulate 7 days at optimal conditions (4°C, 88% RH)
        for day in range(7):
            current_time = day * 1440  # minutes
            batch.update_rsl(4.0, 88.0, current_time)  # temp, humidity, time
        
        # RSL should have decreased but not dramatically
        assert batch.current_rsl < initial_rsl, "RSL should decrease over time"
        assert batch.current_rsl > 40.0, "At optimal conditions, RSL should still be reasonable after 7 days"
        assert not batch.is_spoiled(), "Should not spoil at optimal conditions in 7 days"
    
    def test_rsl_degradation_at_high_temp(self):
        """Test RSL degrades faster at high temperature (Q10 effect)."""
        # Create two identical batches
        batch_cold = OrangeBatch(
            batch_id='COLD',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        batch_hot = OrangeBatch(
            batch_id='HOT',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        # Age both for 3 days at different temperatures
        for day in range(3):
            current_time = day * 1440
            
            # Cold storage (4°C, optimal)
            batch_cold.update_rsl(4.0, 88.0, current_time)
            
            # Hot conditions (30°C, canvas truck in summer)
            batch_hot.update_rsl(30.0, 88.0, current_time)
        
        # Hot batch should degrade MUCH faster
        assert batch_hot.current_rsl < batch_cold.current_rsl, \
            "High temperature should cause faster degradation"
        
        # Should see significant difference (Q10 effect)
        degradation_ratio = (100.0 - batch_hot.current_rsl) / (100.0 - batch_cold.current_rsl)
        assert degradation_ratio > 2.0, \
            f"Hot degradation should be at least 2x faster (ratio: {degradation_ratio})"
    
    def test_rsl_degradation_low_humidity(self):
        """Test RSL degrades faster at low humidity (dehydration)."""
        batch_low_humidity = OrangeBatch(
            batch_id='DRY',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        batch_optimal = OrangeBatch(
            batch_id='OPTIMAL',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        # Age both for 5 days
        for day in range(5):
            current_time = day * 1440
            
            # Low humidity (60%, dehydration risk)
            batch_low_humidity.update_rsl(20.0, 60.0, current_time)
            
            # Optimal humidity (88%)
            batch_optimal.update_rsl(20.0, 88.0, current_time)
        
        # Low humidity should cause faster degradation
        assert batch_low_humidity.current_rsl < batch_optimal.current_rsl, \
            "Low humidity should cause faster degradation (dehydration)"
    
    def test_rsl_degradation_high_humidity(self):
        """Test RSL degrades faster at very high humidity (mold risk)."""
        batch_high_humidity = OrangeBatch(
            batch_id='MOLD',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        batch_optimal = OrangeBatch(
            batch_id='OPTIMAL',
            quantity=500.0,
            harvest_date=datetime(2024, 11, 1)
        )
        
        # Age both for 5 days
        for day in range(5):
            current_time = day * 1440
            
            # Very high humidity (98%, mold risk)
            batch_high_humidity.update_rsl(20.0, 98.0, current_time)
            
            # Optimal humidity (88%)
            batch_optimal.update_rsl(20.0, 88.0, current_time)
        
        # High humidity should cause faster degradation
        assert batch_high_humidity.current_rsl < batch_optimal.current_rsl, \
            "Very high humidity should cause faster degradation (mold risk)"
    
    def test_spoilage_detection(self):
        """Test that batch correctly identifies spoiled cargo."""
        batch = OrangeBatch(
            batch_id='SPOIL_TEST',
            quantity=300.0,
            harvest_date=datetime(2024, 10, 1)  # Old harvest
        )
        
        # Should start not spoiled
        assert not batch.is_spoiled(), "Fresh batch should not be spoiled"
        
        # Age at bad conditions until spoiled
        for day in range(40):
            current_time = day * 1440
            batch.update_rsl(35.0, 95.0, current_time)  # Hot and humid
            
            if batch.is_spoiled():
                break
        
        # Should eventually spoil
        assert batch.is_spoiled(), "Batch should spoil under bad conditions"
        assert batch.current_rsl <= 0, "Spoiled batch should have RSL <= 0"
    
    def test_rsl_never_goes_negative(self):
        """Test that RSL is clamped to 0 and doesn't go negative."""
        batch = OrangeBatch(
            batch_id='CLAMP_TEST',
            quantity=200.0,
            harvest_date=datetime(2024, 9, 1)  # Very old
        )
        
        # Age aggressively
        for day in range(60):
            current_time = day * 1440
            batch.update_rsl(40.0, 98.0, current_time)  # Terrible conditions
        
        # RSL should be clamped to 0, not negative
        assert batch.current_rsl >= 0.0, "RSL should never be negative"
        assert batch.current_rsl <= 100.0, "RSL should never exceed 100.0"
    
    def test_rsl_decreases_monotonically(self):
        """Test that RSL only decreases, never increases."""
        batch = OrangeBatch(
            batch_id='MONOTONIC',
            quantity=400.0,
            harvest_date=datetime(2024, 11, 10)
        )
        
        previous_rsl = batch.current_rsl
        
        # Age over time with varying conditions
        for day in range(10):
            current_time = day * 1440
            # Alternate between good and bad conditions
            temp = 10.0 if day % 2 == 0 else 25.0
            humidity = 88.0 if day % 2 == 0 else 70.0
            
            batch.update_rsl(temp, humidity, current_time)
            
            # RSL should never increase
            assert batch.current_rsl <= previous_rsl, \
                f"RSL increased from {previous_rsl} to {batch.current_rsl} on day {day}"
            previous_rsl = batch.current_rsl
    
    def test_extreme_temperature_handling(self):
        """Test that batch handles extreme temperatures gracefully."""
        batch_freezing = OrangeBatch(
            batch_id='FREEZE',
            quantity=100.0,
            harvest_date=datetime(2024, 11, 15)
        )
        
        batch_scorching = OrangeBatch(
            batch_id='SCORCH',
            quantity=100.0,
            harvest_date=datetime(2024, 11, 15)
        )
        
        # Test extreme temperatures
        for day in range(3):
            current_time = day * 1440
            
            # Freezing (damages cells)
            batch_freezing.update_rsl(0.0, 88.0, current_time)
            
            # Scorching hot
            batch_scorching.update_rsl(50.0, 88.0, current_time)
        
        # Both should degrade (no crashes)
        assert batch_freezing.current_rsl < 100.0
        assert batch_scorching.current_rsl < 100.0
        assert batch_scorching.current_rsl < batch_freezing.current_rsl, \
            "Extreme heat should degrade faster than cold"
    
    def test_harvest_date_tracking(self):
        """Test that harvest date is correctly stored and used."""
        harvest_date = datetime(2024, 11, 1, 8, 30)  # Nov 1, 8:30am
        batch = OrangeBatch(
            batch_id='DATE_TEST',
            quantity=600.0,
            harvest_date=harvest_date
        )
        
        assert batch.harvest_date == harvest_date, "Harvest date should be stored correctly"
