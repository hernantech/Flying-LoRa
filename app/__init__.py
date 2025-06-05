import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_flask_exporter import PrometheusMetrics

from .config.config import config
from .utils.logging import setup_logging

# Initialize extensions
socketio = SocketIO()
limiter = Limiter(key_func=get_remote_address)
metrics = PrometheusMetrics.for_app_factory()

def create_app(config_name=None):
    """Create Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Configure app
    app.config['SECRET_KEY'] = config.get('JWT_SECRET', 'dev-secret-key')
    app.config['CORS_ORIGINS'] = config.get('security.cors_origins', [])
    app.config['RATELIMIT_DEFAULT'] = f"{config.get('security.rate_limit', 100)}/minute"
    
    # Initialize extensions
    CORS(app)
    limiter.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins=app.config['CORS_ORIGINS'],
        ping_interval=config.get('websocket.ping_interval', 25),
        ping_timeout=config.get('websocket.ping_timeout', 10),
        max_size=config.get('websocket.max_message_size', 1048576)
    )
    metrics.init_app(app)
    
    # Setup logging
    setup_logging(app)
    
    # Register blueprints
    from .api.detection import detection_bp
    from .api.localization import localization_bp
    from .api.drone import drone_bp
    from .api.lora import lora_bp
    from .api.system import system_bp
    
    app.register_blueprint(detection_bp, url_prefix='/api/detection')
    app.register_blueprint(localization_bp, url_prefix='/api/localization')
    app.register_blueprint(drone_bp, url_prefix='/api/drone')
    app.register_blueprint(lora_bp, url_prefix='/api/lora')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    
    # Register websocket handlers
    from .websockets.detection import register_detection_handlers
    from .websockets.telemetry import register_telemetry_handlers
    from .websockets.visualization import register_visualization_handlers
    
    register_detection_handlers(socketio)
    register_telemetry_handlers(socketio)
    register_visualization_handlers(socketio)
    
    # Register error handlers
    from .utils.errors import register_error_handlers
    register_error_handlers(app)
    
    # Register CLI commands
    from .utils.cli import register_cli_commands
    register_cli_commands(app)
    
    # Register middleware
    from .utils.middleware import register_middleware
    register_middleware(app)
    
    return app 