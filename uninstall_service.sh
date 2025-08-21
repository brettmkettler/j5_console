#!/bin/bash

# J5 Console Auto-Start Uninstall Script
# Run this script to remove the J5 Console service

echo "🗑️  Uninstalling J5 Console Auto-Start Service..."

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash uninstall_service.sh"
    exit 1
fi

# Check if service exists
if [ ! -f "/etc/systemd/system/j5-console.service" ]; then
    echo "ℹ️  Service not found - may already be uninstalled"
else
    echo "🛑 Stopping J5 Console service..."
    systemctl stop j5-console.service 2>/dev/null || true
    
    echo "🚫 Disabling auto-start..."
    systemctl disable j5-console.service 2>/dev/null || true
    
    echo "🗑️  Removing service file..."
    rm -f /etc/systemd/system/j5-console.service
    
    echo "🔄 Reloading systemd..."
    systemctl daemon-reload
    
    echo "🧹 Resetting failed state (if any)..."
    systemctl reset-failed j5-console.service 2>/dev/null || true
fi

echo ""
echo "✅ J5 Console service uninstalled successfully!"
echo ""
echo "📋 What was removed:"
echo "  ❌ Auto-start on boot disabled"
echo "  ❌ Service stopped"
echo "  ❌ Service file deleted"
echo "  ❌ Systemd configuration cleaned"
echo ""
echo "📁 Your files remain untouched:"
echo "  ✅ j5_console.py - still in Desktop"
echo "  ✅ venv/ - still in Desktop"
echo "  ✅ All your code and data"
echo ""
echo "🔄 To run manually again:"
echo "  cd ~/Desktop"
echo "  source venv/bin/activate"
echo "  python j5_console.py"
echo ""
echo "🚀 To reinstall auto-start:"
echo "  sudo bash install_service.sh"
