#!/bin/bash

# J5 Console Service Update Script
# Use this when you make changes to your code and want to restart the service

echo "🔄 Updating J5 Console Service..."

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash update_service.sh"
    exit 1
fi

# Check if service exists
if [ ! -f "/etc/systemd/system/j5-console.service" ]; then
    echo "❌ Service not installed!"
    echo "Run: sudo bash install_service.sh"
    exit 1
fi

echo "🛑 Stopping service..."
systemctl stop j5-console.service

echo "⏳ Waiting for clean shutdown..."
sleep 2

echo "🚀 Starting service with updated code..."
systemctl start j5-console.service

echo "⏳ Waiting for startup..."
sleep 3

echo ""
echo "📊 Service Status:"
systemctl status j5-console.service --no-pager -l

echo ""
echo "✅ Service updated and restarted!"
echo ""
echo "📋 Useful commands:"
echo "  sudo journalctl -u j5-console -f    # Follow live logs"
echo "  sudo systemctl status j5-console    # Check status"
echo "  curl http://localhost:5000/system/status  # Test API"
echo ""
echo "🌐 Access your updated console:"
echo "  http://your-pi-ip:5000/docs/"
