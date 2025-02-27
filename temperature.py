import time
from machine import Pin, SPI

class MAX31855Sensor:
    """
    Class xử lý cảm biến nhiệt độ MAX31855K (Thermocouple)
    """
    
    def __init__(self, spi, cs_pin):
        """
        Khởi tạo cảm biến MAX31855
        
        Tham số:
        - spi: Đối tượng SPI đã được khởi tạo
        - cs_pin: Pin CS (Chip Select) để giao tiếp với cảm biến
        """
        self.spi = spi
        self.cs = cs_pin
        self.cs.value(1)  # Disable chip select
    
    def read_temp(self):
        """Đọc nhiệt độ từ cảm biến MAX31855"""
        try:
            # Kích hoạt cảm biến (CS low)
            self.cs.value(0)
            
            # Đọc 4 byte dữ liệu từ cảm biến
            data = bytearray(4)
            self.spi.readinto(data)
            
            # Giải phóng cảm biến (CS high)
            self.cs.value(1)
            
            # Kiểm tra lỗi
            if data[3] & 0x01:
                print("Lỗi cảm biến MAX31855: Open circuit")
                return None
            if data[3] & 0x02:
                print("Lỗi cảm biến MAX31855: Short to GND")
                return None
            if data[3] & 0x04:
                print("Lỗi cảm biến MAX31855: Short to VCC")
                return None
            
            # Trích xuất giá trị nhiệt độ (14 bit đầu tiên)
            raw_temp = ((data[0] << 8) | data[1]) >> 2
            
            # Xử lý giá trị âm (nếu bit dấu là 1)
            if raw_temp & 0x2000:
                # Số âm, áp dụng bù 2
                raw_temp = raw_temp - 0x4000
            
            # Chuyển đổi thành độ C (0.25 độ C mỗi bit)
            temp_c = raw_temp * 0.25
            
            # Làm tròn đến 2 chữ số thập phân
            return round(temp_c, 2)
        except Exception as e:
            print("Lỗi khi đọc MAX31855:", e)
            return None

class DHT22Sensor:
    """
    Class xử lý cảm biến nhiệt độ/độ ẩm DHT22 (AM2302)
    """
    
    def __init__(self, pin):
        """
        Khởi tạo cảm biến DHT22
        
        Tham số:
        - pin: Pin để giao tiếp với cảm biến DHT22
        """
        self.pin = pin
        self.last_read = 0
        self.temp = None
        self.humidity = None
    
    def _pulses_to_binary(self, pulses, threshold):
        """Chuyển đổi độ dài xung thành dữ liệu nhị phân"""
        binary = 0
        for i, pulse in enumerate(pulses):
            binary = binary << 1
            if pulse > threshold:
                binary = binary | 1
        return binary
    
    def read(self):
        """Đọc nhiệt độ và độ ẩm từ cảm biến DHT22"""
        try:
            # Đảm bảo thời gian tối thiểu giữa các lần đọc là 2 giây
            current_time = time.time()
            if current_time - self.last_read < 2:
                if self.temp is not None and self.humidity is not None:
                    return self.temp, self.humidity
                time.sleep(2 - (current_time - self.last_read))
            
            self.last_read = time.time()
            
            # Reset giao tiếp với DHT22
            pin = self.pin
            pin.init(Pin.OUT)
            pin.value(1)
            time.sleep_ms(50)
            
            # Gửi tín hiệu bắt đầu
            pin.value(0)
            time.sleep_ms(20)  # Ít nhất 18ms
            pin.value(1)
            time.sleep_us(30)  # 20-40us
            
            # Chuyển pin sang chế độ đọc
            pin.init(Pin.IN, Pin.PULL_UP)
            
            # Đọc phản hồi từ DHT22
            timeout = 100000  # Thời gian chờ tối đa (100ms)
            count = 0
            
            # Chờ pin xuống thấp
            while pin.value() == 1:
                count += 1
                if count > timeout:
                    return None, None
            
            # Chờ pin lên cao
            count = 0
            while pin.value() == 0:
                count += 1
                if count > timeout:
                    return None, None
            
            # Chờ pin xuống thấp
            count = 0
            while pin.value() == 1:
                count += 1
                if count > timeout:
                    return None, None
            
            # Đọc 40 bit dữ liệu (80 xung)
            pulses = []
            for _ in range(40):
                # Chờ pin lên cao
                count = 0
                while pin.value() == 0:
                    count += 1
                    if count > timeout:
                        return None, None
                
                # Đo thời gian pin ở mức cao
                count = 0
                start = time.ticks_us()
                while pin.value() == 1:
                    count += 1
                    if count > timeout:
                        return None, None
                pulses.append(time.ticks_us() - start)
            
            # Phân tích dữ liệu
            threshold = 50  # Ngưỡng phân biệt bit 0 và bit 1 (thường là ~50us)
            
            # Chuyển đổi xung thành bit
            bits = self._pulses_to_binary(pulses, threshold)
            
            # Trích xuất dữ liệu từ 40 bit nhận được
            humidity_high = (bits >> 32) & 0xFF
            humidity_low = (bits >> 24) & 0xFF
            temp_high = (bits >> 16) & 0xFF
            temp_low = (bits >> 8) & 0xFF
            checksum = bits & 0xFF
            
            # Kiểm tra checksum
            calc_checksum = (humidity_high + humidity_low + temp_high + temp_low) & 0xFF
            if calc_checksum != checksum:
                print("Lỗi checksum DHT22")
                return None, None
            
            # Tính toán giá trị thực
            humidity = ((humidity_high << 8) | humidity_low) / 10.0
            
            # Xử lý nhiệt độ (bit dấu ở vị trí bit thứ 15)
            if temp_high & 0x80:
                # Số âm
                temp = -((((temp_high & 0x7F) << 8) | temp_low) / 10.0)
            else:
                temp = ((temp_high << 8) | temp_low) / 10.0
            
            # Cập nhật giá trị đã đọc
            self.temp = round(temp, 2)
            self.humidity = round(humidity, 2)
            
            return self.temp, self.humidity
        except Exception as e:
            print("Lỗi khi đọc DHT22:", e)
            return None, None 