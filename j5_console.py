from gpiozero import Button, LED, PWMOutputDevice
from gpiozero.pins.lgpio import LGPIOFactory
from flask import Flask, request
from flask_restx import Api, Resource, fields, reqparse
from threading import Thread, Event
import time

# Use lgpio backend for Pi 5 compatibility
pin_factory = LGPIOFactory()
button = Button(26, pull_up=True, pin_factory=pin_factory)  # Input button (red button)
ir_receiver = Button(18, pull_up=True, pin_factory=pin_factory)  # IR receiver input
orange_lamp = LED(5, pin_factory=pin_factory)
red_lamp = LED(6, pin_factory=pin_factory)  # Red lamp
# Servo configuration with proper limits
# Standard servo: 1ms (0°) to 2ms (180°) pulse width at 50Hz
# Duty cycle: 1ms/20ms = 5% (0°), 2ms/20ms = 10% (180°)
# Some servos may need different limits - adjust as needed
left_door = PWMOutputDevice(12, pin_factory=pin_factory, frequency=50)
console_door = PWMOutputDevice(16, pin_factory=pin_factory, frequency=50)
right_door = PWMOutputDevice(19, pin_factory=pin_factory, frequency=50)
startup_led = LED(13, pin_factory=pin_factory)  # Startup indicator
malfunction_led1 = LED(27, pin_factory=pin_factory)  # Malfunction LED set 1
malfunction_led2 = LED(22, pin_factory=pin_factory)  # Malfunction LED set 2
other2 = LED(24, pin_factory=pin_factory)  # GPIO 24 pin 18 white wires

# Servo configuration with individual limits and calibration
# Each servo can have different min/max pulse widths for optimal operation
servo_config = {
    'left_door': {
        'device': left_door,
        'min_pulse': 1.0,    # Minimum pulse width in ms (0°)
        'max_pulse': 2.0,    # Maximum pulse width in ms (180°)
        'min_angle': 0,      # Minimum safe angle
        'max_angle': 180,    # Maximum safe angle
        'center_angle': 90,  # Center/neutral position
        'description': 'Left door servo'
    },
    'console_door': {
        'device': console_door,
        'min_pulse': 1.0,
        'max_pulse': 2.0,
        'min_angle': 0,
        'max_angle': 180,
        'center_angle': 90,
        'description': 'Console door servo'
    },
    'right_door': {
        'device': right_door,
        'min_pulse': 1.0,
        'max_pulse': 2.0,
        'min_angle': 0,
        'max_angle': 180,
        'center_angle': 90,
        'description': 'Right door servo'
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
    'malfunction_led2': malfunction_led2,
    'other2': other2
}

# Global state
current_state = "deactivated"  # Can be: "activated", "deactivated", "malfunction"

# Events to control blinking threads
blink_stop_event = Event()
malfunction_stop_event = Event()

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
            malfunction_led2.on()
            
            # Wait 0.5 seconds (but check for stop event)
            for _ in range(5):  # 5 * 0.1s = 0.5s
                if malfunction_stop_event.is_set():
                    break
                time.sleep(0.1)
            
            # Turn off malfunction LEDs
            malfunction_led1.off()
            malfunction_led2.off()
            
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

# Function to set servo angle (duty cycle: 2.5% for 0 deg, 12.5% for 180 deg)
def set_servo_angle(name, angle):
    """Set servo angle with proper limits and calibration"""
    if name not in servo_config:
        print(f"Error: Unknown servo '{name}'")
        return False
    
    config = servo_config[name]
    
    # Check angle limits
    if not (config['min_angle'] <= angle <= config['max_angle']):
        print(f"Error: Angle {angle}° out of range [{config['min_angle']}°-{config['max_angle']}°] for {name}")
        return False
    
    # Calculate pulse width based on angle
    pulse_range = config['max_pulse'] - config['min_pulse']
    angle_range = config['max_angle'] - config['min_angle']
    pulse_width = config['min_pulse'] + (angle - config['min_angle']) * (pulse_range / angle_range)
    
    # Convert pulse width to duty cycle (pulse_width_ms / 20ms_period * 100)
    duty_cycle = (pulse_width / 20.0) * 100
    
    # Set servo position (gpiozero uses 0.0-1.0 scale)
    config['device'].value = duty_cycle / 100
    
    print(f"⚙️ {config['description']}: {angle}° (pulse: {pulse_width:.2f}ms, duty: {duty_cycle:.1f}%)")
    return True

def get_servo_info(name=None):
    """Get servo configuration information"""
    if name:
        if name in servo_config:
            return servo_config[name]
        return None
    return servo_config

def test_servo_sweep(name, start_angle=None, end_angle=None, step=10, delay=0.5):
    """Test servo by sweeping through angles"""
    if name not in servo_config:
        print(f"Error: Unknown servo '{name}'")
        return False
    
    config = servo_config[name]
    start = start_angle if start_angle is not None else config['min_angle']
    end = end_angle if end_angle is not None else config['max_angle']
    
    print(f"🔄 Testing {config['description']} sweep: {start}° to {end}°")
    
    # Forward sweep
    for angle in range(start, end + 1, step):
        set_servo_angle(name, angle)
        time.sleep(delay)
    
    # Reverse sweep
    for angle in range(end, start - 1, -step):
        set_servo_angle(name, angle)
        time.sleep(delay)
    
    # Return to center
    set_servo_angle(name, config['center_angle'])
    print(f"✅ {config['description']} test complete")
    return True

def calibrate_servo(name, test_angles=[0, 45, 90, 135, 180]):
    """Calibrate servo by testing specific angles"""
    if name not in servo_config:
        print(f"Error: Unknown servo '{name}'")
        return False
    
    config = servo_config[name]
    print(f"🔧 Calibrating {config['description']}...")
    print(f"Current limits: {config['min_angle']}°-{config['max_angle']}°")
    print(f"Pulse range: {config['min_pulse']:.1f}ms-{config['max_pulse']:.1f}ms")
    
    for angle in test_angles:
        if config['min_angle'] <= angle <= config['max_angle']:
            print(f"\nTesting {angle}°...")
            set_servo_angle(name, angle)
            response = input(f"Does {angle}° look correct? (y/n/s to skip): ").lower()
            if response == 'n':
                print("Consider adjusting min_pulse/max_pulse values in servo_config")
            elif response == 's':
                break
        else:
            print(f"Skipping {angle}° (out of range)")
    
    # Return to center
    set_servo_angle(name, config['center_angle'])
    print(f"✅ Calibration complete for {config['description']}")
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
    malfunction_led2.on()
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
        malfunction_led2.off()
        time.sleep(0.5)
        
        # Turn on all startup LEDs
        startup_led.on()
        malfunction_led1.on()
        malfunction_led2.on()
        time.sleep(0.5)
    
    # Step 4: Keep startup LED on for 5 seconds
    print("Step 4: Keeping startup LED on for 5 seconds")
    # Turn off malfunction LEDs, keep only startup LED
    malfunction_led1.off()
    malfunction_led2.off()
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
        malfunction_led2.on()
        time.sleep(0.3)
        
        # Turn off startup and malfunction LEDs
        startup_led.off()
        malfunction_led1.off()
        malfunction_led2.off()
        time.sleep(0.3)
    
    # Step 2: Light both red and orange lamps and both startup and malfunction LEDs on for 5 seconds
    print("Step 2: Lighting all lamps and LEDs for 5 seconds")
    red_lamp.on()
    orange_lamp.on()
    startup_led.on()
    malfunction_led1.on()
    malfunction_led2.on()
    time.sleep(5)
    
    # Step 3: Turn them off in order every 2 seconds: startup LED, malfunction LEDs, red lamp, orange lamp
    print("Step 3: Turning off lights in sequence")
    
    # Turn off startup LED
    startup_led.off()
    time.sleep(2)
    
    # Turn off malfunction LEDs
    malfunction_led1.off()
    malfunction_led2.off()
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
    @ns_digital.param('name', 'Digital output name (orange_lamp, red_lamp, startup_led, malfunction_led1, malfunction_led2, other2)')
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
        parser.add_argument('action', type=str, required=True, choices=['open', 'close', 'angle'], help='Door action')
        parser.add_argument('angle', type=int, help='Servo angle (0-180, required for angle action)')
        args = parser.parse_args()
        
        action = args['action']
        if action == 'open':
            if set_servo_angle(name, 90):
                return {'status': 'success', 'door': name, 'action': 'opened'}
            else:
                api.abort(404, 'Unknown door')
        elif action == 'close':
            if set_servo_angle(name, 0):
                return {'status': 'success', 'door': name, 'action': 'closed'}
            else:
                api.abort(404, 'Unknown door')
        elif action == 'angle':
            angle = args['angle']
            if angle is None or not (0 <= angle <= 180):
                api.abort(400, 'Invalid or missing angle (0-180)')
            if set_servo_angle(name, angle):
                return {'status': 'success', 'door': name, 'angle': angle}
            else:
                api.abort(404, 'Unknown door')

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
    @ns_servo.param('step', 'Step size for sweep test', type=int, default=10)
    @ns_servo.param('delay', 'Delay between steps (seconds)', type=float, default=0.5)
    @ns_servo.marshal_with(servo_test_model)
    def get(self, name):
        '''Test servo movement (sweep, center, min, max positions)'''
        parser = reqparse.RequestParser()
        parser.add_argument('test_type', type=str, default='sweep', choices=['sweep', 'center', 'min', 'max'])
        parser.add_argument('start_angle', type=int)
        parser.add_argument('end_angle', type=int)
        parser.add_argument('step', type=int, default=10)
        parser.add_argument('delay', type=float, default=0.5)
        args = parser.parse_args()
        
        if name not in servo_config:
            api.abort(404, 'Unknown servo')
        
        config = servo_config[name]
        test_type = args['test_type']
        
        if test_type == 'sweep':
            start = args['start_angle'] if args['start_angle'] is not None else config['min_angle']
            end = args['end_angle'] if args['end_angle'] is not None else config['max_angle']
            success = test_servo_sweep(name, start, end, args['step'], args['delay'])
        elif test_type == 'center':
            success = set_servo_angle(name, config['center_angle'])
        elif test_type == 'min':
            success = set_servo_angle(name, config['min_angle'])
        elif test_type == 'max':
            success = set_servo_angle(name, config['max_angle'])
        
        if success:
            return {'status': 'success', 'servo': name, 'test_type': test_type}
        else:
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
        
        for servo_name in servo_config.keys():
            config = servo_config[servo_name]
            
            if test_type == 'sweep':
                success = test_servo_sweep(servo_name, delay=0.2)  # Faster for all servos
            elif test_type == 'center':
                success = set_servo_angle(servo_name, config['center_angle'])
            elif test_type == 'min':
                success = set_servo_angle(servo_name, config['min_angle'])
            elif test_type == 'max':
                success = set_servo_angle(servo_name, config['max_angle'])
            
            results.append(f"{servo_name}: {'success' if success else 'failed'}")
            time.sleep(0.1)  # Small delay between servos
        
        return {'status': 'completed', 'servo': 'all', 'test_type': test_type}

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

# Function to open console door
def open_console_door():
    print("Opening console door via IR receiver...")
    set_servo_angle('console_door', 90)  # Open position
    time.sleep(2)  # Keep open for 2 seconds
    set_servo_angle('console_door', 0)   # Close position

# Button and IR receiver monitoring thread
def input_monitor():
    print("Monitoring button on GPIO 26 and IR receiver on GPIO 18...")
    while True:
        # Check red button for state toggle
        if button.is_pressed:
            if current_state == "deactivated":
                activation_sequence()
                set_state("activated")
            else:
                deactivation_sequence()
            time.sleep(0.5)  # Debounce delay
        
        # Check IR receiver for console door trigger
        if ir_receiver.is_pressed:
            open_console_door()
            time.sleep(0.5)  # Debounce delay for IR receiver
        
        time.sleep(0.1)

if __name__ == '__main__':
    # Start input monitor in a thread
    input_thread = Thread(target=input_monitor)
    input_thread.daemon = True
    input_thread.start()
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)