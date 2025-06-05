from flask_socketio import emit, join_room, leave_room
from app.services.detection_service import DetectionService
from app.utils.auth import validate_token
import json

def register_detection_handlers(socketio):
    """Register detection WebSocket handlers."""
    
    @socketio.on('connect', namespace='/ws/detections')
    def handle_connect():
        """Handle client connection."""
        try:
            # Validate client token
            token = validate_token()
            if not token:
                return False
            
            # Join detection room
            join_room('detections')
            
            # Send initial detection state
            emit('detection_state', {
                'status': 'connected',
                'active': DetectionService.is_active(),
                'config': DetectionService.get_config()
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
            return False
    
    @socketio.on('disconnect', namespace='/ws/detections')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            leave_room('detections')
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('subscribe', namespace='/ws/detections')
    def handle_subscribe(data):
        """Handle subscription to specific detection events."""
        try:
            # Validate subscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid subscription format')
            
            # Get subscription parameters
            events = data.get('events', ['detections'])
            filters = data.get('filters', {})
            
            # Join specific rooms based on events
            for event in events:
                if event in ['detections', 'statistics', 'status']:
                    join_room(f'detections_{event}')
            
            # Store client filters
            # This would typically be stored in a client session or database
            
            emit('subscription_state', {
                'status': 'subscribed',
                'events': events,
                'filters': filters
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe', namespace='/ws/detections')
    def handle_unsubscribe(data):
        """Handle unsubscription from specific detection events."""
        try:
            # Validate unsubscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid unsubscription format')
            
            # Get events to unsubscribe from
            events = data.get('events', ['detections'])
            
            # Leave specific rooms based on events
            for event in events:
                if event in ['detections', 'statistics', 'status']:
                    leave_room(f'detections_{event}')
            
            emit('subscription_state', {
                'status': 'unsubscribed',
                'events': events
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    def broadcast_detection(detection_data):
        """Broadcast detection data to subscribed clients."""
        try:
            socketio.emit('detection', detection_data, namespace='/ws/detections', room='detections_detections')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/detections')
    
    def broadcast_statistics(stats_data):
        """Broadcast detection statistics to subscribed clients."""
        try:
            socketio.emit('statistics', stats_data, namespace='/ws/detections', room='detections_statistics')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/detections')
    
    def broadcast_status(status_data):
        """Broadcast detection status to subscribed clients."""
        try:
            socketio.emit('status', status_data, namespace='/ws/detections', room='detections_status')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/detections')
    
    # Register broadcast functions with DetectionService
    DetectionService.register_detection_callback(broadcast_detection)
    DetectionService.register_statistics_callback(broadcast_statistics)
    DetectionService.register_status_callback(broadcast_status) 