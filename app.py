import os
import sys
import logging
from dotenv import load_dotenv
from app import create_app, socketio
from app.config.config import config

# Load environment variables
load_dotenv()

# Create Flask application
app = create_app()

# Configure logging
logger = logging.getLogger(__name__)

@app.before_first_request
def before_first_request():
    """Initialize application before first request."""
    try:
        # Validate configuration
        if not config.validate():
            logger.error("Invalid configuration. Please check your settings.")
            sys.exit(1)
        
        # Initialize services
        from app.services.detection_service import DetectionService
        from app.services.localization_service import LocalizationService
        from app.services.drone_service import DroneService
        from app.services.lora_service import LoRaService
        
        DetectionService.initialize()
        LocalizationService.initialize()
        DroneService.initialize()
        LoRaService.initialize()
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        sys.exit(1)

@app.route('/health')
def health_check():
    """Basic health check endpoint."""
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    host = config.get('server.host', '0.0.0.0')
    port = config.get('server.port', 5000)
    debug = config.get('server.debug', False)
    
    # Configure SSL if in production
    ssl_context = None
    if os.getenv('FLASK_ENV') == 'production':
        ssl_cert = config.get('security.ssl_cert')
        ssl_key = config.get('security.ssl_key')
        if ssl_cert and ssl_key:
            ssl_context = (ssl_cert, ssl_key)
    
    try:
        logger.info(f"Starting server on {host}:{port}")
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=config.get('development.hot_reload', False),
            ssl_context=ssl_context
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1) 