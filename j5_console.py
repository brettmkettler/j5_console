from gpiozero import Button, LED, PWMOutputDevice
from gpiozero.pins.lgpio import LGPIOFactory
from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
from threading import Thread, Event
import time
import json
import threading
import sys
import os
import signal
import subprocess
import logging
import requests
from gpiozero.exc import GPIOPinInUse, GPIODeviceClosed

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/j5_console.log')
    ]
)
logger = logging.getLogger('j5_console')

# Function to check if GPIO pins are in use and release them if needed
def check_and_release_gpio_pins(pin_numbers):
    print(f"Checking if GPIO pins {pin_numbers} are in use...")
    
    # Check if there are other j5_console.py processes that might be using GPIO pins
    try:
        # Check for other j5_console.py processes
        ps_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if ps_result.returncode == 0:
            for line in ps_result.stdout.splitlines():
                if 'j5_console.py' in line and str(os.getpid()) not in line:
                    try:
                        pid = int(line.split()[1])
                        print(f"Found other j5_console.py process with PID {pid}, terminating...")
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(2)  # Give it time to terminate and release GPIO pins
                    except (ValueError, ProcessLookupError) as e:
                        print(f"Error terminating process: {e}")
        
        # Optional: Try to check GPIO usage if lsof is available
        try:
            result = subprocess.run(['lsof', '-n', '/dev/gpiochip0'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                print("Found processes using GPIO:")
                print(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # lsof not available or timed out, continue anyway
            pass
            
    except Exception as e:
        print(f"Error checking GPIO usage: {e}")
        # Continue anyway - GPIO initialization will fail if pins are busy

# Use LGPIO pin factory for better performance on Raspberry Pi
pin_factory = LGPIOFactory()

# Initialize GPIO pins - fail fast if devices can't be initialized

# First check and release any conflicting pins
# Added pin 26 for red toggle switch, pin 18 (IR receiver) is enabled
check_and_release_gpio_pins([5, 6, 12, 16, 18, 19, 22, 24, 26, 27])

# Initialize each device individually
# Red toggle switch on GPIO 26 and IR receiver on pin 18 are both enabled
red_toggle_switch = Button(26, pull_up=True, pin_factory=pin_factory)
logger.info(f"Successfully initialized red toggle switch on GPIO 26: {red_toggle_switch}")

ir_receiver = Button(18, pull_up=True, pin_factory=pin_factory)
logger.info(f"Successfully initialized IR receiver on GPIO 18: {ir_receiver}")

# Legacy button variable for compatibility
button = red_toggle_switch

# Initialize LED devices
orange_lamp = LED(5, pin_factory=pin_factory)
logger.info(f"Successfully initialized orange_lamp on GPIO 5: {orange_lamp}")

red_lamp = LED(6, pin_factory=pin_factory)
logger.info(f"Successfully initialized red_lamp on GPIO 6: {red_lamp}")

# Initialize servo devices using Servo class for better Pi 5 compatibility
from gpiozero import Servo

left_door = Servo(12, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000, pin_factory=pin_factory)
left_door.value = 0.0  # Start at center position (90°)
logger.info(f"Successfully initialized left_door servo on GPIO 12: {left_door}")

# Initialize console_door servo device
logger.info("Initializing console_door servo on GPIO pin 16")
console_door = Servo(16, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000, pin_factory=pin_factory)
console_door.value = 0.0  # Start at center position (90°)
logger.info(f"Successfully initialized console_door servo: {console_door}, type: {type(console_door)}")

# Initialize right_door servo device
right_door = Servo(19, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000, pin_factory=pin_factory)
right_door.value = 0.0  # Start at center position (90°)
logger.info(f"Successfully initialized right_door servo on GPIO 19: {right_door}")

# Initialize RC controller inputs for door control
logger.info("Initializing RC relay input on GPIO 14 for console door control")
rc_console_door = Button(14, pull_up=True, pin_factory=pin_factory)
logger.info(f"Successfully initialized RC console door relay on GPIO 14: {rc_console_door}")

logger.info("Initializing RC relay input on GPIO 15 for battery doors control")
rc_battery_doors = Button(15, pull_up=True, pin_factory=pin_factory)
logger.info(f"Successfully initialized RC battery doors relay on GPIO 15: {rc_battery_doors}")

# Startup indicator LEDs (3 LEDs in series) - GPIO 27 Pin 13
startup_led = LED(27, pin_factory=pin_factory)
logger.info(f"Successfully initialized startup_led on GPIO 27: {startup_led}")

# Malfunction indicator LEDs (3 LEDs in series) - GPIO 22 Pin 15  
malfunction_led1 = LED(22, pin_factory=pin_factory)
logger.info(f"Successfully initialized malfunction_led1 on GPIO 22: {malfunction_led1}")

# Remove malfunction_led2 as it's duplicate - only one malfunction LED group in diagram
# malfunction_led2 = LED(22, pin_factory=pin_factory)
# logger.info(f"Successfully initialized malfunction_led2 on GPIO 22: {malfunction_led2}")

# GPIO 24 Pin 18 - Connected to 230 Ohm +3.3v Pin 17 with White Wires
other2 = LED(24, pin_factory=pin_factory)
logger.info(f"Successfully initialized other2 on GPIO 24: {other2}")

logger.info("GPIO initialization complete - all devices initialized successfully")
print("GPIO initialization complete - all devices initialized successfully")

# Servo configuration with proper limits
# Standard servo: 1ms (0°) to 2ms (180°) pulse width at 50Hz
# Duty cycle: 1ms/20ms = 5% (0°), 2ms/20ms = 10% (180°)
# Some servos may need different limits - adjust as needed
# Note: PWM devices are already initialized above, no need to initialize them again
# Note: All LEDs are already initialized above, no need to initialize them again

# Servo configuration with individual limits and calibration
# Each servo can have different min/max pulse widths for optimal operation
# Standard servo: 1ms (0°) to 2ms (180°) pulse width at 50Hz
# Duty cycle: 5% (1ms/20ms) for 0°, 10% (2ms/20ms) for 180°
servo_config = {
    'left_door': {
        'device': left_door,
        'min_pulse': 0.5,    # Minimum pulse width in ms (0°) - adjusted for better response
        'max_pulse': 2.5,    # Maximum pulse width in ms (180°) - adjusted for better response
        'min_angle': 0,      # Minimum safe angle
        'max_angle': 180,    # Maximum safe angle
        'center_angle': 75,  # Center/neutral position
        'description': 'Left door servo',
        'open_angle': 50,    # Angle for open position
        'closed_angle': 140  # Angle for closed position
    },
    'console_door': {
        'device': console_door,
        'min_pulse': 0.5,    # Adjusted for better response
        'max_pulse': 2.5,    # Adjusted for better response
        'min_angle': 0,
        'max_angle': 180,
        'center_angle': 90,
        'description': 'Console door servo',
        'open_angle': 80,    # Angle for open position
        'closed_angle': 135  # Angle for closed position
    },
    'right_door': {
        'device': right_door,
        'min_pulse': 0.5,    # Adjusted for better response
        'max_pulse': 2.5,    # Adjusted for better response
        'min_angle': 0,
        'max_angle': 180,
        'center_angle': 70,
        'description': 'Right door servo',
        'open_angle': 100,   # Angle for open position
        'closed_angle': 30   # Angle for closed position
    }
}

# Dictionary of door PWM devices (for backward compatibility)
door_devices = {name: config['device'] for name, config in servo_config.items()}

# Dictionary of digital output devices
digital_outputs = {
    'orange_lamp': orange_lamp,
    'red_lamp': red_lamp,
    'startup_led': startup_led,
    'malfunction_led1': malfunction_led1,
    'other2': other2
}

# Global state
current_state = "deactivated"  # Can be: "activated", "deactivated", "malfunction"

# Door states
door_states = {
    'console_door': 'closed',  # Can be: "open", "closed"
    'left_door': 'closed',
    'right_door': 'closed'
}

# RC controller PWM decoding state
rc_console_door_pulse = 0
rc_battery_doors_pulse = 0
rc_console_door_last_trigger = 0
rc_battery_doors_last_trigger = 0
rc_trigger_threshold = 1700  # Trigger when pulse > 1700us (stick pushed)
rc_debounce_delay = 1.0  # 1 second between triggers

# Event objects for controlling LED threads
blink_stop_event = Event()
malfunction_stop_event = Event()

# Red toggle switch state
red_toggle_active = False
orange_flash_thread = None
orange_flash_stop_event = Event()

# Red toggle switch debouncing
last_toggle_time = 0
toggle_debounce_delay = 1.0  # 1 second debounce to prevent rapid toggling

# IR receiver debouncing and pattern recognition
last_ir_time = 0
ir_debounce_delay = 0.5  # 500ms between IR signals (allows new button presses)
ir_pulse_times = []  # Store pulse timing for pattern recognition
ir_pattern_timeout = 0.2  # 200ms timeout for pattern completion
ir_pattern_tolerance = 0.05  # 50ms tolerance for pattern matching

# IR learning state
ir_learning_mode = False
ir_learning_timeout = 30.0  # 30 seconds timeout for learning
ir_learning_start_time = 0
learned_ir_signal = None
ir_signal_file = '/tmp/j5_learned_ir_signal.json'

def save_learned_ir_signal(signal_data):
    """Save learned IR signal to persistent storage"""
    try:
        ir_data = {
            'learned_signal': signal_data,
            'learned_pattern': signal_data.get('pattern', []),  # Store timing pattern
            'timestamp': time.time()
        }
        
        with open(ir_signal_file, 'w') as f:
            json.dump(ir_data, f, indent=2)
        
        logger.info(f"IR signal saved to {ir_signal_file}")
        print(f" IR signal saved to {ir_signal_file}")
        print(" IR signal saved and will persist across restarts")
        return True
    except Exception as e:
        logger.error(f"Error saving IR signal: {e}")
        print(f" Error saving IR signal: {e}")
        return False

def load_learned_ir_signal():
    """Load learned IR signal from persistent storage"""
    global learned_ir_signal
    try:
        if os.path.exists(ir_signal_file):
            with open(ir_signal_file, 'r') as f:
                ir_data = json.load(f)
                learned_ir_signal = ir_data
                logger.info(f"IR signal loaded from {ir_signal_file}")
                print(f" Learned IR signal loaded from storage")
                return True
        else:
            logger.info("No learned IR signal file found")
            print(" No learned IR signal found - use learning mode first")
            return False
    except Exception as e:
        logger.error(f"Error loading IR signal: {e}")
        print(f" Error loading IR signal: {e}")
        return False

def patterns_match(pattern1, pattern2, tolerance=0.05):
    """Compare two IR timing patterns with tolerance"""
    if not pattern1 or not pattern2:
        return False
    
    if len(pattern1) != len(pattern2):
        return False
    
    for i in range(len(pattern1)):
        diff = abs(pattern1[i] - pattern2[i])
        if diff > tolerance:
            return False
    
    return True

def process_ir_pattern():
    """Process collected IR pulse timings into a pattern"""
    global ir_pulse_times
    
    if len(ir_pulse_times) < 2:
        return []
    
    # Calculate intervals between pulses
    intervals = []
    for i in range(1, len(ir_pulse_times)):
        interval = ir_pulse_times[i] - ir_pulse_times[i-1]
        intervals.append(interval)
    
    # Clear pulse times for next pattern
    ir_pulse_times = []
    
    return intervals

# Function to blink orange lamp slowly (on 1s, off 1s) - ACTIVATED state
def blink_orange_lamp():
    while not blink_stop_event.is_set():
        orange_lamp.on()
        time.sleep(1)
        if not blink_stop_event.is_set():
            orange_lamp.off()
            time.sleep(1)

# Function for malfunction state - red and orange lamps flash every 0.5s, malfunction LEDs flash every 3s
def malfunction_sequence():
    malfunction_led_timer = 0
    lamp_state = False  # Track current state of lamps
    
    while not malfunction_stop_event.is_set():
        # Flash red and orange lamps every 0.5 seconds
        if lamp_state:
            red_lamp.on()
            orange_lamp.on()
        else:
            red_lamp.off()
            orange_lamp.off()
        
        lamp_state = not lamp_state  # Toggle lamp state
        
        # Flash malfunction LEDs every 3 seconds for 0.5 seconds
        if malfunction_led_timer >= 3.0:
            # Turn on malfunction LEDs for 0.5 seconds
            malfunction_led1.on()
            # malfunction_led2 removed - only one malfunction LED group
            
            # Wait 0.5 seconds (but check for stop event)
            for _ in range(5):  # 5 * 0.1s = 0.5s
                if malfunction_stop_event.is_set():
                    break
                time.sleep(0.1)
            
            # Turn off malfunction LEDs
            malfunction_led1.off()
            # malfunction_led2 removed - only one malfunction LED group
            
            # Reset timer
            malfunction_led_timer = 0
        
        # Wait 0.5 seconds for lamp timing (but check for stop event)
        for _ in range(5):  # 5 * 0.1s = 0.5s
            if malfunction_stop_event.is_set():
                break
            time.sleep(0.1)
        
        # Increment malfunction LED timer
        malfunction_led_timer += 0.5

# Function to set system state
def set_state(new_state):
    global current_state
    
    # Stop all current state activities
    blink_stop_event.set()
    malfunction_stop_event.set()
    time.sleep(0.1)  # Allow threads to stop
    
    # Turn off all lights
    for device in digital_outputs.values():
        device.off()
    
    current_state = new_state
    print(f"Switching to {new_state} state")
    
    if new_state == "activated":
        # Start orange lamp blinking
        blink_stop_event.clear()
        blink_thread = Thread(target=blink_orange_lamp)
        blink_thread.daemon = True
        blink_thread.start()
        
    elif new_state == "malfunction":
        # Start malfunction sequence
        malfunction_stop_event.clear()
        malfunction_thread = Thread(target=malfunction_sequence)
        malfunction_thread.daemon = True
        malfunction_thread.start()
        
    # "deactivated" state - all lights off (already done above)

# Function to toggle between activated and deactivated
def toggle_state():
    if current_state == "deactivated":
        set_state("activated")
    else:
        set_state("deactivated")

# Function to set servo angle with improved calibration
def set_servo_angle(name, angle):
    """
    Set servo to specific angle using gpiozero Servo class
    
    Args:
        name: servo name from servo_config
        angle: target angle in degrees (0-180)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if name not in servo_config:
        logger.error(f"Unknown servo: {name}")
        return False
    
    config = servo_config[name]
    
    # Validate angle range
    if not config['min_angle'] <= angle <= config['max_angle']:
        logger.error(f"Angle {angle}° out of range for {name} (min: {config['min_angle']}°, max: {config['max_angle']}°)")
        return False
    
    logger.debug(f"set_servo_angle called for {name} with angle {angle}°")
    logger.debug(f"Servo config for {name}: {config}")
    
    try:
        # Convert angle to servo value (-1 to 1 range for gpiozero Servo)
        # 0° = -1, 90° = 0, 180° = 1
        servo_value = (angle - 90) / 90.0
        
        logger.info(f"Setting {config['description']} to {angle}° (servo value: {servo_value:.3f})")
        
        # Set the servo position
        config['device'].value = servo_value
        
        print(f" {config['description']}: {angle}° (servo value: {servo_value:.3f})")
        
        # Wait for servo to reach position
        time.sleep(1.5)
        
        # Temporarily disabled PWM disable to test servo movement
        # config['device'].value = None  # For Servo class, None stops the servo
        # logger.debug(f"Servo {name} PWM disabled to prevent jittering")
        # print(f" {config['description']} PWM disabled to prevent jittering")
        
        logger.debug(f"Servo {name} position set successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting {name} servo position: {e}", exc_info=True)
        print(f"Error setting servo position: {e}")
        return False

def get_servo_info(name=None):
    """Get servo configuration information"""
    if name:
        if name in servo_config:
            return servo_config[name]
        return None
    return servo_config

def test_servo_sweep(name, start_angle=None, end_angle=None, step=5, delay=0.5):
    """Test servo by sweeping through angles"""
    logger.info(f"Starting servo sweep test for {name}")
    
    if name not in servo_config:
        logger.error(f"Error: Unknown servo '{name}'")
        print(f"Error: Unknown servo '{name}'")
        return False
    
    config = servo_config[name]
    start = start_angle if start_angle is not None else config['min_angle']
    end = end_angle if end_angle is not None else config['max_angle']
    
    logger.info(f"Servo sweep parameters - name: {name}, start: {start}°, end: {end}°, step: {step}, delay: {delay}s")
    print(f" Testing {config['description']} sweep: {start}° to {end}°")
    
    # Forward sweep
    logger.debug(f"Starting forward sweep for {name} from {start}° to {end}°")
    for angle in range(start, end + 1, step):
        logger.debug(f"Forward sweep: setting {name} to {angle}°")
        set_servo_angle(name, angle)
        time.sleep(delay)
    
    # Reverse sweep
    logger.debug(f"Starting reverse sweep for {name} from {end}° to {start}°")
    for angle in range(end, start - 1, -step):
        logger.debug(f"Reverse sweep: setting {name} to {angle}°")
        set_servo_angle(name, angle)
        time.sleep(delay)
    
    # Return to center
    logger.debug(f"Returning {name} to center position ({config['center_angle']}°)")
    set_servo_angle(name, config['center_angle'])
    
    logger.info(f"Servo sweep test for {name} completed successfully")
    print(f" {config['description']} test complete")
    return True

def calibrate_servo(name, test_angles=[0, 45, 90, 135, 180]):
    """Calibrate servo by testing specific angles"""
    logger.info(f"Starting servo calibration for {name} with test angles: {test_angles}")
    
    if name not in servo_config:
        logger.error(f"Error: Unknown servo '{name}'")
        print(f"Error: Unknown servo '{name}'")
        return False
    
    config = servo_config[name]
    logger.info(f"Calibrating {name} with current config: {config}")
    print(f" Calibrating {config['description']}...")
    print(f"Current limits: {config['min_angle']}°-{config['max_angle']}°")
    print(f"Pulse range: {config['min_pulse']:.1f}ms-{config['max_pulse']:.1f}ms")
    
    for angle in test_angles:
        if config['min_angle'] <= angle <= config['max_angle']:
            logger.debug(f"Testing {name} at {angle}°")
            print(f"\nTesting {angle}°...")
            set_servo_angle(name, angle)
            response = input(f"Does {angle}° look correct? (y/n/s to skip): ").lower()
            logger.debug(f"User response for {name} at {angle}°: {response}")
            
            if response == 'n':
                logger.warning(f"User indicated incorrect position for {name} at {angle}°")
                print("Consider adjusting min_pulse/max_pulse values in servo_config")
            elif response == 's':
                break
        else:
            print(f"Skipping {angle}° (out of range)")
    
    # Return to center
    set_servo_angle(name, config['center_angle'])
    print(f" Calibration complete for {config['description']}")
    return True

# Function to set digital output
def set_digital_output(name, state):
    if name not in digital_outputs:
        return False
    digital_outputs[name].value = 1 if state else 0
    return True

# Activation sequence with light effects
def activation_sequence():
    print("Starting activation sequence...")
    
    # Stop any current state activities temporarily
    blink_stop_event.set()
    malfunction_stop_event.set()
    time.sleep(0.1)
    
    # Turn off all lights first
    for device in digital_outputs.values():
        device.off()
    
    # Step 1: Light up the Startup LEDs and keep them on
    print("Step 1: Lighting up startup LEDs")
    startup_led.on()
    malfunction_led1.on()
    # malfunction_led2 removed - only one malfunction LED group in diagram
    time.sleep(1)  # Keep them on for a moment
    
    # Step 2: Blink the red and orange lamps back and forth
    print("Step 2: Blinking red and orange lamps back and forth")
    for _ in range(6):  # 6 cycles = 12 blinks total
        red_lamp.on()
        orange_lamp.off()
        time.sleep(0.5)
        red_lamp.off()
        orange_lamp.on()
        time.sleep(0.5)
    
    # Turn off both lamps after the sequence
    red_lamp.off()
    orange_lamp.off()
    
    # Step 3: Blink the Startup LEDs off and on 3 times
    print("Step 3: Blinking startup LEDs 3 times")
    for _ in range(3):
        # Turn off all startup LEDs
        startup_led.off()
        malfunction_led1.off()
        # malfunction_led2 removed - only one malfunction LED group in diagram
        
        # Wait 0.5 seconds (but check for stop event)
        time.sleep(0.5)
        
        # Turn on all startup LEDs
        startup_led.on()
        malfunction_led1.on()
        # malfunction_led2 removed - only one malfunction LED group in diagram
        
        # Wait 0.5 seconds (but check for stop event)
        time.sleep(0.5)
    
    # Step 4: Keep startup LED on for 5 seconds
    print("Step 4: Keeping startup LED on for 5 seconds")
    # Turn off malfunction LEDs, keep only startup LED
    malfunction_led1.off()
    # malfunction_led2 removed - only one malfunction LED group in diagram
    startup_led.on()
    time.sleep(5)
    
    # Turn off startup LED before transitioning to activated state
    startup_led.off()
    
    print("Activation sequence complete - transitioning to activated state")

# Deactivation sequence with malfunction effects
def deactivation_sequence():
    print("Starting deactivation sequence...")
    
    # Stop current state activities
    blink_stop_event.set()
    malfunction_stop_event.set()
    time.sleep(0.1)
    
    # Turn off all lights first
    for device in digital_outputs.values():
        device.off()
    
    # Step 1: Flash startup LEDs and malfunction LEDs for 4 seconds
    print("Step 1: Flashing startup and malfunction LEDs for 4 seconds")
    start_time = time.time()
    while time.time() - start_time < 4.0:
        # Turn on startup and malfunction LEDs
        startup_led.on()
        malfunction_led1.on()
        # malfunction_led2 removed - only one malfunction LED group in diagram
        time.sleep(0.3)
        
        # Turn off startup and malfunction LEDs
        startup_led.off()
        malfunction_led1.off()
        # malfunction_led2 removed - only one malfunction LED group in diagram
        time.sleep(0.3)
    
    # Step 2: Light both red and orange lamps and both startup and malfunction LEDs on for 5 seconds
    print("Step 2: Lighting all lamps and LEDs for 5 seconds")
    red_lamp.on()
    orange_lamp.on()
    startup_led.on()
    malfunction_led1.on()
    # malfunction_led2 removed - only one malfunction LED group in diagram
    time.sleep(5)
    
    # Step 3: Turn them off in order every 2 seconds: startup LED, malfunction LEDs, red lamp, orange lamp
    print("Step 3: Turning off lights in sequence")
    
    # Turn off startup LED
    startup_led.off()
    time.sleep(2)
    
    # Turn off malfunction LEDs
    malfunction_led1.off()
    # malfunction_led2 removed - only one malfunction LED group in diagram
    time.sleep(2)
    
    # Turn off red lamp
    red_lamp.off()
    time.sleep(2)
    
    # Turn off orange lamp
    orange_lamp.off()
    time.sleep(1)  # Brief pause before final flash
    
    # Step 4: Quickly flash all lights off and on 2 times then all off
    print("Step 4: Final flash sequence")
    for _ in range(2):
        # Turn on all lights
        for device in digital_outputs.values():
            device.on()
        time.sleep(0.2)
        
        # Turn off all lights
        for device in digital_outputs.values():
            device.off()
        time.sleep(0.2)
    
    # Final shutdown to deactivated state
    set_state("deactivated")
    print("Deactivation sequence complete.")

# Flask app with Swagger documentation
app = Flask(__name__)
api = Api(app, 
    version='1.0', 
    title='J5 Console API',
    description='Complete API control for the J5 Console system with three states: activated, deactivated, and malfunction. Control doors, LEDs, and system states.',
    doc='/docs/'  # Swagger UI will be available at /docs/
)

# API namespaces
ns_state = api.namespace('state', description='System state operations')
ns_door = api.namespace('door', description='Door control operations')
ns_digital = api.namespace('digital', description='LED and digital output control')
ns_servo = api.namespace('servo', description='Direct servo control')
ns_system = api.namespace('system', description='System information and sequences')
ns_ir = api.namespace('ir', description='IR control operations')

# API models for documentation
state_model = api.model('StateResponse', {
    'status': fields.String(description='Operation status'),
    'current_state': fields.String(description='Current system state')
})

door_model = api.model('DoorResponse', {
    'status': fields.String(description='Operation status'),
    'door': fields.String(description='Door name'),
    'action': fields.String(description='Action performed'),
    'angle': fields.Integer(description='Servo angle (if applicable)')
})

digital_model = api.model('DigitalResponse', {
    'status': fields.String(description='Operation status'),
    'digital': fields.String(description='Digital output name'),
    'state': fields.String(description='Output state (on/off)')
})

servo_model = api.model('ServoResponse', {
    'status': fields.String(description='Operation status'),
    'servo': fields.String(description='Servo name'),
    'angle': fields.Integer(description='Servo angle')
})

status_model = api.model('StatusResponse', {
    'current_state': fields.String(description='Current system state'),
    'available_doors': fields.List(fields.String, description='Available door names'),
    'available_digital_outputs': fields.List(fields.String, description='Available digital output names'),
    'available_states': fields.List(fields.String, description='Available system states')
})

sequence_model = api.model('SequenceResponse', {
    'status': fields.String(description='Operation status'),
    'current_state': fields.String(description='Current system state after sequence')
})

ir_learn_model = api.model('IRLearnResponse', {
    'status': fields.String(description='IR learning status'),
    'message': fields.String(description='IR learning status message'),
    'timeout': fields.Integer(description='IR learning timeout in seconds'),
    'learning': fields.Boolean(description='Whether IR learning is active')
})

@ns_servo.route('/<string:name>')
class ServoControl(Resource):
    @ns_servo.doc('control_servo')
    @ns_servo.param('name', 'Servo name (left_door, console_door, right_door)')
    @ns_servo.param('angle', 'Servo angle (0-180 degrees)', type=int, required=True)
    @ns_servo.marshal_with(servo_model)
    def get(self, name):
        '''Control servo position by angle'''
        parser = reqparse.RequestParser()
        parser.add_argument('angle', type=int, required=True, help='Servo angle (0-180)')
        args = parser.parse_args()
        
        angle = args['angle']
        if not (0 <= angle <= 180):
            api.abort(400, 'Invalid angle (0-180)')
        if set_servo_angle(name, angle):
            return {'status': 'success', 'servo': name, 'angle': angle}
        else:
            api.abort(404, 'Unknown servo')

@ns_digital.route('/<string:name>')
class DigitalControl(Resource):
    @ns_digital.doc('control_digital')
    @ns_digital.param('name', 'Digital output name (orange_lamp, red_lamp, startup_led, malfunction_led1, other2)')
    @ns_digital.param('state', 'Output state (on or off)', required=True)
    @ns_digital.marshal_with(digital_model)
    def get(self, name):
        '''Control digital output (LED) state'''
        parser = reqparse.RequestParser()
        parser.add_argument('state', type=str, required=True, choices=['on', 'off'], help='Output state (on/off)')
        args = parser.parse_args()
        
        state_str = args['state']
        state = state_str == 'on'
        if set_digital_output(name, state):
            return {'status': 'success', 'digital': name, 'state': state_str}
        else:
            api.abort(404, 'Unknown digital output')

@ns_door.route('/<string:name>')
class DoorControl(Resource):
    @ns_door.doc('control_door')
    @ns_door.param('name', 'Door name (left_door, console_door, right_door)')
    @ns_door.param('action', 'Door action (open, close, or angle)', required=True)
    @ns_door.param('angle', 'Servo angle (0-180 degrees, required when action=angle)', type=int)
    @ns_door.marshal_with(door_model)
    def get(self, name):
        '''Control door position (open, close, or custom angle)'''
        parser = reqparse.RequestParser()
        parser.add_argument('action', type=str, required=True, choices=['open', 'close', 'toggle', 'angle'], help='Door action')
        parser.add_argument('angle', type=int, help='Servo angle (0-180, required for angle action)')
        args = parser.parse_args()
        
        action = args['action']
        logger.info(f"Door API called: door={name}, action={action}, args={args}")
        print(f"\n Door API: {name} - Action: {action}")
        if action == 'open':
            if name == 'console_door':
                logger.debug(f"Processing 'open' action for console_door")
                try:
                    result = open_console_door()
                    logger.debug(f"open_console_door() returned: {result}")
                    if result:
                        logger.info(f"Successfully opened console door, state: {door_states[name]}")
                        return {'status': 'success', 'door': name, 'action': 'opened', 'state': door_states[name]}
                    else:
                        logger.error("Failed to open console door - function returned False")
                        api.abort(500, 'Failed to open console door')
                except Exception as e:
                    logger.error(f"Exception in open_console_door: {e}", exc_info=True)
                    api.abort(500, f'Error opening console door: {str(e)}')
            elif name in door_states:
                open_angle = servo_config[name]['open_angle']
                print(f" Opening {name} door to {open_angle}°")
                if set_servo_angle(name, open_angle):
                    door_states[name] = 'open'
                    print(f" {name} door opened successfully - State: {door_states[name]}")
                    return {'status': 'success', 'door': name, 'action': 'opened', 'state': door_states[name]}
                else:
                    print(f" Failed to open {name} door")
                    api.abort(500, 'Failed to open door')
            else:
                api.abort(404, 'Unknown door')
        elif action == 'close':
            if name == 'console_door':
                logger.debug(f"Processing 'close' action for console_door")
                try:
                    result = close_console_door()
                    logger.debug(f"close_console_door() returned: {result}")
                    if result:
                        logger.info(f"Successfully closed console door, state: {door_states[name]}")
                        return {'status': 'success', 'door': name, 'action': 'closed', 'state': door_states[name]}
                    else:
                        logger.error("Failed to close console door - function returned False")
                        api.abort(500, 'Failed to close console door')
                except Exception as e:
                    logger.error(f"Exception in close_console_door: {e}", exc_info=True)
                    api.abort(500, f'Error closing console door: {str(e)}')
            elif name in door_states:
                closed_angle = servo_config[name]['closed_angle']
                print(f" Closing {name} door to {closed_angle}°")
                if set_servo_angle(name, closed_angle):
                    door_states[name] = 'closed'
                    print(f" {name} door closed successfully - State: {door_states[name]}")
                    return {'status': 'success', 'door': name, 'action': 'closed', 'state': door_states[name]}
                else:
                    print(f" Failed to close {name} door")
                    api.abort(500, 'Failed to close door')
            else:
                api.abort(404, 'Unknown door')
        elif action == 'toggle':
            if name == 'console_door':
                logger.debug(f"Processing 'toggle' action for console_door")
                try:
                    result = toggle_console_door()
                    logger.debug(f"toggle_console_door() returned: {result}")
                    logger.info(f"Toggled console door, current state: {door_states[name]}")
                    return {'status': 'success', 'door': name, 'action': 'toggled', 'state': door_states[name]}
                except Exception as e:
                    logger.error(f"Exception in toggle_console_door: {e}", exc_info=True)
                    api.abort(500, f'Error toggling console door: {str(e)}')
            elif name in door_states:
                print(f" Toggling {name} door - Current state: {door_states[name]}")
                if door_states[name] == 'closed':
                    open_angle = servo_config[name]['open_angle']
                    print(f"Door is closed, opening to {open_angle}°...")
                    if set_servo_angle(name, open_angle):
                        door_states[name] = 'open'
                        print(f" {name} door toggled to open - State: {door_states[name]}")
                        return {'status': 'success', 'door': name, 'action': 'toggled to open', 'state': door_states[name]}
                else:
                    closed_angle = servo_config[name]['closed_angle']
                    print(f"Door is open, closing to {closed_angle}°...")
                    if set_servo_angle(name, closed_angle):
                        door_states[name] = 'closed'
                        print(f" {name} door toggled to closed - State: {door_states[name]}")
                        return {'status': 'success', 'door': name, 'action': 'toggled to closed', 'state': door_states[name]}
            else:
                api.abort(404, 'Unknown door')
        elif action == 'angle':
            angle = args['angle']
            if angle is None or not (0 <= angle <= 180):
                print(f" Invalid or missing angle: {angle}")
                api.abort(400, 'Invalid or missing angle (0-180)')
            print(f" Setting {name} door to custom angle: {angle}°")
            if set_servo_angle(name, angle):
                print(f" {name} door set to {angle}° successfully")
                return {'status': 'success', 'door': name, 'angle': angle, 'state': door_states[name]}
            else:
                print(f" Failed to set {name} door to angle {angle}°")
                api.abort(404, 'Unknown door')

@ns_ir.route('/learn')
class IRLearn(Resource):
    @ns_ir.doc('learn_ir_signal')
    @ns_ir.marshal_with(ir_learn_model)
    def post(self):
        '''Start IR signal learning mode'''
        global ir_learning_mode, ir_learning_start_time
        
        if ir_learning_mode:
            return {
                'status': 'already_learning',
                'message': 'IR learning mode is already active',
                'timeout': int(ir_learning_timeout - (time.time() - ir_learning_start_time)),
                'learning': True
            }
        
        # Start learning mode
        ir_learning_mode = True
        ir_learning_start_time = time.time()
        
        logger.info("IR learning mode activated")
        print(" IR learning mode activated - waiting for signal...")
        
        return {
            'status': 'learning_started',
            'message': 'IR learning mode activated. Send an IR signal within 30 seconds.',
            'timeout': int(ir_learning_timeout),
            'learning': True
        }
    
    @ns_ir.doc('get_ir_learning_status')
    @ns_ir.marshal_with(ir_learn_model)
    def get(self):
        '''Get current IR learning status'''
        global ir_learning_mode, ir_learning_start_time
        
        if ir_learning_mode:
            remaining_time = max(0, int(ir_learning_timeout - (time.time() - ir_learning_start_time)))
            if remaining_time <= 0:
                # Learning has timed out
                ir_learning_mode = False
                return {
                    'status': 'timeout',
                    'message': 'IR learning mode timed out',
                    'timeout': 0,
                    'learning': False
                }
            return {
                'status': 'learning_active',
                'message': f'IR learning mode active. {remaining_time} seconds remaining.',
                'timeout': remaining_time,
                'learning': True
            }
        else:
            return {
                'status': 'not_learning',
                'message': 'IR learning mode is not active',
                'timeout': 0,
                'learning': False
            }

# Servo testing and calibration models
servo_info_model = api.model('ServoInfo', {
    'name': fields.String(description='Servo name'),
    'description': fields.String(description='Servo description'),
    'min_angle': fields.Integer(description='Minimum angle'),
    'max_angle': fields.Integer(description='Maximum angle'),
    'center_angle': fields.Integer(description='Center angle'),
    'min_pulse': fields.Float(description='Minimum pulse width (ms)'),
    'max_pulse': fields.Float(description='Maximum pulse width (ms)')
})

servo_test_model = api.model('ServoTestResponse', {
    'status': fields.String(description='Test status'),
    'servo': fields.String(description='Servo name'),
    'test_type': fields.String(description='Type of test performed')
})

@ns_servo.route('/<string:name>/info')
class ServoInfo(Resource):
    @ns_servo.doc('get_servo_info')
    @ns_servo.param('name', 'Servo name (left_door, console_door, right_door)')
    @ns_servo.marshal_with(servo_info_model)
    def get(self, name):
        '''Get servo configuration and limits'''
        info = get_servo_info(name)
        if info:
            return {
                'name': name,
                'description': info['description'],
                'min_angle': info['min_angle'],
                'max_angle': info['max_angle'],
                'center_angle': info['center_angle'],
                'min_pulse': info['min_pulse'],
                'max_pulse': info['max_pulse']
            }
        else:
            api.abort(404, 'Unknown servo')

@ns_servo.route('/<string:name>/test')
class ServoTest(Resource):
    @ns_servo.doc('test_servo')
    @ns_servo.param('name', 'Servo name (left_door, console_door, right_door)')
    @ns_servo.param('test_type', 'Test type (sweep, center, min, max)', default='sweep')
    @ns_servo.param('start_angle', 'Start angle for sweep test', type=int)
    @ns_servo.param('end_angle', 'End angle for sweep test', type=int)
    @ns_servo.param('step', 'Step size for sweep test', type=int, default=5)
    @ns_servo.param('delay', 'Delay between steps (seconds)', type=float, default=0.5)
    @ns_servo.marshal_with(servo_test_model)
    def get(self, name):
        '''Test servo movement (sweep, center, min, max positions)'''
        parser = reqparse.RequestParser()
        parser.add_argument('test_type', type=str, default='sweep', choices=['sweep', 'center', 'min', 'max'])
        parser.add_argument('start_angle', type=int)
        parser.add_argument('end_angle', type=int)
        parser.add_argument('step', type=int, default=5)
        parser.add_argument('delay', type=float, default=0.5)
        args = parser.parse_args()
        
        if name not in servo_config:
            api.abort(404, 'Unknown servo')
        
        config = servo_config[name]
        test_type = args['test_type']
        
        success = False  # Initialize success variable
        
        print(f"\n Testing servo: {name} - Test type: {test_type}")
        
        if test_type == 'sweep':
            start = args['start_angle'] if args['start_angle'] is not None else config['min_angle']
            end = args['end_angle'] if args['end_angle'] is not None else config['max_angle']
            print(f" Sweep parameters: start={start}°, end={end}°, step={args['step']}, delay={args['delay']}s")
            success = test_servo_sweep(name, start, end, args['step'], args['delay'])
        elif test_type == 'center':
            print(f" Setting {name} to center position: {config['center_angle']}°")
            success = set_servo_angle(name, config['center_angle'])
        elif test_type == 'min':
            print(f" Setting {name} to minimum position: {config['min_angle']}°")
            success = set_servo_angle(name, config['min_angle'])
        elif test_type == 'max':
            print(f" Setting {name} to maximum position: {config['max_angle']}°")
            success = set_servo_angle(name, config['max_angle'])
        
        if success:
            print(f" Test completed successfully for {name}\n")
            return {'status': 'success', 'servo': name, 'test_type': test_type}
        else:
            print(f" Test failed for {name}\n")
            api.abort(400, 'Test failed')

@ns_servo.route('/test-all')
class ServoTestAll(Resource):
    @ns_servo.doc('test_all_servos')
    @ns_servo.param('test_type', 'Test type (sweep, center, min, max)', default='center')
    @ns_servo.marshal_with(servo_test_model)
    def get(self):
        '''Test all servos simultaneously'''
        parser = reqparse.RequestParser()
        parser.add_argument('test_type', type=str, default='center', choices=['sweep', 'center', 'min', 'max'])
        args = parser.parse_args()
        
        test_type = args['test_type']
        results = []
        
        print(f"\n Testing ALL servos - Test type: {test_type}")
        
        for servo_name in servo_config.keys():
            config = servo_config[servo_name]
            
            print(f"\n Testing {servo_name} ({config['description']})...")
            
            if test_type == 'sweep':
                print(f" Quick sweep from {config['min_angle']}° to {config['max_angle']}°")
                success = test_servo_sweep(servo_name, delay=0.2)  # Faster for all servos
            elif test_type == 'center':
                print(f" Setting to center position: {config['center_angle']}°")
                success = set_servo_angle(servo_name, config['center_angle'])
            elif test_type == 'min':
                print(f" Setting to minimum position: {config['min_angle']}°")
                success = set_servo_angle(servo_name, config['min_angle'])
            elif test_type == 'max':
                print(f" Setting to maximum position: {config['max_angle']}°")
                success = set_servo_angle(servo_name, config['max_angle'])
            
            results.append(f"{servo_name}: {'success' if success else 'failed'}")
            time.sleep(0.1)  # Small delay between servos
        
        print(f"\n All servo tests completed - Results: {', '.join(results)}\n")
        return {'status': 'completed', 'servo': 'all', 'test_type': test_type, 'results': results}

@ns_system.route('/status')
class SystemStatus(Resource):
    @ns_system.doc('get_status')
    @ns_system.marshal_with(status_model)
    def get(self):
        '''Get current system status and available components'''
        return {
            'current_state': current_state,
            'available_doors': list(door_devices.keys()),
            'available_digital_outputs': list(digital_outputs.keys()),
            'available_states': ['activated', 'deactivated', 'malfunction']
        }

@ns_state.route('/')
class StateControl(Resource):
    @ns_state.doc('control_state')
    @ns_state.param('mode', 'System state (activated, deactivated, malfunction)', required=True)
    @ns_state.marshal_with(state_model)
    def get(self):
        '''Control system state (activated, deactivated, malfunction)'''
        parser = reqparse.RequestParser()
        parser.add_argument('mode', type=str, required=True, choices=['activated', 'deactivated', 'malfunction'], help='System state')
        args = parser.parse_args()
        
        mode = args['mode']
        if mode == current_state:
            return {'status': f'Already in {mode} state', 'current_state': current_state}
        
        if mode == "activated":
            activation_sequence()
            set_state("activated")
        elif mode == "deactivated":
            deactivation_sequence()
        else:  # malfunction
            set_state("malfunction")
        
        return {'status': f'State changed to {mode}', 'current_state': current_state}

@ns_system.route('/sequence')
class ActivationSequence(Resource):
    @ns_system.doc('run_sequence')
    @ns_system.marshal_with(sequence_model)
    def get(self):
        '''Run activation sequence with light effects'''
        activation_sequence()
        return {'status': 'sequence completed', 'current_state': current_state}

# Battery door control endpoints
@ns_door.route('/battery')
class BatteryDoorControl(Resource):
    @ns_door.doc('control_battery_doors')
    @ns_door.param('action', 'Battery door action (open, close, toggle)', required=True)
    @ns_door.marshal_with(door_model)
    def get(self):
        '''Control both battery doors simultaneously (left and right)'''
        parser = reqparse.RequestParser()
        parser.add_argument('action', type=str, required=True, choices=['open', 'close', 'toggle'], help='Battery door action')
        args = parser.parse_args()
        
        action = args['action']
        logger.info(f"Battery door API called: action={action}")
        print(f"\n Battery Door API - Action: {action}")
        
        if action == 'open':
            result = open_battery_doors()
            if result:
                return {
                    'status': 'success', 
                    'door': 'battery_doors', 
                    'action': 'opened', 
                    'state': f"left: {door_states['left_door']}, right: {door_states['right_door']}"
                }
            else:
                api.abort(500, 'Failed to open battery doors')
        elif action == 'close':
            result = close_battery_doors()
            if result:
                return {
                    'status': 'success', 
                    'door': 'battery_doors', 
                    'action': 'closed', 
                    'state': f"left: {door_states['left_door']}, right: {door_states['right_door']}"
                }
            else:
                api.abort(500, 'Failed to close battery doors')
        elif action == 'toggle':
            result = toggle_battery_doors()
            return {
                'status': 'success', 
                'door': 'battery_doors', 
                'action': 'toggled', 
                'state': f"left: {door_states['left_door']}, right: {door_states['right_door']}"
            }

# Red toggle switch functions
def red_toggle_sequence():
    """Execute the red toggle switch sequence"""
    global red_toggle_active, orange_flash_thread, orange_flash_stop_event
    
    logger.info("Red toggle switch activated - starting sequence with screen ON")
    print("\n RED TOGGLE SWITCH ACTIVATED!")
    print(" Turning screen ON...")
    
    # Call screen ON API first
    try:
        response = requests.post('http://localhost:3000/api/screen/on', timeout=5)
        if response.status_code == 200:
            logger.info("Screen turned ON successfully")
            print(" Screen turned ON")
        else:
            logger.warning(f"Screen ON API returned status {response.status_code}")
            print(f" Screen ON API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call screen ON API: {e}")
        print(f" Failed to turn screen ON: {e}")
    
    print(" Activating all lamps and LEDs for 10 seconds...")
    
    red_toggle_active = True
    
    # Turn on all red and orange lamps and startup/malfunction LEDs
    try:
        red_lamp.on()
        orange_lamp.on()
        startup_led.on()
        malfunction_led1.on()
        logger.info("All lamps and LEDs activated")
        print(" All lamps and LEDs ON")
        
        # Keep them on for 10 seconds
        logger.info("Waiting 10 seconds...")
        print(" Waiting 10 seconds...")
        time.sleep(10)
        
        # Turn off all except orange lamp
        red_lamp.off()
        startup_led.off()
        malfunction_led1.off()
        orange_lamp.off()  # Turn off before starting flash
        
        logger.info("10-second sequence complete - starting orange lamp flash")
        print(" 10-second sequence complete")
        print(" Starting orange lamp flash (1 second on/off cycle)")
        
        # Start orange lamp flashing thread
        start_orange_flash()
        
    except Exception as e:
        logger.error(f"Error in red toggle sequence: {e}")
        print(f" Error in red toggle sequence: {e}")
        red_toggle_active = False

def start_orange_flash():
    """Start the orange lamp flashing in a separate thread"""
    global orange_flash_thread, orange_flash_stop_event
    
    # Stop any existing flash thread
    stop_orange_flash()
    
    # Reset the stop event
    orange_flash_stop_event.clear()
    
    # Start new flash thread
    orange_flash_thread = Thread(target=orange_flash_worker, daemon=True)
    orange_flash_thread.start()
    logger.info("Orange flash thread started")

def orange_flash_worker():
    """Worker function for orange lamp flashing"""
    logger.info("Orange lamp flashing started - 1 second on/off cycle")
    
    try:
        while not orange_flash_stop_event.is_set():
            # Turn on for 1 second
            orange_lamp.on()
            if orange_flash_stop_event.wait(1.0):  # Wait 1 second or until stop event
                break
            
            # Turn off for 1 second
            orange_lamp.off()
            if orange_flash_stop_event.wait(1.0):  # Wait 1 second or until stop event
                break
                
    except Exception as e:
        logger.error(f"Error in orange flash worker: {e}")
    finally:
        orange_lamp.off()  # Ensure lamp is off when thread stops
        logger.info("Orange lamp flashing stopped")

def stop_orange_flash():
    """Stop the orange lamp flashing"""
    global orange_flash_thread, orange_flash_stop_event
    
    if orange_flash_thread and orange_flash_thread.is_alive():
        logger.info("Stopping orange lamp flash")
        orange_flash_stop_event.set()
        orange_flash_thread.join(timeout=2.0)
        orange_flash_thread = None
        orange_lamp.off()
        print(" Orange lamp flashing stopped")

def red_toggle_off():
    """Handle red toggle switch being turned off"""
    global red_toggle_active
    
    logger.info("Red toggle switch deactivated - starting shutdown sequence")
    print("\n RED TOGGLE SWITCH DEACTIVATED")
    print(" Starting shutdown sequence...")
    
    red_toggle_active = False
    
    # Stop orange flashing
    stop_orange_flash()
    
    # Turn off all lamps and LEDs immediately
    try:
        red_lamp.off()
        orange_lamp.off()
        startup_led.off()
        malfunction_led1.off()
        logger.info("All lamps and LEDs turned off")
        print(" All lamps and LEDs OFF")
        
        # Wait 3 seconds before closing console door
        logger.info("Waiting 3 seconds before closing console door...")
        print(" Waiting 3 seconds before closing console door...")
        time.sleep(3)
        
        # Close the console door
        logger.info("Closing console door")
        print(" Closing console door...")
        result = close_console_door()
        
        if result:
            logger.info("Console door closed successfully via toggle switch")
            print(" Console door closed successfully")
        else:
            logger.error("Failed to close console door via toggle switch")
            print(" Failed to close console door")
            
        logger.info("Red toggle switch shutdown sequence complete")
        print(" Shutdown sequence complete")
        
    except Exception as e:
        logger.error(f"Error in red toggle shutdown sequence: {e}")
        print(f" Error in shutdown sequence: {e}")

# IR door operation function
def ir_door_operation():
    """Execute door operation in separate thread"""
    global door_states
    try:
        current_state = door_states['console_door']
        if current_state == 'closed':
            logger.info("IR triggered - opening console door")
            print(" IR triggered - opening console door")
            open_console_door()
        elif current_state == 'open':
            logger.info("IR triggered - closing console door")
            print(" IR triggered - closing console door")
            close_console_door()
        else:
            logger.info(f"IR triggered - current state: {current_state}")
            print(f" IR triggered - current state: {current_state}")
    except Exception as e:
        logger.error(f"Error in IR door operation: {e}")
        print(f" Error in IR door operation: {e}")

# Functions to control console door
def open_console_door():
    global door_states
    logger.info("Opening console door")
    print("\n Opening console door...")
    
    # Use the configured open angle from servo_config
    open_angle = servo_config['console_door']['open_angle']
    logger.debug(f"Console door open angle from config: {open_angle}°")
    print(f" Setting console_door to open position: {open_angle}°")
    
    success = set_servo_angle('console_door', open_angle)
    
    if success:
        door_states['console_door'] = 'open'
        logger.info(f"Console door opened successfully. State set to: {door_states['console_door']}")
        print(f" Door opened successfully - Current state: {door_states['console_door']}\n")
    else:
        logger.error("Failed to open console door")
        print(f" Failed to open door\n")
    
    return success

def close_console_door():
    global door_states
    logger.info("Closing console door")
    print("\n Closing console door...")
    
    # Use the configured closed angle from servo_config
    closed_angle = servo_config['console_door']['closed_angle']
    logger.debug(f"Console door closed angle from config: {closed_angle}°")
    print(f" Setting console_door to closed position: {closed_angle}°")
    
    success = set_servo_angle('console_door', closed_angle)
    
    if success:
        door_states['console_door'] = 'closed'
        logger.info(f"Console door closed successfully. State set to: {door_states['console_door']}")
        print(f" Door closed successfully - Current state: {door_states['console_door']}\n")
    else:
        logger.error("Failed to close console door")
        print(f" Failed to close door\n")
    
    return success

def toggle_console_door():
    global door_states
    logger.info(f"Toggling console door. Current state: {door_states['console_door']}")
    print(f"\n Toggling console door - Current state: {door_states['console_door']}")
    
    if door_states['console_door'] == 'closed':
        logger.debug("Door is closed, opening it")
        print("Door is closed, opening it...")
        return open_console_door()
    else:
        logger.debug("Door is open, closing it")
        print("Door is open, closing it...")
        return close_console_door()

# Functions to control battery doors (left and right simultaneously)
def open_battery_doors():
    global door_states
    logger.info("Opening battery doors simultaneously (right door finishes 0.1s after left)")
    print("\n Opening battery doors simultaneously...")
    
    # Get configured open angles for both doors
    left_open_angle = servo_config['left_door']['open_angle']
    right_open_angle = servo_config['right_door']['open_angle']
    
    logger.debug(f"Left door open angle: {left_open_angle}°, Right door open angle: {right_open_angle}°")
    print(f" Opening both doors simultaneously - left to {left_open_angle}°, right to {right_open_angle}° (right finishes 0.1s later)")
    
    # Start both doors simultaneously using threads
    import threading
    
    left_success = [False]  # Use list to allow modification in thread
    right_success = [False]
    
    def open_left():
        print(" Opening left door...")
        left_success[0] = set_servo_angle('left_door', left_open_angle)
    
    def open_right():
        # Small delay so right door finishes 0.1s after left
        time.sleep(0.1)
        print(" Opening right door (0.1s later)...")
        right_success[0] = set_servo_angle('right_door', right_open_angle)
    
    # Start both threads simultaneously
    left_thread = threading.Thread(target=open_left)
    right_thread = threading.Thread(target=open_right)
    
    left_thread.start()
    right_thread.start()
    
    # Wait for both to complete
    left_thread.join()
    right_thread.join()
    
    # Update door states
    if left_success[0]:
        door_states['left_door'] = 'open'
        logger.info("Left battery door opened successfully")
        print(" Left battery door opened successfully")
    else:
        logger.error("Failed to open left battery door")
        print(" Failed to open left battery door")
    
    if right_success[0]:
        door_states['right_door'] = 'open'
        logger.info("Right battery door opened successfully")
        print(" Right battery door opened successfully")
    else:
        logger.error("Failed to open right battery door")
        print(" Failed to open right battery door")
    
    overall_success = left_success[0] and right_success[0]
    if overall_success:
        logger.info("Both battery doors opened successfully with simultaneous timing")
        print(" Both battery doors opened successfully with simultaneous timing\n")
    else:
        logger.warning("One or both battery doors failed to open")
        print(" One or both battery doors failed to open\n")
    
    return overall_success

def close_battery_doors():
    global door_states
    logger.info("Closing battery doors simultaneously (right door finishes 0.1s after left)")
    print("\n Closing battery doors simultaneously...")
    
    # Get configured closed angles for both doors
    left_closed_angle = servo_config['left_door']['closed_angle']
    right_closed_angle = servo_config['right_door']['closed_angle']
    
    logger.debug(f"Left door closed angle: {left_closed_angle}°, Right door closed angle: {right_closed_angle}°")
    print(f" Closing both doors simultaneously - left to {left_closed_angle}°, right to {right_closed_angle}° (right finishes 0.1s later)")
    
    # Start both doors simultaneously using threads
    import threading
    
    left_success = [False]  # Use list to allow modification in thread
    right_success = [False]
    
    def close_left():
        print(" Closing left door...")
        left_success[0] = set_servo_angle('left_door', left_closed_angle)
    
    def close_right():
        # Small delay so right door finishes 0.1s after left
        time.sleep(0.1)
        print(" Closing right door (0.1s later)...")
        right_success[0] = set_servo_angle('right_door', right_closed_angle)
    
    # Start both threads simultaneously
    left_thread = threading.Thread(target=close_left)
    right_thread = threading.Thread(target=close_right)
    
    left_thread.start()
    right_thread.start()
    
    # Wait for both to complete
    left_thread.join()
    right_thread.join()
    
    # Update door states
    if left_success[0]:
        door_states['left_door'] = 'closed'
        logger.info("Left battery door closed successfully")
        print(" Left battery door closed successfully")
    else:
        logger.error("Failed to close left battery door")
        print(" Failed to close left battery door")
    
    if right_success[0]:
        door_states['right_door'] = 'closed'
        logger.info("Right battery door closed successfully")
        print(" Right battery door closed successfully")
    else:
        logger.error("Failed to close right battery door")
        print(" Failed to close right battery door")
    
    overall_success = left_success[0] and right_success[0]
    if overall_success:
        logger.info("Both battery doors closed successfully with simultaneous timing")
        print(" Both battery doors closed successfully with simultaneous timing\n")
    else:
        logger.warning("One or both battery doors failed to close")
        print(" One or both battery doors failed to close\n")
    
    return overall_success

def toggle_battery_doors():
    global door_states
    logger.info(f"Toggling battery doors. Left: {door_states['left_door']}, Right: {door_states['right_door']}")
    print(f"\n Toggling battery doors - Left: {door_states['left_door']}, Right: {door_states['right_door']}")
    
    # If either door is closed, open both. If both are open, close both.
    if door_states['left_door'] == 'closed' or door_states['right_door'] == 'closed':
        logger.debug("One or both doors are closed, opening both")
        print("One or both doors are closed, opening both...")
        return open_battery_doors()
    else:
        logger.debug("Both doors are open, closing both")
        print("Both doors are open, closing both...")
        return close_battery_doors()

# Button and IR receiver monitoring thread
def input_monitor():
    logger.info("Input monitoring started (GPIO 26 red toggle switch, GPIO 18 IR receiver enabled)")
    print("Input monitoring started (GPIO 26 red toggle switch, GPIO 18 IR receiver enabled)")
    
    # Set up IR receiver callback
    if ir_receiver is not None:
        def ir_signal_received():
            global door_states, last_ir_time, ir_learning_mode, ir_learning_start_time, learned_ir_signal, ir_pulse_times
            current_time = time.time()
            
            print(f" IR signal received at {current_time}")
            logger.info(f"IR signal received at {current_time}")
            
            # Add pulse time for pattern recognition
            ir_pulse_times.append(current_time)
            
            # Check if we're in learning mode
            if ir_learning_mode:
                # Check if learning has timed out
                if current_time - ir_learning_start_time > ir_learning_timeout:
                    ir_learning_mode = False
                    logger.info("IR learning mode timed out")
                    print(" IR learning mode timed out")
                    ir_pulse_times = []  # Clear pattern data
                    return
                
                # Check if pattern is complete (no new pulses for pattern_timeout)
                if len(ir_pulse_times) > 1:
                    time_since_last = current_time - ir_pulse_times[-2]
                    if time_since_last > ir_pattern_timeout:
                        # Pattern complete, learn it
                        pattern = process_ir_pattern()
                        learned_ir_signal = {
                            'timestamp': current_time,
                            'pattern': pattern
                        }
                        ir_learning_mode = False
                        
                        logger.info(f"IR signal learned successfully with pattern: {pattern}")
                        print(" IR signal learned successfully! Signal will now control console door.")
                        
                        # Save to persistent storage
                        save_learned_ir_signal(learned_ir_signal)
                        return
                
                # Still collecting pattern, return early
                return
            
            # Not in learning mode - check if we have a learned signal
            if not learned_ir_signal:
                logger.debug("No learned IR signal - ignoring")
                print(" IR learning mode not active - ignoring")
                ir_pulse_times = []  # Clear pattern data
                return
            
            # Debouncing check
            if current_time - last_ir_time < ir_debounce_delay:
                logger.debug(f"IR signal ignored - debounce active")
                print(f" IR signal ignored - debounce active")
                return
            
            # Check if pattern is complete (no new pulses for pattern_timeout)
            if len(ir_pulse_times) > 1:
                time_since_last = current_time - ir_pulse_times[-2]
                if time_since_last > ir_pattern_timeout:
                    # Pattern complete, check if it matches learned pattern
                    current_pattern = process_ir_pattern()
                    learned_pattern = learned_ir_signal.get('pattern', [])
                    
                    if patterns_match(current_pattern, learned_pattern, ir_pattern_tolerance):
                        logger.info("IR pattern matches learned signal - executing door operation")
                        print(" IR pattern matches - executing door operation")
                        
                        # Execute door operation
                        last_ir_time = current_time
                        ir_thread = Thread(target=ir_door_operation, daemon=True)
                        ir_thread.start()
                    else:
                        logger.debug(f"IR pattern mismatch - Current: {current_pattern}, Learned: {learned_pattern}")
                        print(" IR pattern doesn't match learned signal - ignoring")
                
                return
            
            # Still collecting pattern for comparison
            return
        # Attach the callback to the IR receiver
        ir_receiver.when_pressed = ir_signal_received
        logger.info("IR receiver callback attached")
        print(" IR receiver callback attached - ready to receive signals")
    
    # Set up RC controller input callbacks
    if rc_console_door is not None and rc_battery_doors is not None:
        def rc_console_door_pressed():
            global door_states
            logger.info("RC console door triggered - toggling console door")
            print(" RC CONSOLE DOOR TRIGGERED - toggling console door")
            toggle_console_door()
        
        def rc_battery_doors_pressed():
            global door_states
            logger.info("RC battery doors triggered - toggling battery doors")
            print(" RC BATTERY DOORS TRIGGERED - toggling battery doors")
            toggle_battery_doors()
        
        # Attach the callbacks to the RC controller inputs
        rc_console_door.when_pressed = rc_console_door_pressed
        rc_battery_doors.when_pressed = rc_battery_doors_pressed
        logger.info("RC controller input callbacks attached")
        print(" RC controller ready - relay inputs active")
    
    # Set up red toggle switch callbacks
    if red_toggle_switch is not None:
        def red_toggle_pressed():
            global last_toggle_time
            current_time = time.time()
            
            # Debouncing: ignore rapid toggle events
            if current_time - last_toggle_time < toggle_debounce_delay:
                logger.debug(f"Red toggle PRESSED ignored - debounce active ({current_time - last_toggle_time:.2f}s since last)")
                print(f" Red toggle PRESSED ignored - debounce active ({current_time - last_toggle_time:.2f}s since last)")
                return
            
            last_toggle_time = current_time
            logger.info("Red toggle switch pressed (activated)")
            print(" Red toggle switch PRESSED - starting sequence")
            try:
                # Run the sequence in a separate thread to avoid blocking
                toggle_thread = Thread(target=red_toggle_sequence, daemon=True)
                toggle_thread.start()
            except Exception as e:
                logger.error(f"Error starting red toggle sequence: {e}")
                print(f" Error starting red toggle sequence: {e}")
        
        def red_toggle_released():
            global last_toggle_time
            current_time = time.time()
            
            # Debouncing: ignore rapid toggle events
            if current_time - last_toggle_time < toggle_debounce_delay:
                logger.debug(f"Red toggle RELEASED ignored - debounce active ({current_time - last_toggle_time:.2f}s since last)")
                print(f" Red toggle RELEASED ignored - debounce active ({current_time - last_toggle_time:.2f}s since last)")
                return
            
            last_toggle_time = current_time
            logger.info("Red toggle switch released (deactivated)")
            print(" Red toggle switch RELEASED - starting shutdown sequence")
            try:
                # Run the shutdown sequence in a separate thread to avoid blocking
                shutdown_thread = Thread(target=red_toggle_off, daemon=True)
                shutdown_thread.start()
            except Exception as e:
                logger.error(f"Error starting red toggle shutdown sequence: {e}")
                print(f" Error starting red toggle shutdown sequence: {e}")
        
        # Attach the callbacks to the red toggle switch
        red_toggle_switch.when_pressed = red_toggle_pressed
        red_toggle_switch.when_released = red_toggle_released
        logger.info("Red toggle switch callbacks attached")
        print(" Red toggle switch callbacks attached - ready for activation")
    
    try:
        while True:
            try:
                # GPIO 26 (button) is disabled, GPIO 18 (IR receiver) is active
                # IR receiver uses callback, so we just need to keep the thread alive
                pass
            except Exception as e:
                logger.error(f"Error in input monitoring: {e}")
                print(f"Error in input monitoring: {e}")
            
            time.sleep(0.1)  # Check every 100ms
    except KeyboardInterrupt:
        logger.info("Input monitoring stopped")
        print("Input monitoring stopped")
    except Exception as e:
        logger.error(f"Input monitor thread error: {e}")
        print(f"Input monitor thread error: {e}")

# GPIO cleanup function
def cleanup_gpio():
    """Clean up GPIO resources"""
    logger.info("Starting GPIO cleanup...")
    print("Starting GPIO cleanup...")
    
    try:
        # Stop all threads
        blink_stop_event.set()
        malfunction_stop_event.set()
        stop_orange_flash()  # Stop orange lamp flashing
        
        # Close all GPIO devices
        devices_to_close = [
            orange_lamp, red_lamp, left_door, console_door, right_door, 
            startup_led, malfunction_led1, other2, ir_receiver, red_toggle_switch,
            rc_console_door, rc_battery_doors
        ]
        
        for device in devices_to_close:
            if device and hasattr(device, 'close'):
                try:
                    device.close()
                    logger.debug(f"Closed device: {device}")
                except Exception as e:
                    logger.warning(f"Error closing device {device}: {e}")
        
        logger.info("GPIO cleanup completed")
        print("GPIO cleanup completed")
    except Exception as e:
        logger.error(f"Error during GPIO cleanup: {e}")
        print(f"Error during GPIO cleanup: {e}")

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    print(f"\nReceived signal {signum}, shutting down gracefully...")
    cleanup_gpio()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # systemctl stop

if __name__ == '__main__':
    try:
        # Start input monitor in a thread
        input_thread = Thread(target=input_monitor)
        input_thread.daemon = True
        input_thread.start()
        
        # Start Flask app
        print("Starting J5 Console API on port 5000...")
        # Disable debug mode to prevent Flask restarts that cause GPIO conflicts
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        print(f"Error starting application: {e}")
        cleanup_gpio()
        sys.exit(1)
    finally:
        # Ensure cleanup happens even on normal exit
        cleanup_gpio()
