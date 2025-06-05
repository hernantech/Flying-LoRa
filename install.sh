#!/bin/bash
set -e

# Configuration
INSTALL_DIR="/opt/flying-lora"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="jetson-localization"
USER="jetson"
GROUP="jetson"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Log function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root"
fi

# Check system requirements
log "Checking system requirements..."
if ! command -v python3 >/dev/null; then
    error "Python 3 is required but not installed"
fi

if ! command -v pip3 >/dev/null; then
    error "pip3 is required but not installed"
fi

# Install system dependencies
log "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    redis-server \
    postgresql \
    postgresql-contrib \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    python3-gst-1.0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    nginx

# Create user and group if they don't exist
log "Setting up user and group..."
if ! getent group "$GROUP" >/dev/null; then
    groupadd "$GROUP"
fi
if ! getent passwd "$USER" >/dev/null; then
    useradd -m -g "$GROUP" -s /bin/bash "$USER"
fi

# Create installation directory
log "Creating installation directory..."
mkdir -p "$INSTALL_DIR"
chown -R "$USER:$GROUP" "$INSTALL_DIR"

# Copy application files
log "Copying application files..."
cp -r . "$INSTALL_DIR/"
chown -R "$USER:$GROUP" "$INSTALL_DIR"

# Create virtual environment
log "Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install Python dependencies
log "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r "$INSTALL_DIR/requirements.txt"

# Install additional Jetson-specific packages
log "Installing Jetson-specific packages..."
pip3 install jetson-stats jtop jetson-utils

# Set up configuration
log "Setting up configuration..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    warn "Please update the configuration in $INSTALL_DIR/.env"
fi

# Set up database
log "Setting up database..."
sudo -u postgres psql -c "CREATE DATABASE flying_lora;" || true
sudo -u postgres psql -c "CREATE USER $USER WITH PASSWORD 'change_me';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE flying_lora TO $USER;" || true

# Initialize database
log "Initializing database..."
source "$INSTALL_DIR/.env"
FLASK_APP=app.py flask db upgrade

# Set up systemd service
log "Setting up systemd service..."
cp "$INSTALL_DIR/jetson-localization.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Set up hardware permissions
log "Setting up hardware permissions..."
usermod -a -G dialout "$USER"  # For serial port access
usermod -a -G video "$USER"    # For camera access
usermod -a -G gpio "$USER"     # For GPIO access
usermod -a -G i2c "$USER"      # For I2C access

# Create log directory
log "Setting up logging..."
mkdir -p "$INSTALL_DIR/logs"
chown -R "$USER:$GROUP" "$INSTALL_DIR/logs"

# Set up Nginx (if needed)
log "Setting up Nginx..."
if [ -f "$INSTALL_DIR/nginx.conf" ]; then
    cp "$INSTALL_DIR/nginx.conf" "/etc/nginx/sites-available/flying-lora"
    ln -sf "/etc/nginx/sites-available/flying-lora" "/etc/nginx/sites-enabled/"
    systemctl restart nginx
fi

# Download YOLOv5 model
log "Downloading YOLOv5 model..."
sudo -u "$USER" python3 -c "from ultralytics import YOLO; YOLO('yolov5s.pt')"

# Final setup
log "Performing final setup..."
systemctl start "$SERVICE_NAME"

# Installation complete
log "Installation complete!"
log "Please:"
log "1. Update the configuration in $INSTALL_DIR/.env"
log "2. Update the database password"
log "3. Check the service status with: systemctl status $SERVICE_NAME"
log "4. View logs with: journalctl -u $SERVICE_NAME" 