#!/usr/bin/env python3
"""
Overkill Solar BMS Bluetooth Integration Service
Connects to two BMS units (left/right tracks) and sends data to BtBmsDisplay
"""

import asyncio
import json
import logging
import time
import struct
from typing import Dict, List, Optional, Tuple
import requests
import signal
import sys

try:
    from bleak import BleakClient, BleakScanner
    BLUETOOTH_AVAILABLE = True
except ImportError:
    print("Warning: bleak not installed. Install with: pip install bleak")
    BLUETOOTH_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('overkill_bms')

class OverkillBMS:
    """Overkill Solar BMS Bluetooth interface"""
    
    # Overkill BMS Bluetooth characteristics
    SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
    CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
    
    # BMS command bytes
    CMD_BASIC_INFO = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
    CMD_CELL_VOLTAGES = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])
    
    def __init__(self, mac_address: str, track: str, battery_offset: int = 0):
        self.mac_address = mac_address
        self.track = track  # 'left' or 'right'
        self.battery_offset = battery_offset  # 0 for left (batteries 1-4), 4 for right (batteries 5-8)
        self.client: Optional[BleakClient] = None
        self.is_connected = False
        
    async def connect(self) -> bool:
        """Connect to BMS via Bluetooth"""
        try:
            logger.info(f"Connecting to {self.track} track BMS: {self.mac_address}")
            self.client = BleakClient(self.mac_address)
            await self.client.connect()
            self.is_connected = True
            logger.info(f"Connected to {self.track} track BMS successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.track} track BMS: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from BMS"""
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.is_connected = False
            logger.info(f"Disconnected from {self.track} track BMS")
    
    async def read_basic_info(self) -> Optional[Dict]:
        """Read basic BMS information (voltage, current, SOC, etc.)"""
        if not self.client or not self.is_connected:
            return None
            
        try:
            # Send command and read response
            await self.client.write_gatt_char(self.CHAR_UUID, self.CMD_BASIC_INFO)
            await asyncio.sleep(0.1)  # Wait for response
            
            response = await self.client.read_gatt_char(self.CHAR_UUID)
            return self._parse_basic_info(response)
            
        except Exception as e:
            logger.error(f"Error reading basic info from {self.track} track BMS: {e}")
            return None
    
    async def read_cell_voltages(self) -> Optional[List[float]]:
        """Read individual cell voltages"""
        if not self.client or not self.is_connected:
            return None
            
        try:
            await self.client.write_gatt_char(self.CHAR_UUID, self.CMD_CELL_VOLTAGES)
            await asyncio.sleep(0.1)
            
            response = await self.client.read_gatt_char(self.CHAR_UUID)
            return self._parse_cell_voltages(response)
            
        except Exception as e:
            logger.error(f"Error reading cell voltages from {self.track} track BMS: {e}")
            return None
    
    def _parse_basic_info(self, data: bytes) -> Dict:
        """Parse basic info response from BMS"""
        if len(data) < 23:
            logger.warning(f"Invalid basic info response length: {len(data)}")
            return {}
        
        try:
            # Parse according to Overkill BMS protocol
            voltage = struct.unpack('>H', data[4:6])[0] / 100.0  # Total voltage in V
            current = struct.unpack('>h', data[6:8])[0] / 100.0  # Current in A (signed)
            remaining_capacity = struct.unpack('>H', data[8:10])[0] / 100.0  # Ah
            nominal_capacity = struct.unpack('>H', data[10:12])[0] / 100.0  # Ah
            soc = data[19]  # State of charge in %
            
            return {
                'voltage': voltage,
                'current': current,
                'remaining_capacity': remaining_capacity,
                'nominal_capacity': nominal_capacity,
                'soc': soc,
                'temperature': data[16] - 40  # Temperature offset
            }
        except Exception as e:
            logger.error(f"Error parsing basic info: {e}")
            return {}
    
    def _parse_cell_voltages(self, data: bytes) -> List[float]:
        """Parse cell voltage response from BMS"""
        voltages = []
        try:
            # Skip header, read cell voltages (2 bytes each)
            for i in range(4, len(data) - 3, 2):
                if i + 1 < len(data):
                    voltage = struct.unpack('>H', data[i:i+2])[0] / 1000.0
                    if voltage > 0.5:  # Valid voltage reading
                        voltages.append(voltage)
        except Exception as e:
            logger.error(f"Error parsing cell voltages: {e}")
        
        return voltages

class BMSService:
    """Main service to manage BMS connections and data collection"""
    
    def __init__(self):
        self.bms_left: Optional[OverkillBMS] = None
        self.bms_right: Optional[OverkillBMS] = None
        self.running = False
        self.btbms_url = "http://localhost:3000"
        
        # BMS Configuration - UPDATE THESE WITH YOUR ACTUAL MAC ADDRESSES
        self.left_bms_mac = "00:00:00:00:00:00"  # Replace with left track BMS MAC
        self.right_bms_mac = "00:00:00:00:00:00"  # Replace with right track BMS MAC
        
    async def initialize(self):
        """Initialize BMS connections"""
        if not BLUETOOTH_AVAILABLE:
            logger.error("Bluetooth not available. Install bleak: pip install bleak")
            return False
            
        logger.info("Initializing Overkill Solar BMS service...")
        
        # Create BMS instances
        self.bms_left = OverkillBMS(self.left_bms_mac, "left", battery_offset=0)
        self.bms_right = OverkillBMS(self.right_bms_mac, "right", battery_offset=4)
        
        # Try to connect to both BMS units
        left_connected = await self.bms_left.connect()
        right_connected = await self.bms_right.connect()
        
        if not left_connected and not right_connected:
            logger.error("Failed to connect to any BMS units")
            return False
            
        logger.info(f"BMS connections: Left={left_connected}, Right={right_connected}")
        return True
    
    async def read_all_batteries(self) -> List[Dict]:
        """Read data from all batteries and format for BtBmsDisplay"""
        batteries = []
        
        # Read left track (batteries 1-4)
        if self.bms_left and self.bms_left.is_connected:
            left_data = await self._read_track_data(self.bms_left, 1)
            batteries.extend(left_data)
        else:
            # Add mock data for disconnected left track
            batteries.extend(self._generate_mock_track(1, 4))
        
        # Read right track (batteries 5-8)
        if self.bms_right and self.bms_right.is_connected:
            right_data = await self._read_track_data(self.bms_right, 5)
            batteries.extend(right_data)
        else:
            # Add mock data for disconnected right track
            batteries.extend(self._generate_mock_track(5, 8))
        
        return batteries
    
    async def _read_track_data(self, bms: OverkillBMS, start_battery: int) -> List[Dict]:
        """Read data from a single track BMS"""
        batteries = []
        
        try:
            # Get basic info (pack level data)
            basic_info = await bms.read_basic_info()
            cell_voltages = await bms.read_cell_voltages()
            
            if not basic_info:
                return self._generate_mock_track(start_battery, start_battery + 3)
            
            # Create battery data for each cell
            for i in range(4):  # 4 cells per BMS
                battery_num = start_battery + i
                
                # Use individual cell voltage if available, otherwise estimate
                if cell_voltages and i < len(cell_voltages):
                    voltage = cell_voltages[i]
                else:
                    voltage = basic_info.get('voltage', 13.2) / 4  # Estimate per cell
                
                # Calculate charge level from voltage (LiFePO4 curve)
                charge_level = self._voltage_to_soc(voltage)
                
                batteries.append({
                    'batteryNumber': battery_num,
                    'voltage': round(voltage, 2),
                    'amperage': round(basic_info.get('current', 0), 1),
                    'chargeLevel': charge_level,
                    'track': bms.track
                })
                
        except Exception as e:
            logger.error(f"Error reading {bms.track} track data: {e}")
            return self._generate_mock_track(start_battery, start_battery + 3)
        
        return batteries
    
    def _voltage_to_soc(self, voltage: float) -> int:
        """Convert LiFePO4 cell voltage to State of Charge percentage"""
        # LiFePO4 voltage curve approximation
        if voltage >= 3.6:
            return 100
        elif voltage >= 3.4:
            return int(80 + (voltage - 3.4) * 100)
        elif voltage >= 3.3:
            return int(60 + (voltage - 3.3) * 200)
        elif voltage >= 3.2:
            return int(40 + (voltage - 3.2) * 200)
        elif voltage >= 3.0:
            return int(20 + (voltage - 3.0) * 100)
        elif voltage >= 2.8:
            return int((voltage - 2.8) * 100)
        else:
            return 0
    
    def _generate_mock_track(self, start: int, end: int) -> List[Dict]:
        """Generate mock data for disconnected track"""
        batteries = []
        for i in range(start, end + 1):
            batteries.append({
                'batteryNumber': i,
                'voltage': 3.3,
                'amperage': 0.0,
                'chargeLevel': 75,
                'track': 'left' if i <= 4 else 'right'
            })
        return batteries
    
    async def send_to_btbms(self, batteries: List[Dict]):
        """Send battery data to BtBmsDisplay API"""
        try:
            # Format data for the existing API
            api_data = []
            for battery in batteries:
                api_data.append({
                    'batteryNumber': battery['batteryNumber'],
                    'voltage': battery['voltage'],
                    'amperage': battery['amperage'],
                    'chargeLevel': battery['chargeLevel']
                })
            
            # Send to BtBmsDisplay API (if running)
            response = requests.post(
                f"{self.btbms_url}/api/batteries/update",
                json=api_data,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug("Successfully sent data to BtBmsDisplay")
            else:
                logger.warning(f"BtBmsDisplay API returned status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"BtBmsDisplay not available: {e}")
        except Exception as e:
            logger.error(f"Error sending data to BtBmsDisplay: {e}")
    
    async def run(self):
        """Main service loop"""
        self.running = True
        logger.info("Starting BMS monitoring service...")
        
        while self.running:
            try:
                # Read all battery data
                batteries = await self.read_all_batteries()
                
                # Log current status
                logger.info(f"Read {len(batteries)} batteries")
                for battery in batteries:
                    logger.info(f"Battery {battery['batteryNumber']}: "
                              f"{battery['voltage']}V, {battery['amperage']}A, "
                              f"{battery['chargeLevel']}% ({battery.get('track', 'unknown')} track)")
                
                # Send to BtBmsDisplay
                await self.send_to_btbms(batteries)
                
                # Wait before next reading
                await asyncio.sleep(5)  # Read every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down BMS service...")
        self.running = False
        
        if self.bms_left:
            await self.bms_left.disconnect()
        if self.bms_right:
            await self.bms_right.disconnect()

# Global service instance
bms_service = BMSService()

async def main():
    """Main entry point"""
    
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(bms_service.shutdown())
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize and run service
    if await bms_service.initialize():
        await bms_service.run()
    else:
        logger.error("Failed to initialize BMS service")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
