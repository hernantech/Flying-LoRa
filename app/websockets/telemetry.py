from flask_socketio import emit, join_room, leave_room
from app.services.drone_service import DroneService
from app.utils.auth import validate_token
import json

def register_telemetry_handlers(socketio):
    """Register telemetry WebSocket handlers."""
    
    @socketio.on('connect', namespace='/ws/telemetry')
    def handle_connect():
        """Handle client connection."""
        try:
            # Validate client token
            token = validate_token()
            if not token:
                return False
            
            # Join telemetry room
            join_room('telemetry')
            
            # Send initial telemetry state
            emit('telemetry_state', {
                'status': 'connected',
                'drone_status': DroneService.get_status(),
                'telemetry': DroneService.get_telemetry()
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
            return False
    
    @socketio.on('disconnect', namespace='/ws/telemetry')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            leave_room('telemetry')
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('subscribe', namespace='/ws/telemetry')
    def handle_subscribe(data):
        """Handle subscription to specific telemetry events."""
        try:
            # Validate subscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid subscription format')
            
            # Get subscription parameters
            events = data.get('events', ['telemetry'])
            rate = data.get('rate', 1.0)  # Updates per second
            fields = data.get('fields', None)  # Specific telemetry fields to receive
            
            # Join specific rooms based on events
            for event in events:
                if event in ['telemetry', 'position', 'status', 'mission']:
                    join_room(f'telemetry_{event}')
            
            # Store client preferences
            # This would typically be stored in a client session or database
            
            emit('subscription_state', {
                'status': 'subscribed',
                'events': events,
                'rate': rate,
                'fields': fields
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    @socketio.on('unsubscribe', namespace='/ws/telemetry')
    def handle_unsubscribe(data):
        """Handle unsubscription from specific telemetry events."""
        try:
            # Validate unsubscription data
            if not isinstance(data, dict):
                raise ValueError('Invalid unsubscription format')
            
            # Get events to unsubscribe from
            events = data.get('events', ['telemetry'])
            
            # Leave specific rooms based on events
            for event in events:
                if event in ['telemetry', 'position', 'status', 'mission']:
                    leave_room(f'telemetry_{event}')
            
            emit('subscription_state', {
                'status': 'unsubscribed',
                'events': events
            })
            
        except Exception as e:
            emit('error', {'message': str(e)})
    
    def broadcast_telemetry(telemetry_data):
        """Broadcast telemetry data to subscribed clients."""
        try:
            socketio.emit('telemetry', telemetry_data, namespace='/ws/telemetry', room='telemetry_telemetry')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/telemetry')
    
    def broadcast_position(position_data):
        """Broadcast position data to subscribed clients."""
        try:
            socketio.emit('position', position_data, namespace='/ws/telemetry', room='telemetry_position')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/telemetry')
    
    def broadcast_status(status_data):
        """Broadcast drone status to subscribed clients."""
        try:
            socketio.emit('status', status_data, namespace='/ws/telemetry', room='telemetry_status')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/telemetry')
    
    def broadcast_mission(mission_data):
        """Broadcast mission updates to subscribed clients."""
        try:
            socketio.emit('mission', mission_data, namespace='/ws/telemetry', room='telemetry_mission')
        except Exception as e:
            socketio.emit('error', {'message': str(e)}, namespace='/ws/telemetry')
    
    # Register broadcast functions with DroneService
    DroneService.register_telemetry_callback(broadcast_telemetry)
    DroneService.register_position_callback(broadcast_position)
    DroneService.register_status_callback(broadcast_status)
    DroneService.register_mission_callback(broadcast_mission) 