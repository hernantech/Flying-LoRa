"""
Metrics collection module for Flying LoRa server.
Provides Prometheus-compatible metrics for monitoring system performance.
"""

from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_client import start_http_server
import psutil
import time
import threading
from typing import Dict, Any

# System Metrics
system_cpu_usage = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
system_memory_usage = Gauge('system_memory_usage_bytes', 'System memory usage in bytes')
system_gpu_usage = Gauge('system_gpu_usage_percent', 'GPU usage percentage')
system_temperature = Gauge('system_temperature_celsius', 'System temperature in Celsius')
system_power_usage = Gauge('system_power_usage_watts', 'System power usage in watts')

# API Metrics
api_requests_total = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method', 'status'])
api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0]
)

# Detection Metrics
detection_count = Counter('detection_count_total', 'Total number of detections')
detection_latency = Histogram(
    'detection_latency_seconds',
    'Object detection latency in seconds',
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5]
)
detection_confidence = Histogram(
    'detection_confidence',
    'Object detection confidence scores',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
)

# LoRa Communication Metrics
lora_messages_sent = Counter('lora_messages_sent_total', 'Total LoRa messages sent')
lora_messages_received = Counter('lora_messages_received_total', 'Total LoRa messages received')
lora_message_latency = Histogram(
    'lora_message_latency_seconds',
    'LoRa message latency in seconds',
    buckets=[0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]
)
lora_signal_strength = Gauge('lora_signal_strength_dbm', 'LoRa signal strength in dBm')
lora_error_rate = Gauge('lora_error_rate_percent', 'LoRa packet error rate percentage')

# WebSocket Metrics
websocket_clients = Gauge('websocket_clients_connected', 'Number of connected WebSocket clients', ['type'])
websocket_messages = Counter('websocket_messages_total', 'Total WebSocket messages', ['type', 'direction'])

# Database Metrics
db_connections = Gauge('db_connections_active', 'Number of active database connections')
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

# Version Info
version_info = Info('flying_lora_version', 'Flying LoRa version information')

class MetricsCollector:
    """Metrics collector for the Flying LoRa server."""
    
    def __init__(self, port: int = 9090):
        """Initialize the metrics collector.
        
        Args:
            port: Port to expose Prometheus metrics on
        """
        self.port = port
        self._running = False
        self._collection_thread = None
        version_info.info({
            'version': '1.0.0',
            'python_version': '3.8',
            'platform': 'jetson'
        })
    
    def start(self):
        """Start the metrics collection server and background collection."""
        if self._running:
            return
        
        start_http_server(self.port)
        self._running = True
        self._collection_thread = threading.Thread(target=self._collect_system_metrics)
        self._collection_thread.daemon = True
        self._collection_thread.start()
    
    def stop(self):
        """Stop the metrics collection."""
        self._running = False
        if self._collection_thread:
            self._collection_thread.join()
    
    def _collect_system_metrics(self):
        """Collect system metrics in the background."""
        while self._running:
            try:
                # CPU usage
                system_cpu_usage.set(psutil.cpu_percent())
                
                # Memory usage
                memory = psutil.virtual_memory()
                system_memory_usage.set(memory.used)
                
                # Temperature (Jetson-specific)
                try:
                    from jtop import jtop
                    with jtop() as jetson:
                        stats = jetson.stats
                        system_temperature.set(stats['Temp CPU'])
                        system_gpu_usage.set(stats['GPU'])
                        system_power_usage.set(stats['power cur'])
                except ImportError:
                    pass  # Not running on Jetson
                
                time.sleep(1)  # Collect every second
            except Exception as e:
                print(f"Error collecting system metrics: {e}")
                time.sleep(5)  # Back off on error
    
    def track_api_request(self, endpoint: str, method: str, status: int, duration: float):
        """Track an API request.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            status: HTTP status code
            duration: Request duration in seconds
        """
        api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()
        api_request_duration.labels(endpoint=endpoint).observe(duration)
    
    def track_detection(self, latency: float, confidence: float):
        """Track an object detection.
        
        Args:
            latency: Detection latency in seconds
            confidence: Detection confidence score (0-1)
        """
        detection_count.inc()
        detection_latency.observe(latency)
        detection_confidence.observe(confidence)
    
    def track_lora_message(self, direction: str, latency: float = None, rssi: float = None):
        """Track a LoRa message.
        
        Args:
            direction: Either 'sent' or 'received'
            latency: Message latency in seconds (optional)
            rssi: Signal strength in dBm (optional)
        """
        if direction == 'sent':
            lora_messages_sent.inc()
        else:
            lora_messages_received.inc()
        
        if latency is not None:
            lora_message_latency.observe(latency)
        
        if rssi is not None:
            lora_signal_strength.set(rssi)
    
    def track_websocket(self, client_type: str, direction: str):
        """Track WebSocket activity.
        
        Args:
            client_type: Type of WebSocket client
            direction: Message direction ('in' or 'out')
        """
        websocket_messages.labels(type=client_type, direction=direction).inc()
    
    def update_websocket_clients(self, client_type: str, count: int):
        """Update WebSocket client count.
        
        Args:
            client_type: Type of WebSocket client
            count: Number of connected clients
        """
        websocket_clients.labels(type=client_type).set(count)
    
    def track_db_query(self, duration: float):
        """Track a database query.
        
        Args:
            duration: Query duration in seconds
        """
        db_query_duration.observe(duration)
        
    def update_db_connections(self, count: int):
        """Update database connection count.
        
        Args:
            count: Number of active connections
        """
        db_connections.set(count)

# Global metrics collector instance
collector = MetricsCollector()

def init_metrics(port: int = 9090):
    """Initialize the metrics collection system.
    
    Args:
        port: Port to expose Prometheus metrics on
    """
    global collector
    collector = MetricsCollector(port)
    collector.start()

def get_collector() -> MetricsCollector:
    """Get the global metrics collector instance.
    
    Returns:
        The global MetricsCollector instance
    """
    return collector 