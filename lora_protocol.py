import queue
import threading
import time
import json
import zlib
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import serial
from config import ConfigManager
from logging_config import LoggerSetup, PerformanceProfiler

class MessagePriority(Enum):
    HIGH = 1    # Control messages, emergency signals
    MEDIUM = 2  # Regular telemetry, status updates
    LOW = 3     # Bulk data transfer, logs

@dataclass
class LoRaPacket:
    message_id: str
    fragment_id: int
    total_fragments: int
    priority: MessagePriority
    payload: bytes
    crc: int
    rssi: int
    snr: float
    timestamp: float

class LoRaProtocolHandler:
    MAX_PACKET_SIZE = 230  # Maximum LoRa packet size
    HEADER_SIZE = 20       # Size reserved for packet header
    RETRY_LIMIT = 3        # Maximum retransmission attempts
    ACK_TIMEOUT = 2.0     # Acknowledgment timeout in seconds

    def __init__(self):
        # Initialize configuration
        self.config = ConfigManager()
        
        # Setup logging
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Initialize queues
        self.send_queue = {
            MessagePriority.HIGH: queue.PriorityQueue(),
            MessagePriority.MEDIUM: queue.PriorityQueue(),
            MessagePriority.LOW: queue.PriorityQueue()
        }
        self.receive_queue = queue.Queue()
        
        # Initialize LoRa serial connection
        self.serial = serial.Serial(
            port=self.config.get('hardware.lora.port', '/dev/ttyUSB0'),
            baudrate=self.config.get('hardware.lora.baud_rate', 115200),
            timeout=1
        )
        
        # Message tracking
        self.pending_acks = {}  # message_id -> timestamp
        self.received_fragments = {}  # message_id -> {fragment_id: packet}
        self.message_buffer = {}  # message_id -> original message
        
        # Signal quality monitoring
        self.signal_stats = {
            'rssi': [],
            'snr': [],
            'packet_loss': 0,
            'retransmissions': 0
        }
        
        # Threading control
        self.running = False
        self.send_thread = None
        self.receive_thread = None
        
        # Register configuration observer
        self.config.register_observer(self._handle_config_change)

    def start(self):
        """Start the LoRa protocol handler"""
        if not self.running:
            self.running = True
            self.send_thread = threading.Thread(target=self._send_loop)
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.send_thread.start()
            self.receive_thread.start()
            self.logger.info("LoRa protocol handler started")

    def stop(self):
        """Stop the LoRa protocol handler"""
        if self.running:
            self.running = False
            if self.send_thread:
                self.send_thread.join()
            if self.receive_thread:
                self.receive_thread.join()
            self.serial.close()
            self.logger.info("LoRa protocol handler stopped")

    def send_message(self, message: str, priority: MessagePriority = MessagePriority.MEDIUM) -> str:
        """Send a message with specified priority"""
        try:
            message_id = f"{time.time()}_{hash(message) & 0xFFFFFFFF}"
            fragments = self._fragment_message(message_id, message)
            
            # Store original message for potential retransmission
            self.message_buffer[message_id] = message
            
            # Queue fragments for transmission
            for fragment in fragments:
                self.send_queue[priority].put((priority.value, fragment))
            
            self.logger.info(f"Message queued for transmission: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            raise

    def receive_message(self, timeout: float = None) -> Optional[str]:
        """Receive a complete message"""
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_signal_quality(self) -> Dict:
        """Get signal quality statistics"""
        if not self.signal_stats['rssi']:
            return {}
        
        return {
            'rssi_avg': sum(self.signal_stats['rssi']) / len(self.signal_stats['rssi']),
            'snr_avg': sum(self.signal_stats['snr']) / len(self.signal_stats['snr']),
            'packet_loss': self.signal_stats['packet_loss'],
            'retransmissions': self.signal_stats['retransmissions']
        }

    def _fragment_message(self, message_id: str, message: str) -> List[LoRaPacket]:
        """Fragment large messages into LoRa packets"""
        data = message.encode()
        payload_size = self.MAX_PACKET_SIZE - self.HEADER_SIZE
        fragments = []
        
        # Calculate total fragments
        total_fragments = (len(data) + payload_size - 1) // payload_size
        
        for i in range(total_fragments):
            start = i * payload_size
            end = start + payload_size
            fragment = data[start:end]
            
            # Create packet
            packet = LoRaPacket(
                message_id=message_id,
                fragment_id=i,
                total_fragments=total_fragments,
                priority=MessagePriority.MEDIUM,
                payload=fragment,
                crc=zlib.crc32(fragment),
                rssi=0,
                snr=0.0,
                timestamp=time.time()
            )
            
            fragments.append(packet)
        
        return fragments

    def _send_loop(self):
        """Main sending loop"""
        while self.running:
            try:
                # Check pending acknowledgments
                self._check_pending_acks()
                
                # Try to send from high priority queue first
                for priority in MessagePriority:
                    if not self.send_queue[priority].empty():
                        _, packet = self.send_queue[priority].get_nowait()
                        self._send_packet(packet)
                        break
                
                time.sleep(0.01)  # Prevent busy waiting
                
            except Exception as e:
                self.logger.error(f"Error in send loop: {e}")
                time.sleep(1)

    def _receive_loop(self):
        """Main receiving loop"""
        while self.running:
            try:
                if self.serial.in_waiting:
                    data = self.serial.readline()
                    packet = self._parse_packet(data)
                    
                    if packet:
                        self._handle_packet(packet)
                
            except Exception as e:
                self.logger.error(f"Error in receive loop: {e}")
                time.sleep(1)

    def _send_packet(self, packet: LoRaPacket):
        """Send a single packet"""
        try:
            # Prepare packet data
            packet_data = {
                'id': packet.message_id,
                'frag': packet.fragment_id,
                'total': packet.total_fragments,
                'priority': packet.priority.value,
                'payload': packet.payload.hex(),
                'crc': packet.crc
            }
            
            # Send packet
            data = json.dumps(packet_data).encode()
            self.serial.write(data + b'\n')
            
            # Track for acknowledgment
            self.pending_acks[packet.message_id] = time.time()
            
        except Exception as e:
            self.logger.error(f"Failed to send packet: {e}")
            # Queue for retransmission
            self.send_queue[packet.priority].put((packet.priority.value, packet))

    def _parse_packet(self, data: bytes) -> Optional[LoRaPacket]:
        """Parse received packet data"""
        try:
            packet_data = json.loads(data.decode())
            
            return LoRaPacket(
                message_id=packet_data['id'],
                fragment_id=packet_data['frag'],
                total_fragments=packet_data['total'],
                priority=MessagePriority(packet_data['priority']),
                payload=bytes.fromhex(packet_data['payload']),
                crc=packet_data['crc'],
                rssi=packet_data.get('rssi', 0),
                snr=packet_data.get('snr', 0.0),
                timestamp=time.time()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse packet: {e}")
            return None

    def _handle_packet(self, packet: LoRaPacket):
        """Handle received packet"""
        # Validate CRC
        if zlib.crc32(packet.payload) != packet.crc:
            self.logger.warning(f"CRC validation failed for packet: {packet.message_id}")
            self.signal_stats['packet_loss'] += 1
            return
        
        # Update signal statistics
        self.signal_stats['rssi'].append(packet.rssi)
        self.signal_stats['snr'].append(packet.snr)
        if len(self.signal_stats['rssi']) > 100:
            self.signal_stats['rssi'] = self.signal_stats['rssi'][-100:]
            self.signal_stats['snr'] = self.signal_stats['snr'][-100:]
        
        # Handle acknowledgment
        if packet.message_id in self.pending_acks:
            del self.pending_acks[packet.message_id]
            return
        
        # Store fragment
        if packet.message_id not in self.received_fragments:
            self.received_fragments[packet.message_id] = {}
        
        self.received_fragments[packet.message_id][packet.fragment_id] = packet
        
        # Check if message is complete
        if len(self.received_fragments[packet.message_id]) == packet.total_fragments:
            self._reassemble_message(packet.message_id)

    def _reassemble_message(self, message_id: str):
        """Reassemble complete message from fragments"""
        try:
            fragments = self.received_fragments[message_id]
            ordered_fragments = [fragments[i].payload for i in range(len(fragments))]
            message = b''.join(ordered_fragments).decode()
            
            # Put complete message in receive queue
            self.receive_queue.put(message)
            
            # Cleanup
            del self.received_fragments[message_id]
            
        except Exception as e:
            self.logger.error(f"Failed to reassemble message: {e}")

    def _check_pending_acks(self):
        """Check for timed out packets and handle retransmission"""
        current_time = time.time()
        for message_id, timestamp in list(self.pending_acks.items()):
            if current_time - timestamp > self.ACK_TIMEOUT:
                if message_id in self.message_buffer:
                    self.signal_stats['retransmissions'] += 1
                    # Retransmit with high priority
                    self.send_message(
                        self.message_buffer[message_id],
                        priority=MessagePriority.HIGH
                    )
                del self.pending_acks[message_id]

    def _handle_config_change(self, new_config: Dict):
        """Handle configuration changes"""
        try:
            # Update serial configuration if needed
            new_port = new_config.get('hardware.lora.port')
            new_baud = new_config.get('hardware.lora.baud_rate')
            
            if new_port and new_port != self.serial.port:
                self.stop()
                self.serial.port = new_port
                self.start()
            
            if new_baud and new_baud != self.serial.baudrate:
                self.stop()
                self.serial.baudrate = new_baud
                self.start()
                
        except Exception as e:
            self.logger.error(f"Failed to handle config change: {e}")

# Example usage
if __name__ == '__main__':
    handler = LoRaProtocolHandler()
    handler.start()
    
    # Example: Send a message
    message_id = handler.send_message("Hello from LoRa!", MessagePriority.HIGH)
    
    # Example: Receive messages
    while True:
        message = handler.receive_message(timeout=1.0)
        if message:
            print(f"Received: {message}")
        
        # Print signal quality
        print("Signal Quality:", handler.get_signal_quality())
        
        time.sleep(1)
    
    handler.stop() 