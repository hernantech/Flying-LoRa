import asyncio
import json
import logging
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol
from metrics import MetricsCollector
from logging_config import LoggerSetup, PerformanceProfiler

class WebSocketManager:
    def __init__(self, host: str = 'localhost', port: int = 8765):
        # Initialize logging
        self.log_setup = LoggerSetup(debug_mode=True)
        self.logger = self.log_setup.get_logger()
        
        # Initialize metrics
        self.metrics = MetricsCollector()
        
        # WebSocket settings
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        
        # System state
        self.detection_running = False
        self.current_mission = None
        
        self.logger.info("WebSocket manager initialized", extra={
            'extra_fields': {
                'host': host,
                'port': port
            }
        })

    async def register(self, websocket: WebSocketServerProtocol):
        """Register a new client connection"""
        self.clients.add(websocket)
        self.logger.info("Client connected", extra={
            'extra_fields': {
                'client_id': id(websocket),
                'client_count': len(self.clients)
            }
        })

    async def unregister(self, websocket: WebSocketServerProtocol):
        """Unregister a client connection"""
        self.clients.remove(websocket)
        self.logger.info("Client disconnected", extra={
            'extra_fields': {
                'client_id': id(websocket),
                'client_count': len(self.clients)
            }
        })

    @PerformanceProfiler.profile(logging.getLogger(__name__))
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send(json.dumps(message)) for client in self.clients]
            )

    async def handle_detection_control(self, command: str):
        """Handle detection start/stop commands"""
        if command == 'start_detection' and not self.detection_running:
            self.detection_running = True
            await self.broadcast({
                'type': 'status',
                'detection': True
            })
        elif command == 'stop_detection' and self.detection_running:
            self.detection_running = False
            await self.broadcast({
                'type': 'status',
                'detection': False
            })

    async def handle_mission(self, data: Dict):
        """Handle mission commands"""
        command = data.get('command')
        if command == 'save':
            mission_data = data.get('data', {})
            # Save mission logic here
            self.logger.info("Mission saved", extra={
                'extra_fields': {
                    'mission_name': mission_data.get('name'),
                    'waypoints': len(mission_data.get('waypoints', []))
                }
            })
        elif command == 'execute':
            mission_name = data.get('name')
            self.current_mission = mission_name
            # Execute mission logic here
            self.logger.info("Mission started", extra={
                'extra_fields': {
                    'mission_name': mission_name
                }
            })

    async def handle_config(self, data: Dict):
        """Handle configuration updates"""
        command = data.get('command')
        if command == 'save':
            config_file = data.get('file')
            config_data = data.get('data', {})
            # Save configuration logic here
            self.logger.info("Configuration updated", extra={
                'extra_fields': {
                    'config_file': config_file
                }
            })

    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get('type')

            if message_type == 'control':
                await self.handle_detection_control(data.get('command'))
            elif message_type == 'mission':
                await self.handle_mission(data)
            elif message_type == 'config':
                await self.handle_config(data)
            elif message_type == 'detection_settings':
                # Update detection settings
                self.metrics.record_detection(
                    latency=0.1,  # Example value
                    confidence=data.get('confidence', 0.5)
                )

        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON message", extra={
                'extra_fields': {
                    'error': str(e),
                    'message': message
                }
            })
        except Exception as e:
            self.logger.error("Error handling message", extra={
                'extra_fields': {
                    'error': str(e),
                    'message': message
                }
            })

    async def connection_handler(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket connections"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Client connection closed", extra={
                'extra_fields': {
                    'client_id': id(websocket)
                }
            })
        finally:
            await self.unregister(websocket)

    async def start_server(self):
        """Start the WebSocket server"""
        self.logger.info("Starting WebSocket server", extra={
            'extra_fields': {
                'host': self.host,
                'port': self.port
            }
        })
        async with websockets.serve(self.connection_handler, self.host, self.port):
            await asyncio.Future()  # Run forever

    def run(self):
        """Run the WebSocket server"""
        asyncio.run(self.start_server())

# Example usage
if __name__ == '__main__':
    manager = WebSocketManager()
    manager.run() 