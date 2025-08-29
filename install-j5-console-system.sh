#!/bin/bash

# J5 Console Complete System Installation Script
# Installs and configures all services, dependencies, and kiosk mode

set -e  # Exit on any error

# Configuration
USER_HOME="/home/seanfuchs"
PROJECT_DIR="$USER_HOME/Desktop/j5_console"
DISPLAY_DIR="$PROJECT_DIR/BtBmsDisplay"

echo "🤖 J5 Console Complete System Installation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo bash install-j5-console-system.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$(whoami)}
USER_HOME="/home/$ACTUAL_USER"
PROJECT_DIR="$USER_HOME/Desktop/j5_console"
DISPLAY_DIR="$PROJECT_DIR/BtBmsDisplay"

echo "📋 Configuration:"
echo "  User: $ACTUAL_USER"
echo "  Home: $USER_HOME"
echo "  Project: $PROJECT_DIR"
echo "  Display: $DISPLAY_DIR"
echo ""

# Verify project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PROJECT_DIR"
    echo "Please ensure the j5_console project is in the correct location."
    exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
apt update
apt upgrade -y

# Install system dependencies
echo "🔧 Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    chromium-browser \
    unclutter \
    xdotool \
    xinit \
    xserver-xorg \
    x11-xserver-utils \
    xserver-xorg-input-evdev \
    bluetooth \
    bluez \
    bluez-tools \
    curl \
    git \
    lsof

# Create Python virtual environment if it doesn't exist
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "$USER_HOME/Desktop/venv" ]; then
    sudo -u $ACTUAL_USER python3 -m venv "$USER_HOME/Desktop/venv"
fi

# Install Python dependencies
echo "📚 Installing Python dependencies..."
sudo -u $ACTUAL_USER "$USER_HOME/Desktop/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# Install Node.js dependencies for display app
echo "📱 Installing Node.js dependencies..."
cd "$DISPLAY_DIR"
sudo -u $ACTUAL_USER npm install
sudo -u $ACTUAL_USER npm run build

# Make scripts executable
echo "🔧 Setting up executable permissions..."
chmod +x "$PROJECT_DIR/j5-console-startup.sh"
chmod +x "$PROJECT_DIR/j5_console.py"
chmod +x "$PROJECT_DIR/overkill_bms_service.py"
chmod +x "$DISPLAY_DIR/kiosk-startup.sh"
chmod +x "$DISPLAY_DIR/.xinitrc"

# Set proper ownership
chown -R $ACTUAL_USER:$ACTUAL_USER "$PROJECT_DIR"

# Copy xinitrc to user home
cp "$DISPLAY_DIR/.xinitrc" "$USER_HOME/.xinitrc"
chown $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.xinitrc"
chmod +x "$USER_HOME/.xinitrc"

# Install systemd services
echo "⚙️ Installing systemd services..."

# Copy all service files to systemd
cp "$PROJECT_DIR/overkill_bms_service.service" /etc/systemd/system/
cp "$PROJECT_DIR/j5-console.service" /etc/systemd/system/
cp "$DISPLAY_DIR/j5-display-kiosk.service" /etc/systemd/system/
cp "$DISPLAY_DIR/kiosk-x11.service" /etc/systemd/system/

# Reload systemd daemon
systemctl daemon-reload

# Enable all services
echo "🚀 Enabling services..."
systemctl enable overkill-bms-service.service
systemctl enable j5-console.service
systemctl enable j5-display-kiosk.service
systemctl enable kiosk-x11.service

# Configure GPIO permissions
echo "🔌 Configuring GPIO permissions..."
usermod -a -G gpio $ACTUAL_USER

# Configure Bluetooth permissions
echo "📡 Configuring Bluetooth permissions..."
usermod -a -G bluetooth $ACTUAL_USER

# Configure auto-login for kiosk mode
echo "👤 Configuring auto-login..."
systemctl set-default multi-user.target

# Create auto-login override
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --noissue --autologin $ACTUAL_USER %I \$TERM
Type=idle
EOF

# Add auto-start X11 to bashrc if not already present
if ! grep -q "startx" "$USER_HOME/.bashrc"; then
    echo "" >> "$USER_HOME/.bashrc"
    echo "# Auto-start X11 for J5 Console Kiosk" >> "$USER_HOME/.bashrc"
    echo "if [ -z \"\$DISPLAY\" ] && [ \"\$(tty)\" = \"/dev/tty1\" ]; then" >> "$USER_HOME/.bashrc"
    echo "    startx" >> "$USER_HOME/.bashrc"
    echo "fi" >> "$USER_HOME/.bashrc"
    chown $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.bashrc"
fi

# Create startup script symlink for easy access
ln -sf "$PROJECT_DIR/j5-console-startup.sh" /usr/local/bin/j5-startup

# Create log directory
mkdir -p /var/log
touch /var/log/j5-console-startup.log
chown $ACTUAL_USER:$ACTUAL_USER /var/log/j5-console-startup.log

echo ""
echo "✅ J5 Console System Installation Complete!"
echo ""
echo "📋 What was installed and configured:"
echo "  ✅ System packages (Python, Node.js, Chromium, X11, Bluetooth)"
echo "  ✅ Python virtual environment with dependencies"
echo "  ✅ Node.js dependencies and built web app"
echo "  ✅ All systemd services with proper dependencies"
echo "  ✅ GPIO and Bluetooth permissions"
echo "  ✅ Auto-login and kiosk mode configuration"
echo "  ✅ Startup script available as 'j5-startup'"
echo ""
echo "🔧 Services installed:"
echo "  • overkill-bms-service.service (BMS data collection)"
echo "  • j5-console.service (GPIO, servos, LEDs, API)"
echo "  • j5-display-kiosk.service (Web interface)"
echo "  • kiosk-x11.service (Kiosk mode display)"
echo ""
echo "🚀 To start the system:"
echo "  Manual: sudo j5-startup"
echo "  Auto:   sudo reboot"
echo ""
echo "📊 Monitor services:"
echo "  sudo systemctl status overkill-bms-service j5-console j5-display-kiosk kiosk-x11"
echo ""
echo "📋 View logs:"
echo "  sudo journalctl -f -u overkill-bms-service -u j5-console -u j5-display-kiosk -u kiosk-x11"
echo ""
echo "🌐 Access points (after startup):"
echo "  Web Interface: http://localhost:3000"
echo "  API Endpoint:  http://localhost:5000"
echo ""
echo "🔄 Reboot now to start J5 Console in kiosk mode automatically!"
