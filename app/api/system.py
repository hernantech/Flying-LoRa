from flask import Blueprint, jsonify, request
from flask_limiter.util import get_remote_address
from app import limiter, metrics, config
from app.utils.auth import require_api_key
from app.utils.validation import validate_json
import psutil
import os
import time

system_bp = Blueprint('system', __name__)

# Apply rate limiting to all endpoints in this blueprint
@system_bp.before_request
@require_api_key
def before_request():
    """Authenticate and rate limit all requests to this blueprint."""
    pass

@system_bp.route('/metrics', methods=['GET'])
@metrics.counter('system_metrics_requests_total', 'Number of system metrics requests')
@limiter.limit("60/minute")
def get_metrics():
    """Get system performance metrics."""
    try:
        # Collect system metrics
        metrics_data = {
            'cpu': {
                'percent': psutil.cpu_percent(interval=1),
                'count': psutil.cpu_count(),
                'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'network': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv,
                'packets_sent': psutil.net_io_counters().packets_sent,
                'packets_recv': psutil.net_io_counters().packets_recv
            },
            'process': {
                'pid': os.getpid(),
                'memory_percent': psutil.Process().memory_percent(),
                'cpu_percent': psutil.Process().cpu_percent(),
                'threads': psutil.Process().num_threads(),
                'open_files': len(psutil.Process().open_files())
            },
            'timestamp': time.time()
        }
        
        return jsonify({
            'status': 'success',
            'data': metrics_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@system_bp.route('/health', methods=['GET'])
@metrics.counter('system_health_requests_total', 'Number of system health requests')
def health_check():
    """Get system health status."""
    try:
        # Check system health
        health_data = {
            'status': 'healthy',
            'services': {
                'detection': True,  # Replace with actual service checks
                'localization': True,
                'drone': True,
                'lora': True,
                'database': True,
                'redis': True
            },
            'uptime': time.time() - psutil.boot_time(),
            'timestamp': time.time()
        }
        
        return jsonify({
            'status': 'success',
            'data': health_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@system_bp.route('/config', methods=['GET', 'POST'])
@metrics.counter('system_config_requests_total', 'Number of system configuration requests')
@limiter.limit("10/minute")
def system_config():
    """Get or update system configuration."""
    try:
        if request.method == 'GET':
            # Get current configuration
            current_config = config.get_all()
            
            return jsonify({
                'status': 'success',
                'data': current_config
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
            config.update(params)
            
            # Save configuration to file
            config.save()
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated successfully'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@system_bp.route('/logs', methods=['GET'])
@metrics.counter('system_logs_requests_total', 'Number of system logs requests')
@limiter.limit("30/minute")
def get_logs():
    """Get system logs."""
    try:
        # Get query parameters
        level = request.args.get('level', 'INFO')
        limit = request.args.get('limit', default=100, type=int)
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        
        # Get log file path from config
        log_file = config.get('logging.file')
        
        if not os.path.exists(log_file):
            return jsonify({
                'status': 'error',
                'message': 'Log file not found'
            }), 404
        
        # Read and filter logs
        logs = []
        with open(log_file, 'r') as f:
            for line in f:
                # Add log parsing and filtering logic here
                logs.append(line.strip())
        
        return jsonify({
            'status': 'success',
            'data': logs[-limit:]  # Return only the last 'limit' logs
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@system_bp.route('/version', methods=['GET'])
@metrics.counter('system_version_requests_total', 'Number of system version requests')
def get_version():
    """Get system version information."""
    try:
        version_info = {
            'version': '1.0.0',  # Replace with actual version
            'build': '123',      # Replace with actual build number
            'commit': 'abc123',  # Replace with actual commit hash
            'python': '.'.join(map(str, os.sys.version_info[:3])),
            'platform': os.sys.platform,
            'architecture': os.sys.maxsize.bit_length() + 1
        }
        
        return jsonify({
            'status': 'success',
            'data': version_info
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 