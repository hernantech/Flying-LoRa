import cv2
import numpy as np
import time
import json
import random
import threading
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from queue import Queue
from pathlib import Path

from config import ConfigManager
from logging_config import LoggerSetup
from lora_protocol import LoRaProtocolHandler, MessagePriority
from mesh_network import MeshNetworkManager, Node
from hardware_interface import HardwareInterface

@dataclass
class SimulatedObject:
    class_name: str
    confidence: float
    position: Tuple[float, float]  # x, y in normalized coordinates
    velocity: Tuple[float, float]  # dx, dy per frame
    size: Tuple[float, float]     # width, height in normalized coordinates

class SimulationEnvironment:
    def __init__(self):
        # Initialize configuration and logging
        self.config = ConfigManager()
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Load simulation config
        self.frame_width = self.config.get('simulation.frame_width', 640)
        self.frame_height = self.config.get('simulation.frame_height', 480)
        self.fps = self.config.get('simulation.fps', 30)
        self.frame_interval = 1.0 / self.fps
        
        # Initialize simulated objects
        self.objects = [
            SimulatedObject(
                class_name='person',
                confidence=0.95,
                position=(random.random(), random.random()),
                velocity=(random.uniform(-0.01, 0.01), random.uniform(-0.01, 0.01)),
                size=(0.1, 0.2)
            )
            for _ in range(3)
        ]
        
        # Initialize virtual nodes
        self.nodes: Dict[str, Dict] = {
            f"node_{i}": {
                'position': (random.random() * 1000, random.random() * 1000),  # meters
                'battery': 100.0,
                'rssi': -60,
                'snr': 10
            }
            for i in range(5)
        }
        
        # Frame generation
        self.frame_count = 0
        self.running = False
        self.frame_queue = Queue(maxsize=10)
        
        # Detection results
        self.detection_queue = Queue(maxsize=10)
        
        # Telemetry data
        self.telemetry = {
            'cpu_temp': 45.0,
            'gpu_temp': 65.0,
            'battery_voltage': 11.8,
            'memory_usage': 60.0
        }
        
        # Start simulation threads
        self.frame_thread = None
        self.telemetry_thread = None

    def start(self):
        """Start simulation"""
        if not self.running:
            self.running = True
            self.frame_thread = threading.Thread(target=self._frame_generator)
            self.telemetry_thread = threading.Thread(target=self._telemetry_generator)
            
            self.frame_thread.start()
            self.telemetry_thread.start()
            
            self.logger.info("Simulation started")

    def stop(self):
        """Stop simulation"""
        if self.running:
            self.running = False
            
            if self.frame_thread:
                self.frame_thread.join()
            if self.telemetry_thread:
                self.telemetry_thread.join()
            
            self.logger.info("Simulation stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        """Get next simulated frame"""
        try:
            return self.frame_queue.get(timeout=1.0)
        except Queue.Empty:
            return None

    def get_detection(self) -> Optional[Dict]:
        """Get next simulated detection result"""
        try:
            return self.detection_queue.put(timeout=1.0)
        except Queue.Empty:
            return None

    def get_telemetry(self) -> Dict:
        """Get current telemetry data"""
        return self.telemetry.copy()

    def _frame_generator(self):
        """Generate simulated camera frames"""
        while self.running:
            start_time = time.time()
            
            # Create blank frame
            frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
            
            # Update object positions
            detections = []
            for obj in self.objects:
                # Update position
                x, y = obj.position
                dx, dy = obj.velocity
                
                x = (x + dx) % 1.0
                y = (y + dy) % 1.0
                obj.position = (x, y)
                
                # Draw object
                w, h = obj.size
                px = int(x * self.frame_width)
                py = int(y * self.frame_height)
                pw = int(w * self.frame_width)
                ph = int(h * self.frame_height)
                
                # Draw rectangle
                color = (0, 255, 0) if obj.class_name == 'person' else (255, 0, 0)
                cv2.rectangle(frame, (px, py), (px + pw, py + ph), color, 2)
                
                # Add detection
                detections.append({
                    'class': obj.class_name,
                    'confidence': obj.confidence,
                    'bbox': [px, py, px + pw, py + ph]
                })
            
            # Add frame number and timestamp
            cv2.putText(
                frame,
                f"Frame: {self.frame_count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )
            
            # Queue frame and detections
            self.frame_queue.put(frame)
            self.detection_queue.put({
                'frame_id': self.frame_count,
                'timestamp': time.time(),
                'objects': detections
            })
            
            self.frame_count += 1
            
            # Maintain FPS
            elapsed = time.time() - start_time
            if elapsed < self.frame_interval:
                time.sleep(self.frame_interval - elapsed)

    def _telemetry_generator(self):
        """Generate simulated telemetry data"""
        while self.running:
            # Update telemetry with random variations
            self.telemetry['cpu_temp'] += random.uniform(-0.5, 0.5)
            self.telemetry['gpu_temp'] += random.uniform(-0.5, 0.5)
            self.telemetry['battery_voltage'] += random.uniform(-0.1, 0.1)
            self.telemetry['memory_usage'] += random.uniform(-1.0, 1.0)
            
            # Keep values in reasonable ranges
            self.telemetry['cpu_temp'] = np.clip(self.telemetry['cpu_temp'], 35, 85)
            self.telemetry['gpu_temp'] = np.clip(self.telemetry['gpu_temp'], 45, 95)
            self.telemetry['battery_voltage'] = np.clip(self.telemetry['battery_voltage'], 10.5, 12.6)
            self.telemetry['memory_usage'] = np.clip(self.telemetry['memory_usage'], 20, 95)
            
            # Update node states
            for node_id, node in self.nodes.items():
                # Update position with random walk
                x, y = node['position']
                x += random.uniform(-1, 1)  # 1 meter steps
                y += random.uniform(-1, 1)
                node['position'] = (x, y)
                
                # Update battery level
                node['battery'] -= random.uniform(0.01, 0.05)
                if node['battery'] < 0:
                    node['battery'] = 100.0
                
                # Update signal quality
                node['rssi'] = -60 + random.uniform(-10, 10)
                node['snr'] = 10 + random.uniform(-2, 2)
            
            time.sleep(1.0)  # Update every second

class SimulatedHardwareInterface(HardwareInterface):
    """Simulated hardware interface for development"""
    def __init__(self):
        super().__init__()
        self.simulation = SimulationEnvironment()
        self.simulation.start()

    def initialize_camera(self):
        """Initialize simulated camera"""
        self.logger.info("Initializing simulated camera")
        return True

    def read_camera_frame(self) -> Tuple[bool, np.ndarray]:
        """Read frame from simulated camera"""
        frame = self.simulation.get_frame()
        return True, frame if frame is not None else np.zeros((480, 640, 3))

    def get_gps_location(self) -> Dict:
        """Get simulated GPS location"""
        return {
            'latitude': 37.7749 + random.uniform(-0.0001, 0.0001),
            'longitude': -122.4194 + random.uniform(-0.0001, 0.0001),
            'altitude': 100 + random.uniform(-1, 1),
            'accuracy': 5.0,
            'timestamp': time.time()
        }

    def get_telemetry(self) -> Dict:
        """Get simulated telemetry data"""
        return self.simulation.get_telemetry()

    def cleanup(self):
        """Cleanup simulation"""
        self.simulation.stop()
        super().cleanup()

class SimulatedLoRaHandler(LoRaProtocolHandler):
    """Simulated LoRa protocol handler"""
    def __init__(self):
        super().__init__()
        self.simulation = SimulationEnvironment()
        
        # Virtual message queue
        self.virtual_queue = Queue()
        
        # Start simulation
        self.simulation.start()

    def send_message(self, message: str, priority: MessagePriority = MessagePriority.MEDIUM) -> str:
        """Simulate sending message with virtual delay"""
        message_id = super().send_message(message, priority)
        
        # Add artificial delay based on priority
        delay = {
            MessagePriority.HIGH: 0.1,
            MessagePriority.MEDIUM: 0.5,
            MessagePriority.LOW: 1.0
        }[priority]
        
        time.sleep(delay)
        
        # Queue message for virtual delivery
        self.virtual_queue.put({
            'message_id': message_id,
            'content': message,
            'timestamp': time.time()
        })
        
        return message_id

    def receive_message(self, timeout: float = None) -> Optional[str]:
        """Receive message from virtual queue"""
        try:
            data = self.virtual_queue.get(timeout=timeout)
            return data['content']
        except Queue.Empty:
            return None

    def get_signal_quality(self) -> Dict:
        """Get simulated signal quality"""
        # Get random node's signal quality
        node_id = random.choice(list(self.simulation.nodes.keys()))
        node = self.simulation.nodes[node_id]
        
        return {
            'rssi': node['rssi'],
            'snr': node['snr']
        }

    def cleanup(self):
        """Cleanup simulation"""
        self.simulation.stop()
        super().cleanup()

# Example usage
if __name__ == '__main__':
    # Create simulated environment
    sim = SimulationEnvironment()
    sim.start()
    
    try:
        while True:
            # Get frame and detections
            frame = sim.get_frame()
            if frame is not None:
                cv2.imshow('Simulation', frame)
            
            # Get telemetry
            telemetry = sim.get_telemetry()
            print("\nTelemetry:", json.dumps(telemetry, indent=2))
            
            # Print node states
            print("\nNodes:")
            for node_id, node in sim.nodes.items():
                print(f"{node_id}:", json.dumps(node, indent=2))
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
    except KeyboardInterrupt:
        pass
    
    finally:
        sim.stop()
        cv2.destroyAllWindows() 