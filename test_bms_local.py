#!/usr/bin/env python3
"""
Local BMS Testing Simulator
Simulates Overkill Solar BMS data for local development and testing
"""

import asyncio
import json
import logging
import time
import random
from typing import Dict, List
import requests
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bms_simulator')

class MockOverkillBMS:
    """Mock Overkill Solar BMS for local testing"""
    
    def __init__(self, track: str, battery_offset: int = 0):
        self.track = track  # 'left' or 'right'
        self.battery_offset = battery_offset
        self.is_connected = True
        self.base_voltage = 3.3  # Base LiFePO4 voltage
        self.base_current = 12.0  # Base current
        self.voltage_drift = 0.0  # Simulated voltage drift over time
        
    async def connect(self) -> bool:
        """Simulate connection"""
        logger.info(f"Mock: Connected to {self.track} track BMS")
        await asyncio.sleep(0.1)  # Simulate connection delay
        return True
    
    async def disconnect(self):
        """Simulate disconnection"""
        logger.info(f"Mock: Disconnected from {self.track} track BMS")
        self.is_connected = False
    
    async def read_basic_info(self) -> Dict:
        """Generate realistic mock BMS data"""
        await asyncio.sleep(0.05)  # Simulate read delay
        
        # Simulate voltage drift over time (charging/discharging)
        self.voltage_drift += random.uniform(-0.001, 0.001)
        self.voltage_drift = max(-0.3, min(0.3, self.voltage_drift))  # Keep within bounds
        
        # Generate realistic pack data
        pack_voltage = (self.base_voltage + self.voltage_drift) * 4  # 4 cells in series
        current = self.base_current + random.uniform(-2, 2)  # ±2A variation
        
        # Simulate different charging states
        time_factor = time.time() % 300  # 5-minute cycle
        if time_factor < 60:  # First minute: charging
            current = abs(current)
        elif time_factor < 120:  # Second minute: discharging
            current = -abs(current)
        else:  # Rest: idle/float
            current = random.uniform(-1, 1)
        
        return {
            'voltage': round(pack_voltage, 2),
            'current': round(current, 1),
            'remaining_capacity': round(45 + random.uniform(-5, 5), 1),
            'nominal_capacity': 50.0,
            'soc': max(10, min(100, int(75 + random.uniform(-15, 15)))),
            'temperature': round(25 + random.uniform(-3, 8), 1)  # 22-33°C
        }
    
    async def read_cell_voltages(self) -> List[float]:
        """Generate realistic individual cell voltages"""
        await asyncio.sleep(0.05)
        
        voltages = []
        for i in range(4):  # 4 cells per pack
            # Add small variations between cells
            cell_voltage = self.base_voltage + self.voltage_drift + random.uniform(-0.02, 0.02)
            # Keep within LiFePO4 safe range
            cell_voltage = max(2.8, min(3.65, cell_voltage))
            voltages.append(round(cell_voltage, 3))
        
        return voltages

class MockBMSService:
    """Mock BMS service for local testing"""
    
    def __init__(self):
        self.bms_left = MockOverkillBMS("left", battery_offset=0)
        self.bms_right = MockOverkillBMS("right", battery_offset=4)
        self.running = False
        self.btbms_url = "http://localhost:3000"
        
    async def initialize(self):
        """Initialize mock BMS connections"""
        logger.info("Initializing Mock BMS service for local testing...")
        
        left_connected = await self.bms_left.connect()
        right_connected = await self.bms_right.connect()
        
        logger.info(f"Mock BMS connections: Left={left_connected}, Right={right_connected}")
        return True
    
    async def read_all_batteries(self) -> List[Dict]:
        """Read mock data from all batteries"""
        batteries = []
        
        # Read left track (batteries 1-4)
        left_data = await self._read_track_data(self.bms_left, 1)
        batteries.extend(left_data)
        
        # Read right track (batteries 5-8)
        right_data = await self._read_track_data(self.bms_right, 5)
        batteries.extend(right_data)
        
        return batteries
    
    async def _read_track_data(self, bms: MockOverkillBMS, start_battery: int) -> List[Dict]:
        """Read mock data from a single track"""
        batteries = []
        
        # Get mock basic info and cell voltages
        basic_info = await bms.read_basic_info()
        cell_voltages = await bms.read_cell_voltages()
        
        # Create battery data for each cell
        for i in range(4):  # 4 cells per BMS
            battery_num = start_battery + i
            
            # Use individual cell voltage
            voltage = cell_voltages[i] if i < len(cell_voltages) else basic_info['voltage'] / 4
            
            # Calculate charge level from voltage
            charge_level = self._voltage_to_soc(voltage)
            
            batteries.append({
                'batteryNumber': battery_num,
                'voltage': round(voltage, 2),
                'amperage': round(basic_info['current'], 1),
                'chargeLevel': charge_level,
                'track': bms.track,
                'temperature': basic_info.get('temperature', 25)
            })
        
        return batteries
    
    def _voltage_to_soc(self, voltage: float) -> int:
        """Convert LiFePO4 cell voltage to State of Charge percentage"""
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
    
    async def send_to_btbms(self, batteries: List[Dict]):
        """Send battery data to BtBmsDisplay API"""
        try:
            # Format data for the API
            api_data = []
            for battery in batteries:
                api_data.append({
                    'batteryNumber': battery['batteryNumber'],
                    'voltage': battery['voltage'],
                    'amperage': battery['amperage'],
                    'chargeLevel': battery['chargeLevel']
                })
            
            # Try to send to BtBmsDisplay
            response = requests.post(
                f"{self.btbms_url}/api/batteries/update",
                json=api_data,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("✅ Successfully sent data to BtBmsDisplay")
            else:
                logger.warning(f"⚠️ BtBmsDisplay API returned status: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.info("🔌 BtBmsDisplay not running (start with 'npm run dev' in BtBmsDisplay folder)")
        except requests.exceptions.RequestException as e:
            logger.debug(f"BtBmsDisplay connection issue: {e}")
        except Exception as e:
            logger.error(f"Error sending data to BtBmsDisplay: {e}")
    
    async def run(self):
        """Main simulation loop"""
        self.running = True
        logger.info("🚀 Starting Mock BMS monitoring service...")
        logger.info("📊 Generating realistic battery data for testing...")
        
        while self.running:
            try:
                # Read all battery data
                batteries = await self.read_all_batteries()
                
                # Log current status
                print(f"\n📋 Mock BMS Data Update ({time.strftime('%H:%M:%S')})")
                print("=" * 60)
                
                for battery in batteries:
                    status_icon = "🔋" if battery['chargeLevel'] > 50 else "🪫"
                    track_icon = "⬅️" if battery['track'] == 'left' else "➡️"
                    
                    print(f"{status_icon} {track_icon} Battery {battery['batteryNumber']}: "
                          f"{battery['voltage']}V | {battery['amperage']:+.1f}A | "
                          f"{battery['chargeLevel']}% | {battery.get('temperature', 25)}°C")
                
                # Send to BtBmsDisplay
                await self.send_to_btbms(batteries)
                
                # Wait before next reading
                await asyncio.sleep(3)  # Update every 3 seconds for testing
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Mock BMS service...")
        self.running = False
        
        await self.bms_left.disconnect()
        await self.bms_right.disconnect()

# Global service instance
mock_bms_service = MockBMSService()

async def main():
    """Main entry point"""
    
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(mock_bms_service.shutdown())
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🔋 Mock Overkill Solar BMS Simulator")
    print("=" * 50)
    print("This simulates real BMS data for local testing")
    print("Start BtBmsDisplay with 'npm run dev' to see live data")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    # Initialize and run service
    if await mock_bms_service.initialize():
        await mock_bms_service.run()
    else:
        logger.error("Failed to initialize Mock BMS service")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
