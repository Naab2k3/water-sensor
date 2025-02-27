import time
import struct
from machine import UART

class WaterLevelSensor:
    """
    Class xử lý giao tiếp với cảm biến mực nước QDY30A-B qua giao thức Modbus RTU
    """
    
    def __init__(self, uart, max_range=3.0, slave_address=1):
        """
        Khởi tạo cảm biến mực nước
        
        Tham số:
        - uart: Đối tượng UART đã được khởi tạo
        - max_range: Phạm vi đo tối đa (mặc định là 3.0m)
        - slave_address: Địa chỉ Modbus của thiết bị (mặc định là 1)
        """
        self.uart = uart
        self.max_range = max_range
        self.slave_address = slave_address
    
    def _calculate_crc(self, data):
        """Tính toán CRC-16 cho giao thức Modbus RTU"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = crc >> 1
        return crc & 0xFFFF
    
    def _create_read_request(self, register_address, register_count=1):
        """Tạo lệnh đọc Modbus (function code 03)"""
        # Cấu trúc: [slave address, function code, register address (2 bytes), register count (2 bytes), CRC (2 bytes)]
        command = bytearray([
            self.slave_address,         # Slave address
            0x03,                       # Function code (Read Holding Registers)
            register_address >> 8,      # Register address high byte
            register_address & 0xFF,    # Register address low byte
            0x00,                       # Register count high byte
            register_count,             # Register count low byte
        ])
        
        # Thêm CRC
        crc = self._calculate_crc(command)
        command.append(crc & 0xFF)      # CRC low byte
        command.append(crc >> 8)        # CRC high byte
        
        return command
    
    def _parse_response(self, response, register_count=1):
        """Phân tích phản hồi từ thiết bị Modbus"""
        if not response or len(response) < 5:
            return None
            
        # Kiểm tra địa chỉ slave và function code
        if response[0] != self.slave_address or response[1] != 0x03:
            return None
            
        # Số byte dữ liệu
        byte_count = response[2]
        if len(response) < byte_count + 5:  # Slave + FC + Byte count + Data + CRC (2 bytes)
            return None
            
        # Lấy dữ liệu
        data = response[3:3+byte_count]
        
        # Kiểm tra CRC
        received_crc = (response[3+byte_count] << 8) | response[3+byte_count-1]
        calculated_crc = self._calculate_crc(response[:3+byte_count])
        if received_crc != calculated_crc:
            return None
            
        # Xử lý dữ liệu tùy theo số lượng thanh ghi
        if register_count == 1:
            return (data[0] << 8) | data[1]
        else:
            # Xử lý nhiều thanh ghi nếu cần
            results = []
            for i in range(0, byte_count, 2):
                if i + 1 < byte_count:
                    results.append((data[i] << 8) | data[i + 1])
            return results
    
    def read_raw(self):
        """Đọc giá trị thô từ cảm biến"""
        # Địa chỉ thanh ghi chứa giá trị mực nước (cần điều chỉnh theo tài liệu của cảm biến)
        register_address = 0x0000
        
        # Tạo lệnh
        command = self._create_read_request(register_address)
        
        # Xóa bộ đệm UART
        self.uart.read()
        
        # Gửi lệnh
        self.uart.write(command)
        
        # Chờ phản hồi
        time.sleep(0.1)
        
        # Đọc phản hồi
        response = self.uart.read()
        
        # Phân tích phản hồi
        raw_value = self._parse_response(response)
        
        return raw_value
    
    def read_level(self):
        """Đọc mực nước hiện tại và chuyển đổi thành đơn vị mét"""
        try:
            raw_value = self.read_raw()
            if raw_value is None:
                return None
                
            # Chuyển đổi giá trị thô thành mét
            # Giả sử giá trị thô là từ 0-65535 tương ứng với 0-100% của phạm vi đo
            level_percent = raw_value / 65535.0 * 100.0
            level_meters = level_percent / 100.0 * self.max_range
            
            # Làm tròn đến 2 chữ số thập phân
            return round(level_meters, 2)
        except Exception as e:
            print("Lỗi khi đọc mực nước:", e)
            return None 