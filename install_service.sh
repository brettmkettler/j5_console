#!/bin/bash

# J5 Console Auto-Start Installation Script
# Run this script on your Raspberry Pi to set up automatic startup

echo "🚀 Installing J5 Console Auto-Start Service..."

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash install_service.sh"
    exit 1
fi

# Check if service file exists
if [ ! -f "j5-console.service" ]; then
    echo "❌ Service file 'j5-console.service' not found!"
    echo "Make sure you're running this from the Desktop/j5_console directory"
    exit 1
fi

echo "📋 Installing systemd service..."

# Copy service file to systemd directory
cp j5-console.service /etc/systemd/system/

# Set proper permissions
chmod 644 /etc/systemd/system/j5-console.service

# Reload systemd to recognize the new service
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable j5-console.service

echo "✅ Service installed successfully!"
echo ""
echo "📋 Available commands:"
echo "  sudo systemctl start j5-console     # Start the service now"
echo "  sudo systemctl stop j5-console      # Stop the service"
echo "  sudo systemctl restart j5-console   # Restart the service"
echo "  sudo systemctl status j5-console    # Check service status"
echo "  sudo systemctl disable j5-console   # Disable auto-start"
echo ""
echo "📊 To view logs:"
echo "  sudo journalctl -u j5-console -f    # Follow live logs"
echo "  sudo journalctl -u j5-console       # View all logs"
echo ""
echo "🔄 The service will now start automatically on boot!"
echo "🚀 Starting service now..."

# Start the service
systemctl start j5-console.service

# Show status
echo ""
echo "📊 Service Status:"
systemctl status j5-console.service --no-pager -l
