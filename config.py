import os
import yaml
import json
from typing import Any, Dict, Optional
from pathlib import Path
from functools import lru_cache
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from cryptography.fernet import Fernet

class ConfigChangeHandler(FileSystemEventHandler):
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def on_modified(self, event):
        if event.src_path == self.config_manager.config_file:
            self.config_manager.reload_config()

class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_dir: str = "config"):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / f"{os.getenv('ENV', 'development')}.yaml"
        self.secrets_file = self.config_dir / "secrets.enc"
        self.config: Dict[str, Any] = {}
        self._observers: list = []
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize encryption key
        self.key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher_suite = Fernet(self.key)
        
        # Load initial configuration
        self.reload_config()
        
        # Setup file watcher
        self._setup_file_watcher()

    def _setup_file_watcher(self):
        """Setup watchdog observer for config file changes"""
        self.observer = Observer()
        handler = ConfigChangeHandler(self)
        self.observer.schedule(handler, str(self.config_dir), recursive=False)
        self.observer.start()

    def reload_config(self):
        """Reload configuration from file"""
        with self._lock:
            try:
                if self.config_file.exists():
                    with open(self.config_file, 'r') as f:
                        self.config = yaml.safe_load(f)
                else:
                    self.config = self._create_default_config()
                
                # Load encrypted secrets
                self._load_secrets()
                
                # Notify observers
                self._notify_observers()
                
            except Exception as e:
                print(f"Error loading configuration: {e}")
                if not self.config:
                    self.config = self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        config = {
            'server': {
                'host': 'localhost',
                'port': 8000,
                'debug': True if os.getenv('ENV') == 'development' else False
            },
            'detection': {
                'model_path': 'models/detectnet.onnx',
                'confidence_threshold': 0.5,
                'max_frame_rate': 30,
                'gpu_memory_fraction': 0.6
            },
            'hardware': {
                'camera': {
                    'width': 1280,
                    'height': 720,
                    'fps': 30
                },
                'lora': {
                    'port': '/dev/ttyUSB0',
                    'baud_rate': 115200
                },
                'gpio': {
                    'status_led': 18,
                    'error_led': 23
                }
            },
            'resources': {
                'cpu_governor': 'ondemand',
                'gpu_freq_max': 1300500000,
                'power_mode': '10W',
                'thermal_throttle_temp': 80
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/flying_lora.log',
                'max_size_mb': 100,
                'backup_count': 5
            }
        }
        
        # Save default config
        self.save_config(config)
        return config

    def save_config(self, config: Dict[str, Any]):
        """Save configuration to file"""
        with self._lock:
            with open(self.config_file, 'w') as f:
                yaml.safe_dump(config, f)

    def _load_secrets(self):
        """Load encrypted secrets"""
        try:
            if self.secrets_file.exists():
                with open(self.secrets_file, 'rb') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                    secrets = json.loads(decrypted_data)
                    self.config['secrets'] = secrets
        except Exception as e:
            print(f"Error loading secrets: {e}")
            self.config['secrets'] = {}

    def save_secret(self, key: str, value: str):
        """Save an encrypted secret"""
        with self._lock:
            secrets = self.config.get('secrets', {})
            secrets[key] = value
            
            # Encrypt and save
            encrypted_data = self.cipher_suite.encrypt(json.dumps(secrets).encode())
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            self.config['secrets'] = secrets

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        try:
            value = self.config
            for k in key.split('.'):
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    @lru_cache(maxsize=100)
    def get_cached(self, key: str, default: Any = None) -> Any:
        """Get cached configuration value"""
        return self.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        with self._lock:
            keys = key.split('.')
            current = self.config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
            self.save_config(self.config)

    def register_observer(self, callback):
        """Register a callback for configuration changes"""
        if callback not in self._observers:
            self._observers.append(callback)

    def unregister_observer(self, callback):
        """Unregister a configuration change callback"""
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self):
        """Notify all observers of configuration changes"""
        for callback in self._observers:
            try:
                callback(self.config)
            except Exception as e:
                print(f"Error notifying observer: {e}")

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()

# Example usage
if __name__ == '__main__':
    # Get singleton instance
    config = ConfigManager()
    
    # Example: Register observer
    def config_changed(new_config):
        print("Configuration changed:", new_config)
    
    config.register_observer(config_changed)
    
    # Example: Get and set values
    print(config.get('server.host'))
    config.set('server.port', 8080)
    
    # Example: Save secret
    config.save_secret('api_key', 'secret_value')
    
    # Example: Get cached value
    cached_value = config.get_cached('server.port') 