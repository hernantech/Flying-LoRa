import os
import yaml
import json
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache
from threading import Lock

class ConfigurationManager:
    """Thread-safe configuration manager with dynamic updates"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.env = os.getenv("FLASK_ENV", "development")
        self._config: Dict[str, Any] = {}
        self._lock = Lock()
        
        # Load configurations
        self.reload_config()
    
    def reload_config(self) -> None:
        """Reload all configuration files"""
        with self._lock:
            # Load base config
            base_config = self._load_yaml("base_config.yml")
            
            # Load environment-specific config
            env_config = self._load_yaml(f"{self.env}_config.yml")
            
            # Load secrets from environment or .env file
            secrets = self._load_secrets()
            
            # Merge configurations
            self._config = {
                **base_config,
                **env_config,
                **secrets
            }
    
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load and parse YAML configuration file"""
        try:
            config_path = self.config_dir / filename
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading {filename}: {e}")
        return {}
    
    def _load_secrets(self) -> Dict[str, str]:
        """Load secrets from environment variables"""
        secrets = {}
        
        # API keys
        secrets['API_KEY'] = os.getenv('API_KEY')
        secrets['JWT_SECRET'] = os.getenv('JWT_SECRET')
        
        # Database
        secrets['DB_USERNAME'] = os.getenv('DB_USERNAME')
        secrets['DB_PASSWORD'] = os.getenv('DB_PASSWORD')
        
        # Redis
        secrets['REDIS_URL'] = os.getenv('REDIS_URL')
        
        # Remove None values
        return {k: v for k, v in secrets.items() if v is not None}
    
    @lru_cache(maxsize=128)
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with caching"""
        with self._lock:
            return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Update configuration value"""
        with self._lock:
            self._config[key] = value
            # Clear the cache for this key
            self.get.cache_clear()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Batch update configuration values"""
        with self._lock:
            self._config.update(updates)
            # Clear entire cache as multiple values may have changed
            self.get.cache_clear()
    
    def save(self) -> None:
        """Save current configuration to file"""
        with self._lock:
            # Separate configs
            base_config = {}
            env_config = {}
            secrets = {}
            
            for key, value in self._config.items():
                if key.isupper():  # Secrets are uppercase
                    secrets[key] = value
                elif key.startswith(self.env):
                    env_config[key] = value
                else:
                    base_config[key] = value
            
            # Save base config
            self._save_yaml("base_config.yml", base_config)
            
            # Save environment config
            self._save_yaml(f"{self.env}_config.yml", env_config)
    
    def _save_yaml(self, filename: str, data: Dict[str, Any]) -> None:
        """Save configuration to YAML file"""
        try:
            config_path = self.config_dir / filename
            with open(config_path, 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving {filename}: {e}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get complete configuration (excluding secrets)"""
        with self._lock:
            # Filter out secret keys
            return {
                k: v for k, v in self._config.items()
                if not k.isupper()  # Secrets are uppercase
            }
    
    def validate(self) -> bool:
        """Validate current configuration"""
        required_keys = {
            'server.host',
            'server.port',
            'detection.enabled',
            'detection.model_path',
            'lora.device',
            'lora.frequency',
            'database.url',
            'redis.url'
        }
        
        with self._lock:
            return all(
                self.get(key) is not None
                for key in required_keys
            )

# Global configuration instance
config = ConfigurationManager() 