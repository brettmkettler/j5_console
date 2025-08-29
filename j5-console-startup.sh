#!/bin/bash

# J5 Console Master Startup Script
# Starts all services in proper order and launches kiosk mode

set -e  # Exit on any error

# Configuration
USER_HOME="/home/seanfuchs"
PROJECT_DIR="$USER_HOME/Desktop/j5_console"
DISPLAY_DIR="$PROJECT_DIR/BtBmsDisplay"
LOG_FILE="/var/log/j5-console-startup.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo bash j5-console-startup.sh"
    exit 1
fi

log "🚀 Starting J5 Console System..."

# Function to wait for service to be active
wait_for_service() {
    local service_name=$1
    local max_attempts=30
    local attempt=0
    
    log "⏳ Waiting for $service_name to start..."
    
    while [ $attempt -lt $max_attempts ]; do
        if systemctl is-active --quiet "$service_name"; then
            log "✅ $service_name is active"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "❌ $service_name failed to start within timeout"
    return 1
}

# Function to check service health
check_service_health() {
    local service_name=$1
    local port=$2
    
    if [ -n "$port" ]; then
        log "🔍 Checking $service_name health on port $port..."
        if curl -s -f "http://localhost:$port" > /dev/null 2>&1; then
            log "✅ $service_name health check passed"
            return 0
        else
            log "⚠️ $service_name health check failed"
            return 1
        fi
    fi
}

# Stop any existing services
log "🛑 Stopping existing services..."
systemctl stop kiosk-x11.service 2>/dev/null || true
systemctl stop j5-display-kiosk.service 2>/dev/null || true
systemctl stop j5-console.service 2>/dev/null || true
systemctl stop overkill-bms-service.service 2>/dev/null || true

# Wait a moment for services to stop
sleep 3

# Start services in dependency order
log "🔧 Starting core services..."

# 1. Start BMS service first (provides battery data)
log "📊 Starting Overkill BMS Service..."
systemctl start overkill-bms-service.service
wait_for_service "overkill-bms-service.service"

# 2. Start J5 Console service (GPIO, servos, LEDs, API)
log "🎛️ Starting J5 Console Service..."
systemctl start j5-console.service
wait_for_service "j5-console.service"

# Wait for J5 Console API to be ready
sleep 5
check_service_health "j5-console" "5000"

# 3. Start Display service (web app)
log "🖥️ Starting J5 Display Service..."
systemctl start j5-display-kiosk.service
wait_for_service "j5-display-kiosk.service"

# Wait for web app to be ready
sleep 10
check_service_health "j5-display-kiosk" "3000"

# 4. Start kiosk mode (X11 and Chromium)
log "🖼️ Starting Kiosk Mode..."
systemctl start kiosk-x11.service
wait_for_service "kiosk-x11.service"

# Final health checks
log "🔍 Performing final system checks..."

# Check all services are running
services=("overkill-bms-service.service" "j5-console.service" "j5-display-kiosk.service" "kiosk-x11.service")
all_healthy=true

for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        log "✅ $service is running"
    else
        log "❌ $service is not running"
        all_healthy=false
    fi
done

# Check web services are responding
if check_service_health "j5-console" "5000" && check_service_health "j5-display-kiosk" "3000"; then
    log "✅ All web services are responding"
else
    log "⚠️ Some web services may not be fully ready"
    all_healthy=false
fi

# Final status
if [ "$all_healthy" = true ]; then
    log "🎉 J5 Console System startup completed successfully!"
    log "🌐 Web interface available at: http://localhost:3000"
    log "🔧 API available at: http://localhost:5000"
else
    log "⚠️ J5 Console System started with some issues - check service logs"
fi

log "📋 Service Status Summary:"
systemctl status overkill-bms-service.service --no-pager -l | head -3 | tail -1 >> "$LOG_FILE"
systemctl status j5-console.service --no-pager -l | head -3 | tail -1 >> "$LOG_FILE"
systemctl status j5-display-kiosk.service --no-pager -l | head -3 | tail -1 >> "$LOG_FILE"
systemctl status kiosk-x11.service --no-pager -l | head -3 | tail -1 >> "$LOG_FILE"

log "📊 View logs with: sudo journalctl -f -u j5-console.service -u j5-display-kiosk.service -u kiosk-x11.service -u overkill-bms-service.service"

exit 0
