from flask_socketio import emit, join_room, leave_room
from app.services.detection_service import DetectionService
from app.services.localization_service import LocalizationService
from app.services.drone_service import DroneService
from app.utils.auth import validate_token
import json
import time

def register_visualization_handlers(socketio):
    """Register visualization WebSocket handlers."""
    
    @socketio.on('connect', namespace='/ws/visualization')
    def handle_connect():
        """Handle client connection."""
        try:
            # Validate client token
            token = validate_token()
            if not token:
                return False
            
            # Join visualization room
            join_room('visualization')
            
            # Send initial visualization state
            emit('visualization_state', {
                'status': 'connected',
                'timestamp': time.time(),
                'active_layers': [
                    'detections',
                    'localization',
                    'drones',
                    'terrain'
                ]
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
            return False
    
    @socketio.on('disconnect', namespace='/ws/visualization')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            leave_room('visualization')
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('subscribe', namespace='/ws/visualization')
    def handle_subscribe(data):
        """Handle subscription to specific visualization layers."""
        try:
            # Validate subscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid subscription format')
            
            # Get subscription parameters
            layers = data.get('layers', ['all'])
            update_rate = data.get('update_rate', 1.0)  # Updates per second
            view_bounds = data.get('view_bounds', None)  # Geographic bounds to receive data for
            
            # Join specific rooms based on layers
            available_layers = [
                'detections',
                'localization',
                'drones',
                'terrain',
                'heatmap',
                'trajectories'
            ]
            
            if 'all' in layers:
                layers = available_layers
            
            for layer in layers:
                if layer in available_layers:
                    join_room(f'visualization_{layer}')
            
            # Store client preferences
            # This would typically be stored in a client session or database
            
            emit('subscription_state', {
                'status': 'subscribed',
                'layers': layers,
                'update_rate': update_rate,
                'view_bounds': view_bounds
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe', namespace='/ws/visualization')
    def handle_unsubscribe(data):
        """Handle unsubscription from specific visualization layers."""
        try:
            # Validate unsubscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid unsubscription format')
            
            # Get layers to unsubscribe from
            layers = data.get('layers', ['all'])
            
            # Leave specific rooms based on layers
            available_layers = [
                'detections',
                'localization',
                'drones',
                'terrain',
                'heatmap',
                'trajectories'
            ]
            
            if 'all' in layers:
                layers = available_layers
            
            for layer in layers:
                if layer in available_layers:
                    leave_room(f'visualization_{layer}')
            
            emit('subscription_state', {
                'status': 'unsubscribed',
                'layers': layers
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('view_update', namespace='/ws/visualization')
    def handle_view_update(data):
        """Handle client view updates (pan/zoom)."""
        try:
            # Validate view update data
            if not isinstance(data, dict):
                raise ValueError('Invalid view update format')
            
            # Get view parameters
            view_bounds = data.get('view_bounds')
            zoom_level = data.get('zoom_level')
            
            if not view_bounds:
                raise ValueError('view_bounds is required')
            
            # Update client view preferences
            # This would typically be stored in a client session or database
            
            # Send acknowledgment
            emit('view_state', {
                'status': 'updated',
                'view_bounds': view_bounds,
                'zoom_level': zoom_level
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    def broadcast_detection_visualization(detection_data):
        """Broadcast detection visualization data to subscribed clients."""
        try:
            visualization_data = {
                'type': 'detection',
                'timestamp': time.time(),
                'data': detection_data
            }
            socketio.emit('visualization_update', visualization_data,
                         namespace='/ws/visualization', room='visualization_detections')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/visualization')
    
    def broadcast_localization_visualization(localization_data):
        """Broadcast localization visualization data to subscribed clients."""
        try:
            visualization_data = {
                'type': 'localization',
                'timestamp': time.time(),
                'data': localization_data
            }
            socketio.emit('visualization_update', visualization_data,
                         namespace='/ws/visualization', room='visualization_localization')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/visualization')
    
    def broadcast_drone_visualization(drone_data):
        """Broadcast drone visualization data to subscribed clients."""
        try:
            visualization_data = {
                'type': 'drone',
                'timestamp': time.time(),
                'data': drone_data
            }
            socketio.emit('visualization_update', visualization_data,
                         namespace='/ws/visualization', room='visualization_drones')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/visualization')
    
    def broadcast_heatmap_visualization(heatmap_data):
        """Broadcast heatmap visualization data to subscribed clients."""
        try:
            visualization_data = {
                'type': 'heatmap',
                'timestamp': time.time(),
                'data': heatmap_data
            }
            socketio.emit('visualization_update', visualization_data,
                         namespace='/ws/visualization', room='visualization_heatmap')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/visualization')
    
    # Register visualization callbacks with services
    DetectionService.register_visualization_callback(broadcast_detection_visualization)
    LocalizationService.register_visualization_callback(broadcast_localization_visualization)
    DroneService.register_visualization_callback(broadcast_drone_visualization) 