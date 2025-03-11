import machine
import time
import struct
from logger import Logger
from watchdog import WatchdogTimer

class QDY30ASensor:
    """
    Driver for QDY30A-B liquid level sensor using RS485 communication
    """
    def __init__(self, uart_id=1, tx_pin=24, rx_pin=25, baudrate=9600, sensor_address=1):
        self.logger = Logger()
        self.uart = machine.UART(
            uart_id,
            baudrate=baudrate,
            tx=machine.Pin(tx_pin),
            rx=machine.Pin(rx_pin),
            bits=8,
            parity=None,
            stop=1,
            timeout=1000  # 1 second timeout
        )
        self.sensor_address = sensor_address
        self.last_reading = None
        self.last_reading_time = 0
        self.reading_interval = 2000  # 2 seconds between readings
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
    def _calculate_crc16(self, data):
        """Calculate CRC-16 (Modbus) for the data"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        # Return CRC as two bytes (low byte first, then high byte)
        return crc & 0xFF, (crc >> 8) & 0xFF
        
    def _build_read_command(self, register_address, register_count=1):
        """Build Modbus RTU read holding registers command (function code 0x03)"""
        # Command structure: [address, function_code, reg_addr_hi, reg_addr_lo, reg_count_hi, reg_count_lo, crc_lo, crc_hi]
        cmd = [
            self.sensor_address,  # Sensor address
            0x03,                 # Function code: Read Holding Registers
            register_address >> 8,  # Register address high byte
            register_address & 0xFF, # Register address low byte
            register_count >> 8,   # Number of registers high byte
            register_count & 0xFF  # Number of registers low byte
        ]
        
        # Calculate CRC and append to command
        crc_lo, crc_hi = self._calculate_crc16(cmd)
        cmd.append(crc_lo)
        cmd.append(crc_hi)
        
        return bytes(cmd)
        
    def _parse_response(self, response, expected_bytes):
        """Parse and validate the Modbus RTU response"""
        if not response or len(response) < 5:  # Minimum valid response length
            self.logger.log(f"Invalid response: too short ({len(response) if response else 0} bytes)")
            return None
            
        # Check if the response is for our sensor address
        if response[0] != self.sensor_address:
            self.logger.log(f"Response address mismatch: expected {self.sensor_address}, got {response[0]}")
            return None
            
        # Check function code (should be 0x03 or error code 0x83)
        if response[1] == 0x83:  # Error response
            error_code = response[2] if len(response) > 2 else "unknown"
            self.logger.log(f"Sensor returned error code: {error_code}")
            return None
            
        if response[1] != 0x03:  # Not a valid read response
            self.logger.log(f"Invalid function code in response: {response[1]}")
            return None
            
        # Check byte count
        byte_count = response[2]
        if byte_count != expected_bytes:
            self.logger.log(f"Unexpected byte count: expected {expected_bytes}, got {byte_count}")
            return None
            
        # Extract data (skip address, function code, and byte count)
        data = response[3:3+byte_count]
        
        # Verify CRC
        if len(response) >= 3 + byte_count + 2:  # Make sure we have CRC bytes
            received_crc_lo = response[3 + byte_count]
            received_crc_hi = response[3 + byte_count + 1]
            
            # Calculate CRC for the received data
            calc_crc_lo, calc_crc_hi = self._calculate_crc16(response[:3+byte_count])
            
            if received_crc_lo != calc_crc_lo or received_crc_hi != calc_crc_hi:
                self.logger.log(f"CRC mismatch: received {received_crc_lo:02X}{received_crc_hi:02X}, calculated {calc_crc_lo:02X}{calc_crc_hi:02X}")
                return None
        
        return data
        
    def read_level(self, watchdog=None):
        """Read the liquid level from the sensor"""
        current_time = time.ticks_ms()
        
        # Check if we need to wait before reading again
        if self.last_reading_time and time.ticks_diff(current_time, self.last_reading_time) < self.reading_interval:
            return self.last_reading
            
        if watchdog:
            watchdog.feed()
            
        try:
            # Clear any pending data in the UART buffer
            while self.uart.any():
                self.uart.read()
                
            # Send read command for register 0 (assuming this is the level register)
            # Note: Actual register address may vary depending on sensor documentation
            cmd = self._build_read_command(0)
            self.uart.write(cmd)
            
            # Wait for response
            start_time = time.ticks_ms()
            while not self.uart.any() and time.ticks_diff(time.ticks_ms(), start_time) < 1000:
                time.sleep_ms(10)
                if watchdog:
                    watchdog.feed()
                    
            # Read response
            if self.uart.any():
                response = self.uart.read()
                
                # Parse response (expecting 4 bytes of data for a float value)
                data = self._parse_response(response, 4)
                
                if data and len(data) == 4:
                    # Convert 4 bytes to float (assuming IEEE 754 format)
                    # Note: Byte order may need adjustment based on sensor documentation
                    level = struct.unpack('>f', data)[0]  # Big-endian float
                    
                    self.last_reading = level
                    self.last_reading_time = current_time
                    self.consecutive_failures = 0
                    return level
            
            # If we get here, reading failed
            self.consecutive_failures += 1
            self.logger.log(f"Failed to read sensor (attempt {self.consecutive_failures})")
            
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.logger.log("Too many consecutive failures, sensor may be disconnected")
                
            return self.last_reading  # Return last valid reading or None
            
        except Exception as e:
            self.consecutive_failures += 1
            self.logger.log(f"Error reading sensor: {e}")
            return self.last_reading
            
    def get_level(self):
        """Get the last read level without triggering a new reading"""
        return self.last_reading 