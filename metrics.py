from prometheus_client import Counter, Gauge, Histogram, start_http_server
import psutil
import time
from typing import Dict

class MetricsCollector:
    def __init__(self, port: int = 9090):
        # Detection metrics
        self.detection_count = Counter(
            'flying_lora_detections_total',
            'Total number of detections made'
        )
        self.detection_latency = Histogram(
            'flying_lora_detection_latency_seconds',
            'Detection processing latency in seconds',
            buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        )
        self.detection_confidence = Histogram(
            'flying_lora_detection_confidence',
            'Detection confidence scores',
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )

        # API metrics
        self.api_requests = Counter(
            'flying_lora_api_requests_total',
            'Total number of API requests',
            ['endpoint', 'method', 'status']
        )
        self.api_latency = Histogram(
            'flying_lora_api_latency_seconds',
            'API request latency in seconds',
            ['endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )

        # System metrics
        self.cpu_usage = Gauge(
            'flying_lora_cpu_usage_percent',
            'Current CPU usage percentage'
        )
        self.memory_usage = Gauge(
            'flying_lora_memory_usage_bytes',
            'Current memory usage in bytes'
        )
        self.disk_usage = Gauge(
            'flying_lora_disk_usage_percent',
            'Current disk usage percentage'
        )

        # LoRa metrics
        self.lora_signal_strength = Gauge(
            'flying_lora_signal_strength_dbm',
            'LoRa signal strength in dBm'
        )
        self.lora_packets_sent = Counter(
            'flying_lora_packets_sent_total',
            'Total number of LoRa packets sent'
        )
        self.lora_packets_received = Counter(
            'flying_lora_packets_received_total',
            'Total number of LoRa packets received'
        )
        self.lora_packet_loss = Gauge(
            'flying_lora_packet_loss_percent',
            'LoRa packet loss percentage'
        )

        # Business metrics
        self.mission_duration = Histogram(
            'flying_lora_mission_duration_seconds',
            'Mission duration in seconds',
            buckets=[60, 300, 600, 1800, 3600, 7200]
        )
        self.mission_success_rate = Gauge(
            'flying_lora_mission_success_rate',
            'Mission success rate as a percentage'
        )

        # Start Prometheus HTTP server
        start_http_server(port)

    def record_detection(self, latency: float, confidence: float):
        """Record detection metrics"""
        self.detection_count.inc()
        self.detection_latency.observe(latency)
        self.detection_confidence.observe(confidence)

    def record_api_request(self, endpoint: str, method: str, status: int, latency: float):
        """Record API request metrics"""
        self.api_requests.labels(endpoint=endpoint, method=method, status=status).inc()
        self.api_latency.labels(endpoint=endpoint).observe(latency)

    def update_system_metrics(self):
        """Update system resource metrics"""
        self.cpu_usage.set(psutil.cpu_percent())
        mem = psutil.virtual_memory()
        self.memory_usage.set(mem.used)
        disk = psutil.disk_usage('/')
        self.disk_usage.set(disk.percent)

    def record_lora_metrics(self, signal_strength: float, packets: Dict[str, int]):
        """Record LoRa communication metrics"""
        self.lora_signal_strength.set(signal_strength)
        self.lora_packets_sent.inc(packets.get('sent', 0))
        self.lora_packets_received.inc(packets.get('received', 0))
        
        if packets.get('sent', 0) > 0:
            loss_rate = (packets.get('sent', 0) - packets.get('received', 0)) / packets.get('sent', 0) * 100
            self.lora_packet_loss.set(loss_rate)

    def record_mission_metrics(self, duration: float, success: bool):
        """Record mission-related metrics"""
        self.mission_duration.observe(duration)
        # Update success rate using exponential moving average
        current_rate = self.mission_success_rate._value.get()
        if current_rate is None:
            current_rate = 100 if success else 0
        else:
            # Use 0.1 as smoothing factor
            current_rate = (0.9 * current_rate) + (0.1 * (100 if success else 0))
        self.mission_success_rate.set(current_rate)

# Example usage
if __name__ == '__main__':
    metrics = MetricsCollector()
    
    # Simulate metrics collection
    while True:
        metrics.update_system_metrics()
        time.sleep(15)  # Update every 15 seconds 