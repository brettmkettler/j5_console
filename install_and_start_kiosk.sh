#!/bin/bash

# J5 Console Complete Installation and Kiosk Startup Script
# Installs all services and immediately starts kiosk mode

echo "🚀 Installing J5 Console Complete System and Starting Kiosk..."
echo ""

# Check if running as root (needed for systemd)
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    echo "Usage: sudo bash install_and_start_kiosk.sh"
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

# Install system packages
echo "📦 Installing system packages..."
apt update
apt install -y python3-pip python3-venv chromium-browser unclutter xdotool xinit xserver-xorg x11-xserver-utils
apt install -y xserver-xorg-input-evdev  # Touch screen support

# Install Node.js if not present
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js 18.x..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

# Create Python virtual environment if it doesn't exist
if [ ! -d "$USER_HOME/Desktop/venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    sudo -u $ACTUAL_USER python3 -m venv "$USER_HOME/Desktop/venv"
    sudo -u $ACTUAL_USER "$USER_HOME/Desktop/venv/bin/pip" install -r requirements.txt
fi

# Install J5 Console API service
echo "📋 Installing J5 Console API service..."
cp j5-console.service /etc/systemd/system/
chmod 644 /etc/systemd/system/j5-console.service

# Setup BtBmsDisplay
echo "📋 Setting up BtBmsDisplay..."
cd BtBmsDisplay

# Install npm dependencies
echo "  Installing npm dependencies..."
sudo -u $ACTUAL_USER npm install

# Build application
echo "  Building application..."
sudo -u $ACTUAL_USER npm run build

# Go back to main directory
cd ..

# Make scripts executable
chmod +x start_j5_kiosk.sh
chmod +x stop_j5_kiosk.sh
chmod +x start_local_kiosk.sh 2>/dev/null || true

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable j5-console.service

echo ""
echo "✅ Installation complete! Starting services and kiosk mode..."
echo ""

# Start J5 Console service
echo "🔧 Starting J5 Console API service..."
systemctl start j5-console.service
sleep 3

# Check if service started successfully
if systemctl is-active --quiet j5-console.service; then
    echo "✅ J5 Console API service started successfully"
else
    echo "⚠️ J5 Console API service may have issues, but continuing..."
fi

# Switch to user and start kiosk mode
echo "🖥️ Starting kiosk mode..."
echo "  Switching to user $ACTUAL_USER and launching kiosk..."

# Create a startup script for the user
cat > /tmp/start_kiosk_as_user.sh << EOF
#!/bin/bash
cd "$USER_HOME/Desktop/j5_console"
export DISPLAY=:0
./start_j5_kiosk.sh
EOF

chmod +x /tmp/start_kiosk_as_user.sh
chown $ACTUAL_USER:$ACTUAL_USER /tmp/start_kiosk_as_user.sh

# Start X11 and kiosk as the actual user
sudo -u $ACTUAL_USER bash -c "
    export HOME='$USER_HOME'
    cd '$USER_HOME/Desktop/j5_console'
    
    # Start X11 if not running
    if [ -z \"\$DISPLAY\" ]; then
        export DISPLAY=:0
        startx &
        sleep 5
    fi
    
    # Start the kiosk
    ./start_j5_kiosk.sh
" &

echo ""
echo "✅ J5 Console Complete System installed and started!"
echo ""
echo "📋 What was installed and started:"
echo "  ✅ J5 Console API service (port 5000) - Auto-enabled on boot"
echo "  ✅ BtBmsDisplay web interface (port 3000)"
echo "  ✅ Chromium kiosk mode with touch support and 2.0 zoom"
echo "  ✅ Python virtual environment with dependencies"
echo "  ✅ Node.js and npm dependencies"
echo ""
echo "🔧 Kiosk Features:"
echo "  • Touch events enabled"
echo "  • 2.0x zoom for larger UI elements"
echo "  • Full-screen mode"
echo "  • Screen power management disabled"
echo "  • Mouse cursor auto-hide"
echo ""
echo "📋 Available commands:"
echo "  sudo systemctl status j5-console        # Check API service"
echo "  ./start_j5_kiosk.sh                     # Restart kiosk manually"
echo "  ./stop_j5_kiosk.sh                      # Stop kiosk"
echo "  pkill -f chromium-browser               # Kill browser only"
echo ""
echo "🌐 The kiosk should now be running at http://localhost:3000"
echo "🔄 The J5 Console service will start automatically on boot"
