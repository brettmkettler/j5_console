#!/usr/bin/env python3
"""
Servo Test Script for Raspberry Pi 5
This script tests servo movement with different approaches to identify the issue
"""

import time
import logging
from gpiozero import Servo, PWMOutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_servo_methods():
    """Test different servo control methods"""
    
    print("🔧 Testing Servo Control Methods on Raspberry Pi 5")
    print("=" * 50)
    
    # Test 1: Standard gpiozero Servo class
    print("\n1️⃣ Testing gpiozero Servo class (GPIO 16)")
    try:
        servo = Servo(16)
        print("✅ Servo initialized successfully")
        
        # Test movement
        angles = [0, 90, 180, 90]  # Test sequence
        for i, angle in enumerate(angles):
            servo_value = (angle - 90) / 90.0
            print(f"   Moving to {angle}° (value: {servo_value:.2f})")
            servo.value = servo_value
            time.sleep(2)
            
        servo.close()
        print("✅ Test 1 completed")
        
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
    
    # Test 2: Servo with custom pulse widths
    print("\n2️⃣ Testing Servo with custom pulse widths")
    try:
        servo = Servo(16, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
        print("✅ Custom servo initialized")
        
        # Test movement
        for angle in [0, 45, 90, 135, 180]:
            servo_value = (angle - 90) / 90.0
            print(f"   Moving to {angle}° (value: {servo_value:.2f})")
            servo.value = servo_value
            time.sleep(1.5)
            
        servo.close()
        print("✅ Test 2 completed")
        
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
    
    # Test 3: PWMOutputDevice approach
    print("\n3️⃣ Testing PWMOutputDevice approach")
    try:
        pwm = PWMOutputDevice(16, frequency=50)
        print("✅ PWM device initialized")
        
        # Test different duty cycles
        duty_cycles = [0.025, 0.075, 0.125]  # 1ms, 1.5ms, 2.5ms pulse widths
        angles = [0, 90, 180]
        
        for duty, angle in zip(duty_cycles, angles):
            print(f"   Setting {angle}° (duty cycle: {duty:.3f})")
            pwm.value = duty
            time.sleep(2)
            
        pwm.close()
        print("✅ Test 3 completed")
        
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
    
    # Test 4: PiGPIO factory (if available)
    print("\n4️⃣ Testing with PiGPIO factory")
    try:
        pin_factory = PiGPIOFactory()
        servo = Servo(16, pin_factory=pin_factory)
        print("✅ PiGPIO servo initialized")
        
        # Quick test
        servo.min()
        time.sleep(1)
        servo.mid()
        time.sleep(1)
        servo.max()
        time.sleep(1)
        servo.mid()
        
        servo.close()
        print("✅ Test 4 completed")
        
    except Exception as e:
        print(f"❌ Test 4 failed: {e}")

def check_system_info():
    """Check system configuration"""
    print("\n🔍 System Information")
    print("=" * 30)
    
    try:
        # Check if running as root/sudo
        import os
        print(f"User ID: {os.getuid()}")
        print(f"Effective User ID: {os.geteuid()}")
        
        # Check GPIO permissions
        import stat
        try:
            gpio_stat = os.stat('/dev/gpiomem')
            print(f"GPIO permissions: {stat.filemode(gpio_stat.st_mode)}")
        except:
            print("❌ Cannot access /dev/gpiomem")
            
        # Check if pigpio daemon is running
        import subprocess
        try:
            result = subprocess.run(['pgrep', 'pigpiod'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ pigpiod daemon is running")
            else:
                print("⚠️  pigpiod daemon not running")
        except:
            print("❓ Cannot check pigpiod status")
            
    except Exception as e:
        print(f"❌ System check failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Servo Diagnostics")
    
    check_system_info()
    test_servo_methods()
    
    print("\n" + "=" * 50)
    print("🏁 Diagnostics Complete")
    print("\nIf no servos moved, check:")
    print("1. Servo power supply (5V, sufficient current)")
    print("2. Servo signal wire connected to GPIO 16")
    print("3. Common ground between Pi and servo")
    print("4. Run with sudo if permission issues")
    print("5. Enable hardware PWM in raspi-config")
