import RPi.GPIO as GPIO
import time
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from threading import Thread

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)

# Define pins
button_pin = 26  # Input button (big red activation/deactivation button)
orange_lamp_pin = 5
transistor_pin = 6  # NPN transistor control
left_door_pin = 12
console_door_pin = 16
right_door_pin = 19
startup_led_pin = 13  # Startup indicator (3 LEDs)
malfunction_led_pin1 = 27  # One set for malfunction
malfunction_led_pin2 = 22  # Another set for malfunction
ir_receiver_pin = 18  # GPIO 18 IR Receiver
other_pin2 = 24  # GPIO 24 pin 18 white wires

# List of door pins for servos
door_pins = {
    'left_door': left_door_pin,
    'console_door': console_door_pin,
    'right_door': right_door_pin
}

# List of digital output pins
digital_outputs = {
    'orange_lamp': orange_lamp_pin,
    'transistor': transistor_pin,
    'startup_led': startup_led_pin,
    'malfunction_led1': malfunction_led_pin1,
    'malfunction_led2': malfunction_led_pin2,
    'other2': other_pin2
}

# Set up button as input with pull-up
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set up IR receiver as input with pull-up
GPIO.setup(ir_receiver_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set up digital outputs
for pin in digital_outputs.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# System state
activated = False
malfunction = False
activation_thread = None
malfunction_thread = None

# Set up PWM for doors (assuming servos at 50Hz)
servos = {}
for name, pin in door_pins.items():
    GPIO.setup(pin, GPIO.OUT)
    servos[name] = GPIO.PWM(pin, 50)
    servos[name].start(0)  # Start PWM at 0 duty cycle

# Function to set servo angle (duty cycle approximation: 2.5% for 0 deg, 12.5% for 180 deg, adjust as needed)
def set_servo_angle(name, angle):
    if name not in servos:
        return False
    duty = 2.5 + (angle / 18.0)  # Map 0-180 to 2.5-12.5
    servos[name].ChangeDutyCycle(duty)
    return True

# Function to set digital output
def set_digital_output(name, state):
    if name not in digital_outputs:
        return False
    GPIO.output(digital_outputs[name], GPIO.HIGH if state else GPIO.LOW)
    return True

# Activation sequence with blinking lights and orange lamp flashing
def activation_sequence():
    global activated
    print("Starting activation sequence...")
    
    # Startup light blinking
    for _ in range(5):
        set_digital_output('startup_led', True)
        time.sleep(0.2)
        set_digital_output('startup_led', False)
        time.sleep(0.2)
    
    # Turn on transistor and other outputs
    set_digital_output('transistor', True)
    set_digital_output('other2', True)
    
    activated = True
    print("System ACTIVATED - Orange lamp will flash every second")

# Deactivation sequence with malfunction blinking and shutdown
def deactivation_sequence():
    global activated
    print("Starting deactivation sequence...")
    
    activated = False
    
    # Malfunction blinking sequence
    for _ in range(8):
        # Flash malfunction LEDs and orange lamp
        set_digital_output('malfunction_led1', True)
        set_digital_output('malfunction_led2', True)
        set_digital_output('orange_lamp', True)
        time.sleep(0.3)
        set_digital_output('malfunction_led1', False)
        set_digital_output('malfunction_led2', False)
        set_digital_output('orange_lamp', False)
        time.sleep(0.3)
    
    # Shutdown sequence - turn off all outputs
    for name in digital_outputs.keys():
        set_digital_output(name, False)
    
    print("System DEACTIVATED - All systems shutdown")

# Continuous orange lamp flashing when activated
def orange_lamp_flasher():
    global activated
    while True:
        if activated and not malfunction:
            set_digital_output('orange_lamp', True)
            time.sleep(1)
            set_digital_output('orange_lamp', False)
            time.sleep(1)
        else:
            time.sleep(0.5)  # Check activation state more frequently when deactivated

# Malfunction state handler
def malfunction_handler():
    global malfunction
    while True:
        if malfunction:
            # Red lamp (other2) flashes every 0.5 seconds
            set_digital_output('other2', True)
            time.sleep(0.5)
            set_digital_output('other2', False)
            time.sleep(0.5)
        else:
            time.sleep(0.5)

# Malfunction LED handler (separate timing)
def malfunction_led_handler():
    global malfunction
    while True:
        if malfunction:
            # Malfunction LEDs on for 2 seconds
            set_digital_output('malfunction_led1', True)
            set_digital_output('malfunction_led2', True)
            time.sleep(2)
            # Malfunction LEDs off for 0.5 seconds
            set_digital_output('malfunction_led1', False)
            set_digital_output('malfunction_led2', False)
            time.sleep(0.5)
        else:
            time.sleep(0.5)

# Set system state
def set_system_state(state):
    global activated, malfunction, activation_thread, malfunction_thread
    
    if state == 'activated':
        malfunction = False
        if not activated:
            activation_sequence()
            # Start orange lamp flasher thread if not already running
            if activation_thread is None or not activation_thread.is_alive():
                activation_thread = Thread(target=orange_lamp_flasher)
                activation_thread.daemon = True
                activation_thread.start()
    elif state == 'deactivated':
        malfunction = False
        if activated:
            deactivation_sequence()
    elif state == 'malfunction':
        activated = False
        malfunction = True
        print("System entering MALFUNCTION state")
        
        # Start malfunction threads if not already running
        if malfunction_thread is None or not malfunction_thread.is_alive():
            malfunction_thread = Thread(target=malfunction_handler)
            malfunction_thread.daemon = True
            malfunction_thread.start()
            
            # Start malfunction LED thread
            malfunction_led_thread = Thread(target=malfunction_led_handler)
            malfunction_led_thread.daemon = True
            malfunction_led_thread.start()

# Toggle activation state (for button compatibility)
def toggle_activation():
    global activated
    if not activated:
        set_system_state('activated')
    else:
        set_system_state('deactivated')

# Flask app for API with Swagger documentation
app = Flask(__name__)
api = Api(app, 
    version='1.0', 
    title='J5 Console Control API',
    description='Raspberry Pi-based control system for doors, lights, and indicators',
    doc='/docs/'  # Swagger UI will be available at /docs/
)

# API namespaces
ns_system = api.namespace('system', description='System state operations')
ns_doors = api.namespace('doors', description='Door control operations')
ns_leds = api.namespace('leds', description='LED control operations')
ns_legacy = api.namespace('legacy', description='Legacy servo and digital control')

# API models for documentation
state_model = api.model('StateResponse', {
    'status': fields.String(description='Operation status'),
    'previous_state': fields.String(description='Previous system state'),
    'current_state': fields.String(description='Current system state')
})

status_model = api.model('StatusResponse', {
    'activated': fields.Boolean(description='System activation status'),
    'malfunction': fields.Boolean(description='System malfunction status'),
    'state': fields.String(description='Current system state')
})

door_model = api.model('DoorResponse', {
    'status': fields.String(description='Operation status'),
    'door': fields.String(description='Door name'),
    'action': fields.String(description='Action performed')
})

led_model = api.model('LEDResponse', {
    'status': fields.String(description='Operation status'),
    'led': fields.String(description='LED name'),
    'state': fields.String(description='LED state')
})

servo_model = api.model('ServoResponse', {
    'status': fields.String(description='Operation status'),
    'servo': fields.String(description='Servo name'),
    'angle': fields.Integer(description='Servo angle')
})

@ns_legacy.route('/servo/<string:name>')
@ns_legacy.param('name', 'Servo name (console_door, left_door, right_door)')
@ns_legacy.param('angle', 'Servo angle (0-180 degrees)', type='integer')
class ServoControl(Resource):
    @ns_legacy.marshal_with(servo_model)
    @ns_legacy.doc('control_servo')
    def get(self, name):
        '''Control servo position'''
        angle = request.args.get('angle', type=int)
        if angle is None or not (0 <= angle <= 180):
            api.abort(400, 'Invalid or missing angle (0-180)')
        if set_servo_angle(name, angle):
            return {'status': 'success', 'servo': name, 'angle': angle}
        else:
            api.abort(404, 'Unknown servo')

@ns_legacy.route('/digital/<string:name>')
@ns_legacy.param('name', 'Digital output name')
@ns_legacy.param('state', 'Output state (on/off)')
class DigitalControl(Resource):
    @ns_legacy.doc('control_digital')
    def get(self, name):
        '''Control digital output'''
        state_str = request.args.get('state')
        if state_str not in ['on', 'off']:
            api.abort(400, 'Invalid or missing state (on/off)')
        state = state_str == 'on'
        if set_digital_output(name, state):
            return {'status': 'success', 'digital': name, 'state': state_str}
        else:
            api.abort(404, 'Unknown digital output')

@ns_system.route('/toggle')
class ToggleActivation(Resource):
    @ns_system.marshal_with(state_model)
    @ns_system.doc('toggle_activation')
    def get(self):
        '''Toggle system between activated and deactivated states'''
        global activated
        old_state = 'activated' if activated else 'deactivated'
        toggle_activation()
        new_state = 'activated' if activated else 'deactivated'
        return {
            'status': 'success',
            'previous_state': old_state,
            'current_state': new_state
        }

@ns_system.route('/state')
@ns_system.param('mode', 'System mode (activated, deactivated, malfunction)')
class SetSystemState(Resource):
    @ns_system.marshal_with(state_model)
    @ns_system.doc('set_system_state')
    def get(self):
        '''Set system state to activated, deactivated, or malfunction'''
        global activated, malfunction
        mode = request.args.get('mode')
        if mode not in ['activated', 'deactivated', 'malfunction']:
            api.abort(400, 'Invalid mode. Use: activated, deactivated, or malfunction')
        
        old_state = 'malfunction' if malfunction else ('activated' if activated else 'deactivated')
        set_system_state(mode)
        new_state = 'malfunction' if malfunction else ('activated' if activated else 'deactivated')
        
        return {
            'status': 'success',
            'previous_state': old_state,
            'current_state': new_state
        }

@ns_system.route('/status')
class GetSystemStatus(Resource):
    @ns_system.marshal_with(status_model)
    @ns_system.doc('get_system_status')
    def get(self):
        '''Get current system status and state'''
        current_state = 'malfunction' if malfunction else ('activated' if activated else 'deactivated')
        return {
            'activated': activated,
            'malfunction': malfunction,
            'state': current_state
        }

@ns_doors.route('/<string:name>')
@ns_doors.param('name', 'Door name (console_door, left_door, right_door)')
@ns_doors.param('action', 'Door action (open, close)')
class DoorControl(Resource):
    @ns_doors.marshal_with(door_model)
    @ns_doors.doc('control_door')
    def get(self, name):
        '''Control door position (open/close)'''
        if name not in door_pins:
            api.abort(404, f'Unknown door. Available: {", ".join(door_pins.keys())}')
        
        action = request.args.get('action')
        if action == 'open':
            set_servo_angle(name, 90)
            return {'status': 'success', 'door': name, 'action': 'opened'}
        elif action == 'close':
            set_servo_angle(name, 0)
            return {'status': 'success', 'door': name, 'action': 'closed'}
        else:
            api.abort(400, 'Invalid action. Use: open or close')

@ns_leds.route('/<string:name>')
@ns_leds.param('name', 'LED name (startup, malfunction1, malfunction2, orange, transistor, red)')
@ns_leds.param('state', 'LED state (on, off)')
class LEDControl(Resource):
    @ns_leds.marshal_with(led_model)
    @ns_leds.doc('control_led')
    def get(self, name):
        '''Control individual LED state'''
        led_mapping = {
            'startup': 'startup_led',
            'malfunction1': 'malfunction_led1', 
            'malfunction2': 'malfunction_led2',
            'orange': 'orange_lamp',
            'transistor': 'transistor',
            'red': 'other2'
        }
        
        if name not in led_mapping:
            api.abort(404, f'Unknown LED. Available: {", ".join(led_mapping.keys())}')
        
        state_str = request.args.get('state')
        if state_str not in ['on', 'off']:
            api.abort(400, 'Invalid state. Use: on or off')
        
        state = state_str == 'on'
        set_digital_output(led_mapping[name], state)
        return {'status': 'success', 'led': name, 'state': state_str}

# Function to open console door
def open_console_door():
    print("Opening console door via IR signal...")
    # Open console door to 90 degrees
    set_servo_angle('console_door', 90)
    # Brief LED indication
    set_digital_output('startup_led', True)
    time.sleep(0.5)
    set_digital_output('startup_led', False)
    # Keep door open for 5 seconds, then close
    time.sleep(5)
    set_servo_angle('console_door', 0)
    print("Console door closed.")

# IR receiver monitoring thread
def ir_monitor():
    print("Monitoring IR receiver on GPIO 18...")
    last_state = GPIO.input(ir_receiver_pin)
    while True:
        current_state = GPIO.input(ir_receiver_pin)
        # Detect falling edge (IR signal received)
        if last_state == GPIO.HIGH and current_state == GPIO.LOW:
            print("IR signal detected!")
            open_console_door()
            time.sleep(0.5)  # Debounce delay
        last_state = current_state
        time.sleep(0.05)  # Check every 50ms

# Big red button monitoring thread
def button_monitor():
    print("Monitoring big red activation/deactivation button on GPIO 26...")
    while True:
        if GPIO.input(button_pin) == GPIO.LOW:
            print("Big red button pressed!")
            toggle_activation()
            time.sleep(1)  # Longer debounce delay for toggle button
        time.sleep(0.1)

if __name__ == '__main__':
    # Start button monitor in a thread
    button_thread = Thread(target=button_monitor)
    button_thread.daemon = True
    button_thread.start()
    
    # Start IR receiver monitor in a thread
    ir_thread = Thread(target=ir_monitor)
    ir_thread.daemon = True
    ir_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)

# Cleanup on exit (though Flask runs forever, can be caught with try-except if needed)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    for pwm in servos.values():
        pwm.stop()
    GPIO.cleanup()