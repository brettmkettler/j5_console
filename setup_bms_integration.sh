#!/bin/bash

# Overkill Solar BMS Integration Setup Script
# Sets up Bluetooth BMS monitoring for J5 Console

echo "🔋 Setting up Overkill Solar BMS Integration..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash setup_bms_integration.sh"
    exit 1
fi

# Get the actual user
ACTUAL_USER=${SUDO_USER:-$(whoami)}
USER_HOME="/home/$ACTUAL_USER"

echo "📋 Configuration:"
echo "  User: $ACTUAL_USER"
echo "  Home: $USER_HOME"
echo "  Project: $USER_HOME/Desktop/j5_console"
echo ""

# Install system Bluetooth packages
echo "📦 Installing Bluetooth packages..."
apt update
apt install -y bluetooth bluez python3-pip

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
sudo -u $ACTUAL_USER "$USER_HOME/Desktop/venv/bin/pip" install bleak requests

# Make BMS service executable
chmod +x overkill_bms_service.py

# Install systemd service
echo "⚙️ Installing BMS service..."
cp overkill_bms_service.service /etc/systemd/system/
chmod 644 /etc/systemd/system/overkill_bms_service.service

# Reload systemd
systemctl daemon-reload

echo ""
echo "✅ BMS Integration setup complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Find your BMS MAC addresses:"
echo "   sudo bluetoothctl"
echo "   scan on"
echo "   (look for your Overkill BMS devices)"
echo ""
echo "2. Edit overkill_bms_service.py and update MAC addresses:"
echo "   nano overkill_bms_service.py"
echo "   # Update these lines:"
echo "   # self.left_bms_mac = \"XX:XX:XX:XX:XX:XX\"   # Left track BMS"
echo "   # self.right_bms_mac = \"YY:YY:YY:YY:YY:YY\"  # Right track BMS"
echo ""
echo "3. Enable and start the service:"
echo "   sudo systemctl enable overkill_bms_service"
echo "   sudo systemctl start overkill_bms_service"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status overkill_bms_service"
echo "   sudo journalctl -u overkill_bms_service -f"
echo ""
echo "🌐 The BMS data will automatically appear in your BtBmsDisplay!"
echo "📊 Left track: Batteries 1-4, Right track: Batteries 5-8"
