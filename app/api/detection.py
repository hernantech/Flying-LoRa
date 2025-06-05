from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address
from app import limiter, metrics
from app.services.detection_service import DetectionService
from app.utils.auth import require_api_key
from app.utils.validation import validate_json

detection_bp = Blueprint('detection', __name__)

# Apply rate limiting to all endpoints in this blueprint
@detection_bp.before_request
@require_api_key
def before_request():
    """Authenticate and rate limit all requests to this blueprint."""
    pass

@detection_bp.route('/start', methods=['POST'])
@metrics.counter('detection_start_requests_total', 'Number of detection start requests')
@limiter.limit("10/minute")
@validate_json({
    'type': 'object',
    'properties': {
        'confidence_threshold': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'frame_skip': {'type': 'integer', 'minimum': 0},
        'max_detections': {'type': 'integer', 'minimum': 1}
    }
})
def start_detection():
    """Start object detection with optional parameters."""
    try:
        # Get optional parameters
        params = request.get_json()
        
        # Start detection service
        DetectionService.start(
            confidence_threshold=params.get('confidence_threshold'),
            frame_skip=params.get('frame_skip'),
            max_detections=params.get('max_detections')
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Detection started successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@detection_bp.route('/stop', methods=['POST'])
@metrics.counter('detection_stop_requests_total', 'Number of detection stop requests')
@limiter.limit("10/minute")
def stop_detection():
    """Stop object detection."""
    try:
        DetectionService.stop()
        
        return jsonify({
            'status': 'success',
            'message': 'Detection stopped successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@detection_bp.route('/status', methods=['GET'])
@metrics.counter('detection_status_requests_total', 'Number of detection status requests')
def get_detection_status():
    """Get current detection status."""
    try:
        status = DetectionService.get_status()
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@detection_bp.route('/latest', methods=['GET'])
@metrics.counter('detection_latest_requests_total', 'Number of latest detection requests')
@limiter.limit("60/minute")
def get_latest_detections():
    """Get latest detection results."""
    try:
        # Get optional query parameters
        limit = request.args.get('limit', default=10, type=int)
        min_confidence = request.args.get('min_confidence', default=0.0, type=float)
        
        # Get latest detections
        detections = DetectionService.get_latest_detections(
            limit=limit,
            min_confidence=min_confidence
        )
        
        return jsonify({
            'status': 'success',
            'data': detections
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@detection_bp.route('/config', methods=['GET', 'POST'])
@metrics.counter('detection_config_requests_total', 'Number of detection configuration requests')
@limiter.limit("10/minute")
def detection_config():
    """Get or update detection configuration."""
    try:
        if request.method == 'GET':
            config = DetectionService.get_config()
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
            DetectionService.update_config(params)
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@detection_bp.route('/statistics', methods=['GET'])
@metrics.counter('detection_statistics_requests_total', 'Number of detection statistics requests')
def get_detection_statistics():
    """Get detection statistics."""
    try:
        # Get optional time range
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        
        # Get statistics
        stats = DetectionService.get_statistics(
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