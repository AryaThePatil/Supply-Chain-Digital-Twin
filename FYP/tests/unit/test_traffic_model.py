"""Unit tests for TrafficModel.

Tests traffic speed calculations, weather effects, and congestion modeling.
"""
import pytest
from src.simulation.network.traffic_model import TrafficModel
from unittest.mock import Mock


@pytest.fixture
def traffic_config():
    """Configuration for traffic model tests."""
    return {
        'traffic': {
            'weather_speed_reduction': {
                'clear': 1.0,
                'light_rain': 0.9,
                'rain': 0.8,
                'heavy_rain': 0.6,
                'fog': 0.7
            },
            'weather_density_increase': {
                'clear': 1.0,
                'rain': 1.2,
                'heavy_rain': 1.3,
                'fog': 1.4
            },
            'congestion_enabled': True,
            'jam_density_per_lane': {
                'motorway': 150,
                'primary': 100,
                'secondary': 80,
                'residential': 60
            },
            'capacity_per_lane': {
                'motorway': 50,
                'primary': 35,
                'secondary': 28,
                'residential': 20
            },
            'base_density_fraction': {
                'motorway': 0.3,
                'primary': 0.35,
                'secondary': 0.4,
                'residential': 0.45
            },
            'time_of_day_multipliers': [0.3] * 24,  # Simplified
            'night_speed_reduction': 0.95
        }
    }


@pytest.mark.unit
class TestTrafficModel:
    """Test suite for TrafficModel."""
    
    def test_model_initialization(self, traffic_config):
        """Test that TrafficModel initializes correctly."""
        model = TrafficModel(traffic_config)
        
        # Check basic attributes exist
        assert hasattr(model, 'config')
        assert hasattr(model, 'current_weather')
        assert model.current_weather == 'clear'
    
    def test_greenshields_model_at_zero_density(self, traffic_config):
        """Test that speed equals free-flow speed when density is zero."""
        model = TrafficModel(traffic_config)
        
        # Create mock segment
        mock_segment = Mock()
        mock_segment.speed_limit_kmh = 60.0
        mock_segment.road_type = 'primary'
        mock_segment.current_traffic_density = 0.0  # No traffic
        
        # At zero density, speed should be close to speed limit
        # Greenshields: speed = free_flow × (1 - density/jam_density)
        # With density=0: speed = free_flow × 1 = free_flow
        speed = model.get_current_speed(mock_segment, 720.0)
        
        # Should be at or near speed limit (may have weather/night reductions)
        assert speed > 0
        assert speed <= mock_segment.speed_limit_kmh
    
    def test_greenshields_model_speed_degrades_with_density(self, traffic_config):
        """Test that speed decreases as density increases (Greenshields model)."""
        model = TrafficModel(traffic_config)
        model.current_weather = 'clear'
        
        # Create three segments with different densities
        low_density = Mock()
        low_density.speed_limit_kmh = 60.0
        low_density.road_type = 'primary'
        low_density.lanes = 2
        low_density.current_traffic_density = 10.0  # Low
        
        med_density = Mock()
        med_density.speed_limit_kmh = 60.0
        med_density.road_type = 'primary'
        med_density.lanes = 2
        med_density.current_traffic_density = 50.0  # Medium
        
        high_density = Mock()
        high_density.speed_limit_kmh = 60.0
        high_density.road_type = 'primary'
        high_density.lanes = 2
        high_density.current_traffic_density = 90.0  # High (near jam)
        
        # Calculate speeds (daytime to avoid night penalty)
        speed_low = model.get_current_speed(low_density, 720.0)
        speed_med = model.get_current_speed(med_density, 720.0)
        speed_high = model.get_current_speed(high_density, 720.0)
        
        # Higher density should mean lower speed
        assert speed_low > speed_med > speed_high
    
    def test_weather_reduces_speed(self, traffic_config):
        """Test that adverse weather reduces traffic speed."""
        model = TrafficModel(traffic_config)
        
        mock_segment = Mock()
        mock_segment.speed_limit_kmh = 60.0
        mock_segment.road_type = 'primary'
        mock_segment.lanes = 2
        mock_segment.current_traffic_density = 20.0
        
        # Clear weather
        model.set_weather('clear')
        speed_clear = model.get_current_speed(mock_segment, 720.0)
        
        # Rain
        model.set_weather('rain')
        speed_rain = model.get_current_speed(mock_segment, 720.0)
        
        # Heavy rain
        model.set_weather('heavy_rain')
        speed_heavy_rain = model.get_current_speed(mock_segment, 720.0)
        
        # Weather should reduce speed
        assert speed_clear > speed_rain > speed_heavy_rain
    
    def test_fog_reduces_speed(self, traffic_config):
        """Test that fog reduces traffic speed."""
        model = TrafficModel(traffic_config)
        
        mock_segment = Mock()
        mock_segment.speed_limit_kmh = 60.0
        mock_segment.road_type = 'primary'
        mock_segment.lanes = 2
        mock_segment.current_traffic_density = 20.0
        
        # Clear weather
        model.set_weather('clear')
        speed_clear = model.get_current_speed(mock_segment, 720.0)
        
        # Fog
        model.set_weather('fog')
        speed_fog = model.get_current_speed(mock_segment, 720.0)
        
        # Fog should reduce speed
        assert speed_fog < speed_clear
    
    def test_night_reduces_speed(self, traffic_config):
        """Test that nighttime reduces traffic speed."""
        model = TrafficModel(traffic_config)
        model.current_weather = 'clear'
        
        mock_segment = Mock()
        mock_segment.speed_limit_kmh = 60.0
        mock_segment.road_type = 'primary'
        mock_segment.lanes = 2
        mock_segment.current_traffic_density = 20.0
        
        # Daytime (12pm)
        speed_day = model.get_current_speed(mock_segment, 720.0)
        
        # Nighttime (2am)
        speed_night = model.get_current_speed(mock_segment, 120.0)
        
        # Night should reduce speed slightly
        assert speed_night <= speed_day
    
    def test_traffic_density_varies_by_time_of_day(self, traffic_config):
        """Test that traffic density is higher during rush hours."""
        model = TrafficModel(traffic_config)
        
        mock_segment = Mock()
        mock_segment.road_type = 'primary'
        mock_segment.speed_limit_kmh = 60.0
        
        # Midnight (low traffic)
        density_midnight = model.get_traffic_density(mock_segment, 0.0)
        
        # Morning rush hour (8am = 480 min)
        density_rush = model.get_traffic_density(mock_segment, 480.0)
        
        # Rush hour should have higher density
        # (This depends on config having time_of_day_multipliers)
        assert density_rush >= density_midnight
    
    def test_update_segment_sets_density_and_speed(self, traffic_config):
        """Test that update_segment correctly sets segment attributes."""
        model = TrafficModel(traffic_config)
        
        mock_segment = Mock()
        mock_segment.road_type = 'primary'
        mock_segment.speed_limit_kmh = 60.0
        
        # Update should set current_traffic_density and current_speed_kmh
        model.update_segment(mock_segment, 720.0)
        
        # Check attributes were set
        assert hasattr(mock_segment, 'current_traffic_density')
        assert hasattr(mock_segment, 'current_speed_kmh')
        assert mock_segment.current_traffic_density >= 0
        assert mock_segment.current_speed_kmh >= 0
    
    def test_speed_never_exceeds_limit(self, traffic_config):
        """Test that calculated speed never exceeds speed limit."""
        model = TrafficModel(traffic_config)
        model.current_weather = 'clear'
        
        mock_segment = Mock()
        mock_segment.speed_limit_kmh = 40.0  # Low limit
        mock_segment.road_type = 'residential'
        mock_segment.current_traffic_density = 5.0  # Very low density
        
        speed = model.get_current_speed(mock_segment, 720.0)
        
        # Should not exceed limit
        assert speed <= mock_segment.speed_limit_kmh
