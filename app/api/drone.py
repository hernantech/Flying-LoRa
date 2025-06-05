from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address
from app import limiter, metrics
from app.services.drone_service import DroneService
from app.utils.auth import require_api_key
from app.utils.validation import validate_json

drone_bp = Blueprint('drone', __name__)

# Apply rate limiting to all endpoints in this blueprint
@drone_bp.before_request
@require_api_key
def before_request():
    """Authenticate and rate limit all requests to this blueprint."""
    pass

@drone_bp.route('/command', methods=['POST'])
@metrics.counter('drone_command_requests_total', 'Number of drone command requests')
@limiter.limit("30/minute")
@validate_json({
    'type': 'object',
    'required': ['command'],
    'properties': {
        'command': {
            'type': 'string',
            'enum': [
                'takeoff',
                'land',
                'return_home',
                'move',
                'stop',
                'set_altitude',
                'set_heading'
            ]
        },
        'parameters': {
            'type': 'object',
            'properties': {
                'altitude': {'type': 'number'},
                'heading': {'type': 'number'},
                'velocity': {
                    'type': 'object',
                    'properties': {
                        'x': {'type': 'number'},
                        'y': {'type': 'number'},
                        'z': {'type': 'number'}
                    }
                },
                'position': {
                    'type': 'object',
                    'properties': {
                        'latitude': {'type': 'number'},
                        'longitude': {'type': 'number'},
                        'altitude': {'type': 'number'}
                    }
                }
            }
        }
    }
})
def send_command():
    """Send command to drone."""
    try:
        # Get command parameters
        params = request.get_json()
        
        # Send command
        result = DroneService.send_command(
            command=params['command'],
            parameters=params.get('parameters', {})
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@drone_bp.route('/telemetry', methods=['GET'])
@metrics.counter('drone_telemetry_requests_total', 'Number of drone telemetry requests')
@limiter.limit("60/minute")
def get_telemetry():
    """Get current drone telemetry."""
    try:
        telemetry = DroneService.get_telemetry()
        
        return jsonify({
            'status': 'success',
            'data': telemetry
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@drone_bp.route('/position', methods=['GET'])
@metrics.counter('drone_position_requests_total', 'Number of drone position requests')
@limiter.limit("60/minute")
def get_position():
    """Get current drone position."""
    try:
        position = DroneService.get_position()
        
        return jsonify({
            'status': 'success',
            'data': position
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@drone_bp.route('/status', methods=['GET'])
@metrics.counter('drone_status_requests_total', 'Number of drone status requests')
def get_status():
    """Get current drone status."""
    try:
        status = DroneService.get_status()
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@drone_bp.route('/mission', methods=['GET', 'POST'])
@metrics.counter('drone_mission_requests_total', 'Number of drone mission requests')
@limiter.limit("10/minute")
def handle_mission():
    """Get or set drone mission."""
    try:
        if request.method == 'GET':
            mission = DroneService.get_mission()
            return jsonify({
                'status': 'success',
                'data': mission
            })
            
        else:  # POST
            # Validate mission parameters
            params = request.get_json()
            if not isinstance(params, dict):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid mission format'
                }), 400
            
            # Set mission
            DroneService.set_mission(params)
            
            return jsonify({
                'status': 'success',
                'message': 'Mission set successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@drone_bp.route('/config', methods=['GET', 'POST'])
@metrics.counter('drone_config_requests_total', 'Number of drone configuration requests')
@limiter.limit("10/minute")
def drone_config():
    """Get or update drone configuration."""
    try:
        if request.method == 'GET':
            config = DroneService.get_config()
            return jsonify({
                'status': 'success',
                'data': config
            })
            
        else:  # POST
            # Validate configuration update
            params = request.get_json()
            if not isinstance(params, dict):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid configuration format'
                }), 400
            
            # Update configuration
            DroneService.update_config(params)
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 