#!/bin/bash

# J5 Console Simple Stop Script
# Stops all J5 Console services

echo "🛑 Stopping J5 Console Kiosk..."

# Kill all related processes
pkill -f j5_console.py 2>/dev/null || true
pkill -f "node.*BtBmsDisplay" 2>/dev/null || true
pkill -f chromium-browser 2>/dev/null || true
pkill -f unclutter 2>/dev/null || true

echo "✅ All J5 Console services stopped!"
