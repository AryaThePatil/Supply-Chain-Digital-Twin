"""
Configuration loader for FYP Digital Twin
Centralizes all hardcoded values into YAML config files
"""
import yaml
from pathlib import Path
from typing import Any, Dict


class Config:
    """Singleton configuration loader"""
    _instance = None
    
    def __init__(self):
        """Load configuration files"""
        # Get project root (FYP directory)
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config"
        
        # Load simulation defaults
        sim_config_path = config_dir / "simulation_defaults.yaml"
        if sim_config_path.exists():
            try:
                with open(sim_config_path, 'r') as f:
                    self.simulation = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"[WARNING]  Error parsing {sim_config_path}: {e}")
                print(f"   Using default simulation config")
                self.simulation = self._get_default_simulation_config()
            except (FileNotFoundError, PermissionError) as e:
                # File access errors
                print(f"[WARNING]  Could not access config file: {e}")
                print(f"   Using default simulation config")
                self.simulation = self._get_default_simulation_config()
            except Exception as e:
                # Unexpected errors
                print(f"[WARNING]  Unexpected error loading {sim_config_path}: {type(e).__name__}: {e}")
                print(f"   Using default simulation config")
                self.simulation = self._get_default_simulation_config()
        else:
            self.simulation = self._get_default_simulation_config()
        
        # Load API config
        api_config_path = config_dir / "api.yaml"
        if api_config_path.exists():
            try:
                with open(api_config_path, 'r') as f:
                    self.api = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"[WARNING]  Error parsing {api_config_path}: {e}")
                print(f"   Using default API config")
                self.api = self._get_default_api_config()
            except (FileNotFoundError, PermissionError) as e:
                # File access errors
                print(f"[WARNING]  Could not access API config file: {e}")
                print(f"   Using default API config")
                self.api = self._get_default_api_config()
            except Exception as e:
                # Unexpected errors
                print(f"[WARNING]  Unexpected error loading {api_config_path}: {type(e).__name__}: {e}")
                print(f"   Using default API config")
                self.api = self._get_default_api_config()
        else:
            self.api = self._get_default_api_config()
    
    @classmethod
    def load(cls) -> 'Config':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @staticmethod
    def _get_default_simulation_config() -> Dict[str, Any]:
        """Fallback defaults if config file missing"""
        return {
            'weather': {
                'defaults': {'humidity': 50.0, 'temperature': 25.0}
            },
            'network': {
                'road_quality_penalties': {
                    'dirt': 10.0, 'unpaved': 5.0, 'primary': 0.0,
                    'secondary': 1.0, 'tertiary': 2.0, 'residential': 3.0
                },
                'min_speed_kmh': 1.0
            }
        }
    
    @staticmethod
    def _get_default_api_config() -> Dict[str, Any]:
        """Fallback defaults for API"""
        return {
            'cors': {
                'allowed_origins': ['http://localhost:5173']
            },
            'pagination': {
                'default_limit': 50,
                'max_limit': 1000
            }
        }
    
    def get(self, path: str, default=None):
        """
        Get config value by dot path
        Example: config.get('network.road_quality_penalties.dirt')
        """
        keys = path.split('.')
        value = self.simulation
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default


# Global config instance
config = Config.load()


# Convenience functions
def get_road_penalty(surface: str) -> float:
    """Get road quality penalty for surface type"""
    penalties = config.simulation.get('network', {}).get('road_quality_penalties', {})
    return penalties.get(surface, 3.0)  # Default to residential penalty


def get_weather_defaults() -> Dict[str, float]:
    """Get default weather values"""
    return config.simulation.get('weather', {}).get('defaults', {
        'humidity': 50.0,
        'temperature': 25.0
    })
