#!/bin/bash

# Make all service management scripts executable
echo "🔧 Making scripts executable..."

chmod +x install_service.sh
chmod +x uninstall_service.sh  
chmod +x update_service.sh
chmod +x make_scripts_executable.sh

echo "✅ All scripts are now executable!"
echo ""
echo "📋 Available scripts:"
echo "  ./install_service.sh   - Install auto-start service"
echo "  ./update_service.sh    - Restart service after code changes"
echo "  ./uninstall_service.sh - Remove service completely"
echo ""
echo "💡 Remember to run with sudo for system operations!"
