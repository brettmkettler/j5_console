#!/usr/bin/env python3
"""
FBUS Parser for FrSky TDR18 Receiver
Reads FBUS serial protocol and extracts channel values
"""

import serial
import threading
import time
import logging

logger = logging.getLogger(__name__)

class FBUSParser:
    """Parse FrSky FBUS protocol from serial port"""
    
    def __init__(self, port='/dev/ttyAMA0', baudrate=115200):
        """
        Initialize FBUS parser
        
        Args:
            port: Serial port (default /dev/ttyAMA0 for GPIO 14/15)
            baudrate: FBUS baudrate (default 115200)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.thread = None
        
        # Channel data (16 channels, values 0-2047, center ~1024)
        self.channels = [1024] * 16
        self.last_update = 0
        
        # Callbacks for channel changes
        self.callbacks = {}
        
    def start(self):
        """Start reading FBUS data"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"FBUS parser started on {self.port} at {self.baudrate} baud")
            print(f"🎮 FBUS parser started on {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start FBUS parser: {e}")
            print(f"❌ Failed to start FBUS parser: {e}")
            return False
    
    def stop(self):
        """Stop reading FBUS data"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.serial:
            self.serial.close()
        logger.info("FBUS parser stopped")
        print("🎮 FBUS parser stopped")
    
    def _read_loop(self):
        """Main reading loop"""
        buffer = bytearray()
        
        while self.running:
            try:
                if self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    buffer.extend(data)
                    
                    # Process complete frames
                    while len(buffer) >= 28:  # FBUS frame is 28 bytes
                        frame = self._parse_frame(buffer[:28])
                        if frame:
                            self._update_channels(frame)
                            buffer = buffer[28:]
                        else:
                            # Invalid frame, skip one byte and try again
                            buffer = buffer[1:]
                
                time.sleep(0.001)  # 1ms sleep
                
            except Exception as e:
                logger.error(f"Error in FBUS read loop: {e}")
                time.sleep(0.1)
    
    def _parse_frame(self, data):
        """
        Parse FBUS frame
        
        FBUS frame format (28 bytes):
        - Byte 0: Header (0x0F)
        - Bytes 1-24: Channel data (16 channels, 11 bits each)
        - Byte 25: Flags
        - Byte 26: Checksum
        - Byte 27: End byte (0x00)
        """
        if len(data) != 28:
            return None
        
        # Check header and end byte
        if data[0] != 0x0F or data[27] != 0x00:
            return None
        
        # Verify checksum
        checksum = sum(data[1:26]) & 0xFF
        if checksum != data[26]:
            logger.debug(f"FBUS checksum mismatch: {checksum} != {data[26]}")
            return None
        
        # Extract 16 channels (11 bits each)
        channels = []
        bit_offset = 0
        
        for i in range(16):
            # Get 11 bits for this channel
            byte_offset = bit_offset // 8
            bit_in_byte = bit_offset % 8
            
            # Read 2 bytes and extract 11 bits
            if byte_offset + 1 < 24:
                value = (data[1 + byte_offset] | (data[2 + byte_offset] << 8))
                value = (value >> bit_in_byte) & 0x7FF  # 11 bits
                channels.append(value)
            else:
                channels.append(1024)  # Default center value
            
            bit_offset += 11
        
        return channels
    
    def _update_channels(self, channels):
        """Update channel values and trigger callbacks"""
        self.channels = channels
        self.last_update = time.time()
        
        # Trigger callbacks for changed channels
        for channel_num, callback in self.callbacks.items():
            if 0 <= channel_num < len(channels):
                try:
                    callback(channel_num, channels[channel_num])
                except Exception as e:
                    logger.error(f"Error in channel {channel_num} callback: {e}")
    
    def get_channel(self, channel_num):
        """
        Get current value for a channel
        
        Args:
            channel_num: Channel number (0-15)
            
        Returns:
            Channel value (0-2047, center ~1024)
        """
        if 0 <= channel_num < len(self.channels):
            return self.channels[channel_num]
        return 1024
    
    def register_callback(self, channel_num, callback):
        """
        Register callback for channel changes
        
        Args:
            channel_num: Channel number (0-15)
            callback: Function to call with (channel_num, value)
        """
        self.callbacks[channel_num] = callback
        logger.info(f"Registered callback for channel {channel_num}")
    
    def is_active(self):
        """Check if FBUS data is being received"""
        return (time.time() - self.last_update) < 1.0  # Active if updated within 1 second


if __name__ == '__main__':
    # Test the parser
    logging.basicConfig(level=logging.DEBUG)
    
    parser = FBUSParser()
    
    def channel_callback(channel, value):
        print(f"Channel {channel}: {value}")
    
    # Register callbacks for channels 0 and 1
    parser.register_callback(0, channel_callback)
    parser.register_callback(1, channel_callback)
    
    if parser.start():
        print("FBUS parser running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
                print(f"Channel 0: {parser.get_channel(0)}, Channel 1: {parser.get_channel(1)}")
        except KeyboardInterrupt:
            print("\nStopping...")
            parser.stop()
