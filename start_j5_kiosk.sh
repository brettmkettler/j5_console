#!/bin/bash

# J5 Console Simple Kiosk Startup Script
# Starts services and opens Chromium in kiosk mode

echo "🚀 Starting J5 Console Kiosk..."

# Kill any existing processes
pkill -f j5_console.py 2>/dev/null || true
pkill -f "node.*BtBmsDisplay" 2>/dev/null || true
pkill -f chromium-browser 2>/dev/null || true

# Wait a moment
sleep 2

# Start j5_console.py in background
echo "📡 Starting J5 Console API..."
cd ~/Desktop/j5_console
source venv/bin/activate
python j5_console.py &
J5_PID=$!

# Wait for API to start
sleep 5

# Start BtBmsDisplay in background
echo "🖥️ Starting BtBmsDisplay..."
cd ~/Desktop/j5_console/BtBmsDisplay
npm start &
DISPLAY_PID=$!

# Wait for web server to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if ! curl -s http://localhost:5000/api/system/status >/dev/null 2>&1; then
    echo "⚠️ J5 Console API not responding, but continuing..."
fi

if ! curl -s http://localhost:3000 >/dev/null 2>&1; then
    echo "⚠️ BtBmsDisplay not responding, but continuing..."
fi

# Disable screen blanking
xset -dpms 2>/dev/null || true
xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true

# Hide mouse cursor
unclutter -idle 1 &

echo "🌐 Opening Chromium in kiosk mode..."

# Start Chromium in kiosk mode with touch and zoom
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --disable-features=TranslateUI \
  --disable-ipc-flooding-protection \
  --touch-events=enabled \
  --force-device-scale-factor=2.0 \
  --enable-features=OverlayScrollbar \
  --start-fullscreen \
  --window-position=0,0 \
  --window-size=1920,1080 \
  http://localhost:3000 &

CHROMIUM_PID=$!

echo ""
echo "✅ J5 Console Kiosk Started!"
echo "📊 Process IDs:"
echo "  J5 Console API: $J5_PID"
echo "  BtBmsDisplay: $DISPLAY_PID" 
echo "  Chromium: $CHROMIUM_PID"
echo ""
echo "🔄 To stop everything:"
echo "  pkill -f j5_console.py"
echo "  pkill -f 'node.*BtBmsDisplay'"
echo "  pkill -f chromium-browser"
echo ""
echo "🌐 Kiosk running at http://localhost:3000"

# Wait for Chromium to exit
wait $CHROMIUM_PID
