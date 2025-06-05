from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address
from app import limiter, metrics
from app.services.localization_service import LocalizationService
from app.utils.auth import require_api_key
from app.utils.validation import validate_json

localization_bp = Blueprint('localization', __name__)

# Apply rate limiting to all endpoints in this blueprint
@localization_bp.before_request
@require_api_key
def before_request():
    """Authenticate and rate limit all requests to this blueprint."""
    pass

@localization_bp.route('/compute', methods=['POST'])
@metrics.counter('localization_compute_requests_total', 'Number of localization computation requests')
@limiter.limit("30/minute")
@validate_json({
    'type': 'object',
    'required': ['detections'],
    'properties': {
        'detections': {
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['timestamp', 'objects', 'source'],
                'properties': {
                    'timestamp': {'type': 'number'},
                    'source': {'type': 'string'},
                    'objects': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'required': ['class', 'confidence', 'bbox'],
                            'properties': {
                                'class': {'type': 'string'},
                                'confidence': {'type': 'number'},
                                'bbox': {
                                    'type': 'array',
                                    'items': {'type': 'number'},
                                    'minItems': 4,
                                    'maxItems': 4
                                }
                            }
                        }
                    }
                }
            }
        },
        'algorithm': {'type': 'string', 'enum': ['triangulation', 'multilateration']},
        'min_confidence': {'type': 'number', 'minimum': 0, 'maximum': 1}
    }
})
def compute_localization():
    """Compute object localization from detection data."""
    try:
        # Get request parameters
        params = request.get_json()
        
        # Compute localization
        results = LocalizationService.compute(
            detections=params['detections'],
            algorithm=params.get('algorithm', 'triangulation'),
            min_confidence=params.get('min_confidence', 0.5)
        )
        
        return jsonify({
            'status': 'success',
            'data': results
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@localization_bp.route('/objects', methods=['GET'])
@metrics.counter('localization_objects_requests_total', 'Number of localized objects requests')
@limiter.limit("60/minute")
def get_localized_objects():
    """Get currently localized objects."""
    try:
        # Get optional query parameters
        class_filter = request.args.get('class')
        min_confidence = request.args.get('min_confidence', type=float)
        limit = request.args.get('limit', default=100, type=int)
        
        # Get localized objects
        objects = LocalizationService.get_objects(
            class_filter=class_filter,
            min_confidence=min_confidence,
            limit=limit
        )
        
        return jsonify({
            'status': 'success',
            'data': objects
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@localization_bp.route('/history', methods=['GET'])
@metrics.counter('localization_history_requests_total', 'Number of localization history requests')
@limiter.limit("30/minute")
def get_localization_history():
    """Get historical localization data."""
    try:
        # Get query parameters
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        class_filter = request.args.get('class')
        min_confidence = request.args.get('min_confidence', type=float)
        
        if not start_time or not end_time:
            return jsonify({
                'status': 'error',
                'message': 'start_time and end_time are required'
            }), 400
        
        # Get history
        history = LocalizationService.get_history(
            start_time=start_time,
            end_time=end_time,
            class_filter=class_filter,
            min_confidence=min_confidence
        )
        
        return jsonify({
            'status': 'success',
            'data': history
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@localization_bp.route('/config', methods=['GET', 'POST'])
@metrics.counter('localization_config_requests_total', 'Number of localization configuration requests')
@limiter.limit("10/minute")
def localization_config():
    """Get or update localization configuration."""
    try:
        if request.method == 'GET':
            config = LocalizationService.get_config()
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
            LocalizationService.update_config(params)
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@localization_bp.route('/statistics', methods=['GET'])
@metrics.counter('localization_statistics_requests_total', 'Number of localization statistics requests')
def get_localization_statistics():
    """Get localization statistics."""
    try:
        # Get optional time range
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        
        # Get statistics
        stats = LocalizationService.get_statistics(
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