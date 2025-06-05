import time
import json
import threading
import logging
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import networkx as nx
from lora_protocol import LoRaProtocolHandler, MessagePriority
from config import ConfigManager
from logging_config import LoggerSetup

@dataclass
class Node:
    id: str
    last_seen: float
    rssi: int
    snr: float
    hop_count: int
    battery_level: float
    is_gateway: bool = False

class MessageType(Enum):
    DISCOVERY = "discovery"
    HEARTBEAT = "heartbeat"
    ROUTE_UPDATE = "route_update"
    DATA = "data"

class MeshNetworkManager:
    DISCOVERY_INTERVAL = 60  # Seconds between discovery broadcasts
    HEARTBEAT_INTERVAL = 30  # Seconds between heartbeats
    NODE_TIMEOUT = 180      # Seconds before considering a node offline
    MAX_HOPS = 5           # Maximum number of hops for routing
    
    def __init__(self, node_id: str, is_gateway: bool = False):
        # Initialize configuration and logging
        self.config = ConfigManager()
        self.log_setup = LoggerSetup()
        self.logger = self.log_setup.get_logger()
        
        # Node information
        self.node_id = node_id
        self.is_gateway = is_gateway
        
        # Initialize LoRa protocol handler
        self.lora = LoRaProtocolHandler()
        
        # Network state
        self.nodes: Dict[str, Node] = {}  # node_id -> Node
        self.routing_table: Dict[str, str] = {}  # destination -> next_hop
        self.network_graph = nx.Graph()
        
        # Message handling
        self.message_handlers = {
            MessageType.DISCOVERY: self._handle_discovery,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.ROUTE_UPDATE: self._handle_route_update,
            MessageType.DATA: self._handle_data
        }
        
        # Threading control
        self.running = False
        self.discovery_thread = None
        self.heartbeat_thread = None
        self.cleanup_thread = None
        
        # Statistics
        self.stats = {
            'messages_forwarded': 0,
            'route_updates': 0,
            'active_nodes': 0,
            'total_bandwidth': 0
        }

    def start(self):
        """Start the mesh network manager"""
        if not self.running:
            self.running = True
            self.lora.start()
            
            # Start management threads
            self.discovery_thread = threading.Thread(target=self._discovery_loop)
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop)
            
            self.discovery_thread.start()
            self.heartbeat_thread.start()
            self.cleanup_thread.start()
            
            # Register self as a node
            self._register_node(
                self.node_id,
                Node(
                    id=self.node_id,
                    last_seen=time.time(),
                    rssi=0,
                    snr=0,
                    hop_count=0,
                    battery_level=1.0,
                    is_gateway=self.is_gateway
                )
            )
            
            self.logger.info(f"Mesh network manager started (Node ID: {self.node_id})")

    def stop(self):
        """Stop the mesh network manager"""
        if self.running:
            self.running = False
            self.lora.stop()
            
            if self.discovery_thread:
                self.discovery_thread.join()
            if self.heartbeat_thread:
                self.heartbeat_thread.join()
            if self.cleanup_thread:
                self.cleanup_thread.join()
            
            self.logger.info("Mesh network manager stopped")

    def send_message(self, destination: str, message: str, priority: MessagePriority = MessagePriority.MEDIUM):
        """Send a message to a destination node"""
        try:
            if destination not in self.routing_table:
                self.logger.warning(f"No route to destination: {destination}")
                return False
            
            next_hop = self.routing_table[destination]
            message_data = {
                'type': MessageType.DATA.value,
                'source': self.node_id,
                'destination': destination,
                'next_hop': next_hop,
                'payload': message
            }
            
            self.lora.send_message(json.dumps(message_data), priority)
            self.stats['total_bandwidth'] += len(message.encode())
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False

    def get_network_topology(self) -> Dict:
        """Get current network topology information"""
        return {
            'nodes': len(self.nodes),
            'active_nodes': sum(1 for n in self.nodes.values() 
                              if time.time() - n.last_seen < self.NODE_TIMEOUT),
            'routes': len(self.routing_table),
            'gateway_nodes': sum(1 for n in self.nodes.values() if n.is_gateway),
            'stats': self.stats
        }

    def _discovery_loop(self):
        """Periodic network discovery broadcast"""
        while self.running:
            try:
                discovery_data = {
                    'type': MessageType.DISCOVERY.value,
                    'node_id': self.node_id,
                    'is_gateway': self.is_gateway,
                    'battery_level': 1.0,  # TODO: Implement actual battery monitoring
                    'timestamp': time.time()
                }
                
                self.lora.send_message(
                    json.dumps(discovery_data),
                    MessagePriority.LOW
                )
                
                time.sleep(self.DISCOVERY_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in discovery loop: {e}")
                time.sleep(1)

    def _heartbeat_loop(self):
        """Periodic heartbeat broadcast"""
        while self.running:
            try:
                heartbeat_data = {
                    'type': MessageType.HEARTBEAT.value,
                    'node_id': self.node_id,
                    'timestamp': time.time()
                }
                
                self.lora.send_message(
                    json.dumps(heartbeat_data),
                    MessagePriority.LOW
                )
                
                time.sleep(self.HEARTBEAT_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(1)

    def _cleanup_loop(self):
        """Periodic cleanup of inactive nodes"""
        while self.running:
            try:
                current_time = time.time()
                inactive_nodes = [
                    node_id for node_id, node in self.nodes.items()
                    if current_time - node.last_seen > self.NODE_TIMEOUT
                    and node_id != self.node_id
                ]
                
                for node_id in inactive_nodes:
                    self._remove_node(node_id)
                
                self.stats['active_nodes'] = len(self.nodes) - len(inactive_nodes)
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                time.sleep(1)

    def _register_node(self, node_id: str, node: Node):
        """Register a new node in the network"""
        self.nodes[node_id] = node
        self.network_graph.add_node(node_id)
        self._update_routing_table()

    def _remove_node(self, node_id: str):
        """Remove a node from the network"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.network_graph.remove_node(node_id)
            self._update_routing_table()
            self.logger.info(f"Node removed from network: {node_id}")

    def _update_routing_table(self):
        """Update routing table based on current network topology"""
        try:
            new_routing_table = {}
            
            # Find shortest paths to all nodes
            for dest_id in self.nodes:
                if dest_id == self.node_id:
                    continue
                
                try:
                    path = nx.shortest_path(
                        self.network_graph,
                        self.node_id,
                        dest_id,
                        weight='weight'
                    )
                    
                    if len(path) <= self.MAX_HOPS:
                        new_routing_table[dest_id] = path[1]  # Next hop
                
                except nx.NetworkXNoPath:
                    continue
            
            # Update routing table if changes detected
            if new_routing_table != self.routing_table:
                self.routing_table = new_routing_table
                self.stats['route_updates'] += 1
                
                # Broadcast route update
                update_data = {
                    'type': MessageType.ROUTE_UPDATE.value,
                    'node_id': self.node_id,
                    'routes': list(self.routing_table.items()),
                    'timestamp': time.time()
                }
                
                self.lora.send_message(
                    json.dumps(update_data),
                    MessagePriority.MEDIUM
                )
            
        except Exception as e:
            self.logger.error(f"Failed to update routing table: {e}")

    def _handle_discovery(self, data: Dict):
        """Handle discovery messages"""
        node_id = data['node_id']
        if node_id != self.node_id:
            signal_quality = self.lora.get_signal_quality()
            
            node = Node(
                id=node_id,
                last_seen=time.time(),
                rssi=signal_quality.get('rssi_avg', 0),
                snr=signal_quality.get('snr_avg', 0),
                hop_count=1,  # Direct connection
                battery_level=data['battery_level'],
                is_gateway=data['is_gateway']
            )
            
            self._register_node(node_id, node)
            
            # Update network graph
            weight = 1.0 / (abs(node.rssi) + 1)  # Better RSSI = lower weight
            self.network_graph.add_edge(self.node_id, node_id, weight=weight)

    def _handle_heartbeat(self, data: Dict):
        """Handle heartbeat messages"""
        node_id = data['node_id']
        if node_id in self.nodes:
            self.nodes[node_id].last_seen = time.time()

    def _handle_route_update(self, data: Dict):
        """Handle route update messages"""
        node_id = data['node_id']
        if node_id in self.nodes:
            # Update routes through this node
            for dest, next_hop in data['routes']:
                if dest != self.node_id:
                    path_length = nx.shortest_path_length(
                        self.network_graph,
                        self.node_id,
                        node_id
                    )
                    
                    if path_length < self.MAX_HOPS:
                        self.routing_table[dest] = next_hop

    def _handle_data(self, data: Dict):
        """Handle data messages"""
        if data['destination'] == self.node_id:
            # Message for this node
            self.logger.info(f"Received message from {data['source']}: {data['payload']}")
            return
        
        if data['next_hop'] == self.node_id:
            # Forward message
            if data['destination'] in self.routing_table:
                next_hop = self.routing_table[data['destination']]
                data['next_hop'] = next_hop
                
                self.lora.send_message(
                    json.dumps(data),
                    MessagePriority.MEDIUM
                )
                
                self.stats['messages_forwarded'] += 1
                self.stats['total_bandwidth'] += len(data['payload'].encode())
            else:
                self.logger.warning(f"No route to {data['destination']}")

    def _message_handler(self):
        """Main message handling loop"""
        while self.running:
            try:
                message = self.lora.receive_message(timeout=1.0)
                if message:
                    try:
                        data = json.loads(message)
                        message_type = MessageType(data['type'])
                        
                        if message_type in self.message_handlers:
                            self.message_handlers[message_type](data)
                            
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        self.logger.error(f"Invalid message format: {e}")
                
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")
                time.sleep(1)

# Example usage
if __name__ == '__main__':
    # Create a gateway node
    manager = MeshNetworkManager("gateway_1", is_gateway=True)
    manager.start()
    
    try:
        while True:
            # Print network topology every 10 seconds
            topology = manager.get_network_topology()
            print("\nNetwork Topology:")
            print(f"Active Nodes: {topology['active_nodes']}")
            print(f"Routes: {topology['routes']}")
            print(f"Messages Forwarded: {topology['stats']['messages_forwarded']}")
            print(f"Total Bandwidth: {topology['stats']['total_bandwidth']} bytes")
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        manager.stop() 