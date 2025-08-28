#!/bin/bash

# J5 Console Complete Installation Script
# Installs j5_console.py service AND BtBmsDisplay kiosk mode with X11

echo "🚀 Installing J5 Console Complete System..."
echo ""

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash install_service.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$(whoami)}
USER_HOME="/home/$ACTUAL_USER"

echo "📋 Configuration:"
echo "  User: $ACTUAL_USER"
echo "  Home: $USER_HOME"
echo "  Project: $USER_HOME/Desktop/j5_console"
echo ""

# Check if main service file exists
if [ ! -f "j5-console.service" ]; then
    echo "❌ Service file 'j5-console.service' not found!"
    echo "Make sure you're running this from the Desktop/j5_console directory"
    exit 1
fi

# Install Node.js if not present
echo "📦 Installing Node.js and system packages..."
if ! command -v node &> /dev/null; then
    echo "  Installing Node.js 18.x..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

# Install kiosk system packages
apt update
apt install -y chromium-browser unclutter xdotool xinit xserver-xorg x11-xserver-utils
apt install -y xserver-xorg-input-evdev  # Touch screen support

echo "📋 Installing J5 Console API service..."

# Copy main service file to systemd directory
cp j5-console.service /etc/systemd/system/
chmod 644 /etc/systemd/system/j5-console.service

echo "📋 Setting up BtBmsDisplay..."

# Install BtBmsDisplay dependencies and build
cd BtBmsDisplay
echo "  Installing npm dependencies..."
npm install
echo "  Building application..."
npm run build

# Make kiosk scripts executable
chmod +x kiosk-startup.sh
chmod +x .xinitrc
chown $ACTUAL_USER:$ACTUAL_USER kiosk-startup.sh
chown $ACTUAL_USER:$ACTUAL_USER .xinitrc

# Copy xinitrc to user home
cp .xinitrc "$USER_HOME/.xinitrc"
chown $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.xinitrc"
chmod +x "$USER_HOME/.xinitrc"

# Install BtBmsDisplay services
echo "📋 Installing BtBmsDisplay services..."
cp j5-display-kiosk.service /etc/systemd/system/
cp kiosk-x11.service /etc/systemd/system/
chmod 644 /etc/systemd/system/j5-display-kiosk.service
chmod 644 /etc/systemd/system/kiosk-x11.service

# Go back to main directory
cd ..

# Configure auto-login for kiosk
echo "👤 Configuring auto-login..."
systemctl set-default multi-user.target

# Add auto-start X11 to bashrc if not already present
if ! grep -q "startx" "$USER_HOME/.bashrc"; then
    echo "" >> "$USER_HOME/.bashrc"
    echo "# Auto-start X11 for J5 Console Kiosk" >> "$USER_HOME/.bashrc"
    echo "if [ -z \"\$DISPLAY\" ] && [ \"\$(tty)\" = \"/dev/tty1\" ]; then" >> "$USER_HOME/.bashrc"
    echo "    startx" >> "$USER_HOME/.bashrc"
    echo "fi" >> "$USER_HOME/.bashrc"
    chown $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.bashrc"
fi

# Reload systemd to recognize all services
systemctl daemon-reload

# Enable all services
echo "⚙️ Enabling services..."
systemctl enable j5-console.service
systemctl enable j5-display-kiosk.service
systemctl enable kiosk-x11.service

echo ""
echo "✅ J5 Console Complete System installed successfully!"
echo ""
echo "📋 What was installed:"
echo "  ✅ J5 Console API service (port 5000)"
echo "  ✅ BtBmsDisplay web interface (port 3000)"
echo "  ✅ Kiosk mode with touch support and 2.0 zoom"
echo "  ✅ Auto-start X11 and full-screen display"
echo "  ✅ All services enabled for boot startup"
echo ""
echo "🔧 Kiosk Features:"
echo "  • Touch events enabled"
echo "  • 2.0x zoom for larger UI elements"
echo "  • Full-screen mode"
echo "  • Auto-start on boot"
echo "  • Screen power management disabled"
echo ""
echo "🚀 Starting all services now..."

# Start all services
systemctl start j5-console.service
systemctl start j5-display-kiosk.service
systemctl start kiosk-x11.service

echo ""
echo "📊 Service Status:"
echo ""
echo "J5 Console API:"
systemctl status j5-console.service --no-pager -l
echo ""
echo "BtBmsDisplay:"
systemctl status j5-display-kiosk.service --no-pager -l
echo ""
echo "Kiosk X11:"
systemctl status kiosk-x11.service --no-pager -l
echo ""
echo "📋 Available commands:"
echo "  sudo systemctl status j5-console        # Check API service"
echo "  sudo systemctl status j5-display-kiosk  # Check display service"
echo "  sudo systemctl status kiosk-x11         # Check kiosk service"
echo ""
echo "🔄 The complete system will start automatically on boot!"
echo "🌐 Access the interface at http://localhost:3000 or via kiosk mode"
