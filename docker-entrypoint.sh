#!/bin/bash
set -e

# Function to wait for a service to be ready
wait_for_service() {
    local host="$1"
    local port="$2"
    local service="$3"
    local timeout=30

    echo "Waiting for $service to be ready..."
    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port"; then
            echo "$service is ready!"
            return 0
        fi
        sleep 1
    done
    echo "Timeout waiting for $service"
    return 1
}

# Initialize application
init_app() {
    echo "Initializing application..."
    
    # Create required directories
    mkdir -p /app/logs /app/data /app/models
    
    # Set correct permissions
    chown -R nobody:nogroup /app/logs /app/data
    
    # Wait for required services
    if [[ -n "$REDIS_HOST" ]]; then
        wait_for_service "$REDIS_HOST" "${REDIS_PORT:-6379}" "Redis"
    fi
    
    if [[ -n "$DB_HOST" ]]; then
        wait_for_service "$DB_HOST" "${DB_PORT:-5432}" "Database"
    fi
    
    # Run database migrations if needed
    if [[ "$FLASK_ENV" != "testing" ]]; then
        echo "Running database migrations..."
        flask db upgrade
    fi
    
    # Initialize hardware if not in mock mode
    if [[ "$MOCK_HARDWARE" != "true" ]]; then
        echo "Initializing hardware..."
        # Add hardware initialization commands here
    fi
}

# Handle cleanup on exit
cleanup() {
    echo "Cleaning up..."
    # Add cleanup commands here
    exit 0
}
trap cleanup SIGTERM SIGINT

# Initialize the application
init_app

# Start the application
echo "Starting Flying LoRa server..."
exec "$@" 