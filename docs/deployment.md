# Flying LoRa Deployment Guide

This guide provides step-by-step instructions for deploying the Flying LoRa system on a Jetson Nano.

## Table of Contents
1. [Hardware Requirements](#hardware-requirements)
2. [Software Prerequisites](#software-prerequisites)
3. [Installation](#installation)
4. [Network Configuration](#network-configuration)
5. [Performance Tuning](#performance-tuning)
6. [Troubleshooting](#troubleshooting)

## Hardware Requirements

### Minimum Specifications
- NVIDIA Jetson Nano Developer Kit (4GB)
- MicroSD card (32GB+, UHS-1 or better)
- 5V 4A power supply
- Active cooling solution (fan)
- USB camera or CSI camera module
- LoRa transceiver module (RFM95W)
- GPS module (optional)

### Hardware Connections
1. LoRa Module (SPI):
   - MOSI -> GPIO 10 (SPI0_MOSI)
   - MISO -> GPIO 9 (SPI0_MISO)
   - SCK -> GPIO 11 (SPI0_SCK)
   - CS -> GPIO 8 (SPI0_CS0)
   - RST -> GPIO 22
   - DIO0 -> GPIO 17

2. Camera:
   - For USB camera: Connect to USB 3.0 port
   - For CSI camera: Connect to MIPI CSI port

## Software Prerequisites

1. Operating System:
   ```bash
   # Download and flash JetPack 4.6
   # Follow NVIDIA's instructions for initial setup
   ```

2. System Updates:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

3. Required Packages:
   ```bash
   sudo apt install -y \
       python3-pip \
       python3-dev \
       build-essential \
       libpq-dev \
       redis-server \
       postgresql \
       nginx
   ```

## Installation

1. Clone Repository:
   ```bash
   git clone https://github.com/abumostafa/Flying-LoRa.git
   cd Flying-LoRa
   ```

2. Run Installation Script:
   ```bash
   sudo chmod +x install.sh
   sudo ./install.sh
   ```

3. Configure Environment:
   ```bash
   # Edit environment variables
   sudo nano /opt/flying-lora/.env
   
   # Set the following variables:
   FLASK_ENV=production
   FLASK_APP=app.py
   DATABASE_URL=postgresql://jetson:password@localhost/flying_lora
   REDIS_URL=redis://localhost:6379/0
   API_KEY=your_secure_api_key
   LORA_FREQUENCY=915.0
   DETECTION_MODEL=yolov5s
   ```

4. Start Services:
   ```bash
   sudo systemctl start redis-server
   sudo systemctl start postgresql
   sudo systemctl start jetson-localization
   sudo systemctl start nginx
   ```

## Network Configuration

1. Firewall Setup:
   ```bash
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw allow 5000/tcp  # API
   sudo ufw allow 9090/tcp  # Metrics
   ```

2. SSL Configuration (Optional):
   ```bash
   # Install certbot
   sudo apt install -y certbot python3-certbot-nginx
   
   # Generate certificate
   sudo certbot --nginx -d your-domain.com
   ```

3. Nginx Configuration:
   ```nginx
   # /etc/nginx/sites-available/flying-lora
   server {
       listen 80;
       server_name your-domain.com;
   
       location / {
           proxy_pass http://localhost:5000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   
       location /metrics {
           proxy_pass http://localhost:9090;
       }
   }
   ```

## Performance Tuning

1. Jetson Configuration:
   ```bash
   # Set maximum performance mode
   sudo nvpmodel -m 0
   sudo jetson_clocks
   ```

2. System Optimization:
   ```bash
   # Edit /etc/sysctl.conf
   net.core.somaxconn = 1024
   vm.swappiness = 10
   vm.dirty_ratio = 60
   vm.dirty_background_ratio = 2
   ```

3. PostgreSQL Tuning:
   ```bash
   # Edit /etc/postgresql/12/main/postgresql.conf
   shared_buffers = 1GB
   work_mem = 32MB
   maintenance_work_mem = 256MB
   effective_cache_size = 3GB
   ```

4. Application Settings:
   ```yaml
   # config/production_config.yml
   gunicorn:
     workers: 4
     worker_class: eventlet
     threads: 2
     timeout: 120
   
   detection:
     batch_size: 8
     confidence_threshold: 0.4
     max_detections: 100
   
   websocket:
     ping_interval: 25
     ping_timeout: 120
   ```

## Troubleshooting

### Common Issues

1. Service Won't Start:
   ```bash
   # Check service status
   sudo systemctl status jetson-localization
   
   # View logs
   sudo journalctl -u jetson-localization -n 100
   ```

2. Performance Issues:
   ```bash
   # Monitor system resources
   jtop
   
   # Check GPU usage
   tegrastats
   ```

3. Database Issues:
   ```bash
   # Check PostgreSQL logs
   sudo tail -f /var/log/postgresql/postgresql-12-main.log
   
   # Reset database
   sudo -u postgres psql
   DROP DATABASE flying_lora;
   CREATE DATABASE flying_lora;
   ```

4. LoRa Communication:
   ```bash
   # Check permissions
   sudo usermod -a -G dialout jetson
   sudo chmod 666 /dev/spidev0.0
   
   # Test LoRa module
   python3 tests/lora_test.py
   ```

### Log Files

Important log locations:
- Application: `/opt/flying-lora/logs/`
- System: `/var/log/syslog`
- Nginx: `/var/log/nginx/`
- PostgreSQL: `/var/log/postgresql/`

### Support

For additional support:
1. Check the [GitHub Issues](https://github.com/abumostafa/Flying-LoRa/issues)
2. Review the [API Documentation](docs/openapi.yaml)
3. Contact the development team

## Monitoring

1. Prometheus Metrics:
   - Available at `http://your-domain.com:9090/metrics`
   - Key metrics:
     - `detection_latency_seconds`
     - `lora_message_latency_seconds`
     - `system_cpu_usage_percent`
     - `system_memory_usage_bytes`

2. Logging:
   - JSON-formatted logs
   - Rotation enabled (10MB per file)
   - 5 backup files kept
   - Debug mode available

3. Health Checks:
   - Endpoint: `http://your-domain.com/api/system/health`
   - Monitors: database, Redis, LoRa, detection service 