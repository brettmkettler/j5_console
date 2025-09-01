# J5 Console Auto-Start Setup

## 🚀 **Quick Setup (Recommended)**

1. **Copy files to your Raspberry Pi Desktop:**
   ```bash
   # Make sure these files are in ~/Desktop/:
   # - j5_console.py
   # - j5-console.service  
   # - install_service.sh
   # - venv/ (your virtual environment)
   ```

2. **Run the installation script:**
   ```bash
   cd ~/Desktop
   sudo bash install_service.sh
   ```
#
3. **Done!** The J5 console will now start automatically on boot.

---

## 📋 **Manual Setup (Alternative)**

If you prefer to set it up manually:

1. **Set Permissions:**
   ```bash
   sudo raspi-config nonint get_config_var dtparam /boot/firmware/config.txt
   sudo usermod -a -G gpio $USER
   ```

2. **Copy the service file:**
   ```bash
   sudo cp j5-console.service /etc/systemd/system/
   sudo chmod 644 /etc/systemd/system/j5-console.service
   ```

3. **Enable and start the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable j5-console.service
   sudo systemctl start j5-console.service
   ```

---

## 🔧 **Service Management Scripts**

### **Quick Management:**
```bash
# Install auto-start service
sudo bash install_service.sh

# Update service after code changes
sudo bash update_service.sh

# Completely remove service
sudo bash uninstall_service.sh
```

### **Manual Commands:**
```bash
# Check service status
sudo systemctl status j5-console

# Start/stop/restart service
sudo systemctl start j5-console
sudo systemctl stop j5-console
sudo systemctl restart j5-console

# Enable/disable auto-start on boot
sudo systemctl enable j5-console
sudo systemctl disable j5-console

# View logs (live)
sudo journalctl -u j5-console -f

# View all logs
sudo journalctl -u j5-console
```

---

## 🐛 **Troubleshooting**

### **Service won't start:**
1. Check logs: `sudo journalctl -u j5-console`
2. Verify paths in service file
3. Check virtual environment exists: `ls ~/Desktop/venv/bin/python`
4. Test manually: `cd ~/Desktop && source venv/bin/activate && python j5_console.py`

### **GPIO permissions:**
If you get GPIO permission errors:
```bash
sudo usermod -a -G gpio seanfuchs
# Then reboot
```

### **Network not ready:**
If the service starts before network is ready, it will automatically restart after 10 seconds.

---

## 🌐 **Access Your J5 Console**

Once running, access your console at:
- **Swagger UI:** `http://your-pi-ip:5000/docs/`
- **API Base:** `http://your-pi-ip:5000/`

---

## 🔄 **Alternative Methods**

### **Method 2: Crontab (Simple)**
```bash
# Edit crontab
crontab -e

# Add this line:
@reboot cd /home/seanfuchs/Desktop && source venv/bin/activate && python j5_console.py &
```

### **Method 3: rc.local (Legacy)**
```bash
# Edit rc.local
sudo nano /etc/rc.local

# Add before 'exit 0':
su - seanfuchs -c "cd /home/seanfuchs/Desktop && source venv/bin/activate && python j5_console.py &"
```

---

## ✅ **Verification**

After setup, verify it's working:

1. **Reboot your Pi:**
   ```bash
   sudo reboot
   ```

2. **Check if service started:**
   ```bash
   sudo systemctl status j5-console
   ```

3. **Test the API:**
   ```bash
   curl http://localhost:5000/system/status
   ```

4. **Access Swagger UI in browser:**
   `http://your-pi-ip:5000/docs/`
