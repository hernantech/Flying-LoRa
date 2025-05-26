# Operation Mode Control Server

This Flask server runs on the Jetson and controls operation modes (1, 2, 3).

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python app.py
```

The server will start on port 8080 and be accessible from all network interfaces.

## API Endpoints

### Get Current Mode
- **URL:** `/mode`
- **Method:** `GET`
- **Response:** `{"mode": <current_mode>}`

### Set Mode
- **URL:** `/mode`
- **Method:** `POST`
- **Body:** `{"mode": <new_mode>}`
- **Valid modes:** 1, 2, or 3
- **Response:** `{"mode": <new_mode>}`

### Get Server Status
- **URL:** `/status`
- **Method:** `GET`
- **Response:** `{"status": "running", "mode": <current_mode>}`

## Example Usage

To get the current mode:
```bash
curl http://localhost:8080/mode
```

To set a new mode:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"mode": 2}' http://localhost:8080/mode
```

To get server status:
```bash
curl http://localhost:8080/status
``` 