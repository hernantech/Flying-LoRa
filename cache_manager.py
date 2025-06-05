import json
import time
import logging
import threading
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import redis
from config import ConfigManager
from logging_config import LoggerSetup

class CacheManager:
    def __init__(self):
        # Initialize configuration and logging
        self.config = ConfigManager()
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Redis configuration
        redis_config = {
            'host': self.config.get('cache.redis.host', 'localhost'),
            'port': self.config.get('cache.redis.port', 6379),
            'db': self.config.get('cache.redis.db', 0),
            'password': self.config.get('cache.redis.password', None),
            'decode_responses': True  # Automatically decode responses to Python objects
        }
        
        # Initialize Redis connection
        self.redis = redis.Redis(**redis_config)
        
        # Cache configuration
        self.default_ttl = self.config.get('cache.default_ttl', 3600)  # 1 hour
        self.max_memory = self.config.get('cache.max_memory_mb', 512)  # MB
        
        # Configure Redis memory limits
        self._configure_redis()
        
        # Start background tasks
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._periodic_cleanup)
        self.cleanup_thread.start()

    def _configure_redis(self):
        """Configure Redis settings"""
        try:
            # Set memory limit
            self.redis.config_set('maxmemory', f'{self.max_memory}mb')
            # Set eviction policy (LRU for volatile keys)
            self.redis.config_set('maxmemory-policy', 'volatile-lru')
            
        except redis.RedisError as e:
            self.logger.error(f"Failed to configure Redis: {e}")

    def set_detection_result(self, detection_id: str, result: Dict,
                           ttl: Optional[int] = None) -> bool:
        """Cache detection results with TTL"""
        try:
            key = f"detection:{detection_id}"
            return self._set_with_ttl(key, result, ttl)
            
        except Exception as e:
            self.logger.error(f"Failed to cache detection result: {e}")
            return False

    def get_detection_result(self, detection_id: str) -> Optional[Dict]:
        """Retrieve cached detection result"""
        try:
            key = f"detection:{detection_id}"
            return self._get_json(key)
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve detection result: {e}")
            return None

    def set_localization_data(self, node_id: str, location: Dict,
                            ttl: Optional[int] = None) -> bool:
        """Cache node localization data"""
        try:
            key = f"location:{node_id}"
            return self._set_with_ttl(key, location, ttl)
            
        except Exception as e:
            self.logger.error(f"Failed to cache localization data: {e}")
            return False

    def get_localization_data(self, node_id: str) -> Optional[Dict]:
        """Retrieve cached localization data"""
        try:
            key = f"location:{node_id}"
            return self._get_json(key)
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve localization data: {e}")
            return None

    def cache_api_response(self, endpoint: str, params: Dict, response: Dict,
                          ttl: Optional[int] = None) -> bool:
        """Cache API response"""
        try:
            # Create cache key from endpoint and sorted parameters
            param_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
            key = f"api:{endpoint}:{param_str}"
            return self._set_with_ttl(key, response, ttl)
            
        except Exception as e:
            self.logger.error(f"Failed to cache API response: {e}")
            return False

    def get_cached_api_response(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Retrieve cached API response"""
        try:
            param_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
            key = f"api:{endpoint}:{param_str}"
            return self._get_json(key)
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve API response: {e}")
            return None

    def set_metric_data(self, metric_name: str, timestamp: float,
                       value: float, ttl: Optional[int] = None) -> bool:
        """Cache time-series metric data using sorted sets"""
        try:
            key = f"metric:{metric_name}"
            member = f"{timestamp}:{value}"
            
            # Store in sorted set with timestamp as score
            self.redis.zadd(key, {member: timestamp})
            
            if ttl:
                self.redis.expire(key, ttl)
            
            # Trim old data (keep last 1000 points)
            self.redis.zremrangebyrank(key, 0, -1001)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cache metric data: {e}")
            return False

    def get_metric_data(self, metric_name: str,
                       start_time: Optional[float] = None,
                       end_time: Optional[float] = None) -> List[Dict]:
        """Retrieve cached metric data within time range"""
        try:
            key = f"metric:{metric_name}"
            
            # Set time range
            min_score = start_time if start_time is not None else '-inf'
            max_score = end_time if end_time is not None else '+inf'
            
            # Get data from sorted set
            data = self.redis.zrangebyscore(key, min_score, max_score)
            
            # Parse results
            results = []
            for item in data:
                timestamp, value = item.split(':')
                results.append({
                    'timestamp': float(timestamp),
                    'value': float(value)
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve metric data: {e}")
            return []

    def invalidate_cache(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to invalidate cache: {e}")
            return 0

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            info = self.redis.info()
            return {
                'used_memory_mb': int(info['used_memory']) / 1024 / 1024,
                'total_keys': info['db0']['keys'],
                'evicted_keys': info.get('evicted_keys', 0),
                'hits': info['keyspace_hits'],
                'misses': info['keyspace_misses'],
                'hit_rate': info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])
                if (info['keyspace_hits'] + info['keyspace_misses']) > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {}

    def _set_with_ttl(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Helper method to set value with TTL"""
        try:
            # Convert value to JSON string
            json_value = json.dumps(value)
            
            # Set value with TTL
            if ttl is None:
                ttl = self.default_ttl
            
            return bool(self.redis.setex(key, ttl, json_value))
            
        except Exception as e:
            self.logger.error(f"Failed to set cache value: {e}")
            return False

    def _get_json(self, key: str) -> Optional[Any]:
        """Helper method to get and parse JSON value"""
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get cache value: {e}")
            return None

    def _periodic_cleanup(self):
        """Periodic cache maintenance"""
        while self.running:
            try:
                # Get cache stats
                stats = self.get_cache_stats()
                
                # Log cache status
                self.logger.info(f"Cache stats: {stats}")
                
                # If memory usage is high, trigger cleanup
                if stats.get('used_memory_mb', 0) > self.max_memory * 0.9:
                    self.logger.warning("Cache memory usage high, cleaning up...")
                    # Redis will handle eviction automatically based on policy
                
                time.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Cache cleanup failed: {e}")
                time.sleep(60)

    def close(self):
        """Close Redis connection and stop background tasks"""
        self.running = False
        
        if self.cleanup_thread:
            self.cleanup_thread.join()
        
        try:
            self.redis.close()
        except Exception as e:
            self.logger.error(f"Failed to close Redis connection: {e}")

# Example usage
if __name__ == '__main__':
    cache = CacheManager()
    
    # Example: Cache detection result
    detection_result = {
        'objects': [
            {'class': 'person', 'confidence': 0.95, 'bbox': [100, 100, 200, 200]},
            {'class': 'car', 'confidence': 0.87, 'bbox': [300, 300, 500, 400]}
        ],
        'frame_id': 1234,
        'timestamp': time.time()
    }
    cache.set_detection_result('det_123', detection_result, ttl=300)
    
    # Example: Cache localization data
    location_data = {
        'latitude': 37.7749,
        'longitude': -122.4194,
        'altitude': 100,
        'accuracy': 5.0,
        'timestamp': time.time()
    }
    cache.set_localization_data('drone_1', location_data, ttl=60)
    
    # Example: Cache API response
    api_response = {
        'status': 'success',
        'data': {'temperature': 25, 'humidity': 60},
        'timestamp': time.time()
    }
    cache.cache_api_response('/sensors/status', {'device_id': 'sensor_1'}, api_response)
    
    # Example: Cache metric data
    for i in range(10):
        cache.set_metric_data('cpu_usage', time.time(), 50 + i)
    
    # Example: Get cache stats
    stats = cache.get_cache_stats()
    print("\nCache Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Cleanup
    cache.close() 