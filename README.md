# Flying LoRa Server

A production-ready Flask server for the Flying LoRa project, providing real-time object detection, localization, drone control, and LoRa communication capabilities.

## Features

- **Object Detection**
  - Real-time object detection using YOLOv5
  - Configurable detection parameters
  - Detection statistics and performance metrics
  - WebSocket streaming of detection results

- **Object Localization**
  - Multi-sensor triangulation
  - Real-time position tracking
  - Historical trajectory analysis
  - Confidence-based filtering

- **Drone Control**
  - Real-time telemetry monitoring
  - Mission planning and execution
  - Position and altitude control
  - Safety monitoring and failsafes

- **LoRa Communication**
  - Reliable message transmission
  - Priority-based message handling
  - Network status monitoring
  - Automatic retransmission

- **System Management**
  - Configuration management
  - Performance monitoring
  - Health checks
  - Logging and diagnostics

## Architecture

### Core Components

1. **API Endpoints**
   - RESTful API for all core functionalities
   - Rate limiting and authentication
   - Comprehensive error handling
   - Prometheus metrics integration

2. **WebSocket Endpoints**
   - Real-time data streaming
   - Subscription-based updates
   - Efficient client-server communication
   - Automatic reconnection handling

3. **Configuration Management**
   - Environment-based configuration
   - Dynamic configuration updates
   - Secure secrets management
   - YAML-based configuration files

4. **Service Layer**
   - Detection Service
   - Localization Service
   - Drone Service
   - LoRa Service

## API Documentation

### Detection API

```
POST   /api/detection/start        - Start object detection
POST   /api/detection/stop         - Stop object detection
GET    /api/detection/status       - Get detection status
GET    /api/detection/latest       - Get latest detections
```

### Localization API

```
POST   /api/localization/compute   - Trigger localization
GET    /api/localization/objects   - Get localized objects
GET    /api/localization/history   - Get historical data
```

### Drone API

```
POST   /api/drone/command          - Send control command
GET    /api/drone/telemetry        - Get current telemetry
GET    /api/drone/position         - Get current position
```

### LoRa API

```
POST   /api/lora/send             - Send LoRa message
GET    /api/lora/receive          - Get received messages
GET    /api/lora/status           - Get LoRa status
```

### System API

```
GET    /api/system/metrics        - Get system metrics
GET    /api/system/health         - Health check
POST   /api/system/config         - Update configuration
```

### WebSocket Endpoints

```
/ws/detections     - Real-time detection stream
/ws/telemetry      - Real-time telemetry stream
/ws/visualization  - Real-time visualization data
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/flying-lora.git
   cd flying-lora
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Initialize the database:
   ```bash
   flask db upgrade
   ```

## Configuration

1. Base configuration: `config/base_config.yml`
2. Environment-specific: `config/development_config.yml` or `config/production_config.yml`
3. Environment variables: See `.env.example` for required variables

## Running the Server

### Development

```bash
flask run --debug
```

### Production

```bash
gunicorn -k eventlet -w 4 -b 0.0.0.0:5000 app:app
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run performance tests
pytest tests/performance/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For support, please open an issue on GitHub or contact the maintainers.