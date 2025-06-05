from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address
from app import limiter, metrics
from app.services.lora_service import LoRaService
from app.utils.auth import require_api_key
from app.utils.validation import validate_json

lora_bp = Blueprint('lora', __name__)

# Apply rate limiting to all endpoints in this blueprint
@lora_bp.before_request
@require_api_key
def before_request():
    """Authenticate and rate limit all requests to this blueprint."""
    pass

@lora_bp.route('/send', methods=['POST'])
@metrics.counter('lora_send_requests_total', 'Number of LoRa send requests')
@limiter.limit("30/minute")
@validate_json({
    'type': 'object',
    'required': ['message'],
    'properties': {
        'message': {
            'type': 'object',
            'required': ['type', 'payload'],
            'properties': {
                'type': {'type': 'string'},
                'payload': {'type': 'object'},
                'priority': {'type': 'integer', 'minimum': 0, 'maximum': 3},
                'target': {'type': 'string'},
                'require_ack': {'type': 'boolean'}
            }
        },
        'retry_count': {'type': 'integer', 'minimum': 0},
        'timeout': {'type': 'number', 'minimum': 0}
    }
})
def send_message():
    """Send LoRa message."""
    try:
        # Get message parameters
        params = request.get_json()
        
        # Send message
        result = LoRaService.send_message(
            message=params['message'],
            retry_count=params.get('retry_count'),
            timeout=params.get('timeout')
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

@lora_bp.route('/receive', methods=['GET'])
@metrics.counter('lora_receive_requests_total', 'Number of LoRa receive requests')
@limiter.limit("60/minute")
def get_messages():
    """Get received LoRa messages."""
    try:
        # Get query parameters
        message_type = request.args.get('type')
        source = request.args.get('source')
        limit = request.args.get('limit', default=100, type=int)
        since = request.args.get('since', type=float)
        
        # Get messages
        messages = LoRaService.get_messages(
            message_type=message_type,
            source=source,
            limit=limit,
            since=since
        )
        
        return jsonify({
            'status': 'success',
            'data': messages
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@lora_bp.route('/status', methods=['GET'])
@metrics.counter('lora_status_requests_total', 'Number of LoRa status requests')
def get_status():
    """Get LoRa module status."""
    try:
        status = LoRaService.get_status()
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@lora_bp.route('/config', methods=['GET', 'POST'])
@metrics.counter('lora_config_requests_total', 'Number of LoRa configuration requests')
@limiter.limit("10/minute")
def lora_config():
    """Get or update LoRa configuration."""
    try:
        if request.method == 'GET':
            config = LoRaService.get_config()
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
            LoRaService.update_config(params)
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@lora_bp.route('/network', methods=['GET'])
@metrics.counter('lora_network_requests_total', 'Number of LoRa network requests')
def get_network_status():
    """Get LoRa network status."""
    try:
        # Get network status
        status = LoRaService.get_network_status()
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@lora_bp.route('/statistics', methods=['GET'])
@metrics.counter('lora_statistics_requests_total', 'Number of LoRa statistics requests')
def get_statistics():
    """Get LoRa statistics."""
    try:
        # Get optional time range
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        
        # Get statistics
        stats = LoRaService.get_statistics(
            start_time=start_time,
            end_time=end_time
        )
        
        return jsonify({
            'status': 'success',
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 