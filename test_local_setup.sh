#!/bin/bash

# Local Testing Setup for BMS Integration
# Sets up development environment on Mac/local machine

echo "🧪 Setting up Local BMS Testing Environment..."
echo ""

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️ This script is designed for macOS. For other systems, install dependencies manually."
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+ first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install requests asyncio

# Make test script executable
chmod +x test_bms_local.py

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+ first."
    echo "   Download from: https://nodejs.org/"
    exit 1
fi

# Check if npm dependencies are installed in BtBmsDisplay
if [ ! -d "BtBmsDisplay/node_modules" ]; then
    echo "📦 Installing BtBmsDisplay dependencies..."
    cd BtBmsDisplay
    npm install
    cd ..
fi

echo ""
echo "✅ Local testing environment setup complete!"
echo ""
echo "🚀 How to test locally:"
echo ""
echo "1. Start BtBmsDisplay (in one terminal):"
echo "   cd BtBmsDisplay"
echo "   npm run dev"
echo ""
echo "2. Start Mock BMS Simulator (in another terminal):"
echo "   source venv/bin/activate"
echo "   python test_bms_local.py"
echo ""
echo "3. Open browser to see live data:"
echo "   http://localhost:3000"
echo ""
echo "📊 The simulator will generate realistic battery data and send it to the web interface!"
echo "🔄 Data updates every 3 seconds with simulated charging/discharging cycles"
echo "⬅️➡️ Left track (batteries 1-4) and Right track (batteries 5-8)"
