"""
Test Weather Humidity and States (Debug Mode)
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.simulation.models.weather_model import WeatherModel

def test_weather_debug():
    print("DEBUG: Starting Weather Test", flush=True)
    
    config = {'weather': {}}
    weather = WeatherModel(config)
    
    # CASE 1: SUMMER (May) - Should be mostly Clear
    print("\n--- TEST: SUMMER (Month 5) ---", flush=True)
    rain_count = 0
    total_runs = 50
    
    print(f"Probabilities default: {weather.default_probs}", flush=True)
    
    for i in range(total_runs):
        weather.state_duration = 0 # Force change
        weather.update(current_time=i*1000, month=5, hour=14.0)
        
        state = weather.current_state
        if state != 'clear':
            # Only print non-clear to reduce spam, unless it's broken
            pass
        
        if state in ['rain', 'heavy_rain', 'light_rain']:
            rain_count += 1
            
    print(f"Summer Rain Count: {rain_count}/{total_runs}", flush=True)
    
    # CASE 2: WINTER (Jan) - Morning Fog
    print("\n--- TEST: WINTER MORNING (Month 1, 05:00) ---", flush=True)
    fog_count = 0
    total_runs = 50
    
    for i in range(total_runs):
        weather.state_duration = 0
        weather.update(current_time=i*1000, month=1, hour=5.0)
        
        state = weather.current_state
        if state == 'fog':
            fog_count += 1
            
    print(f"Winter Fog Count: {fog_count}/{total_runs}", flush=True)

    # CASE 3: MONSOON (July) - Rain
    print("\n--- TEST: MONSOON (Month 7) ---", flush=True)
    rain_count = 0
    humidities = []
    
    for i in range(total_runs):
        weather.state_duration = 0
        weather.update(current_time=i*1000, month=7, hour=14.0)
        
        state = weather.current_state
        if state in ['rain', 'heavy_rain', 'light_rain']:
            rain_count += 1
        humidities.append(weather.get_humidity(7, 14.0))

    avg_h = sum(humidities)/len(humidities)
    print(f"Monsoon Rain Count: {rain_count}/{total_runs}", flush=True)
    print(f"Monsoon Avg Humidity: {avg_h:.1f}%", flush=True)

if __name__ == "__main__":
    test_weather_debug()
