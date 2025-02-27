from machine import UART
import time

class GSM:
    def __init__(self, uart_id=1, tx_pin=8, rx_pin=9, baud_rate=9600):
        self.uart = UART(uart_id, baud_rate)
        self.uart.init(baudrate=baud_rate, bits=8, parity=None, stop=1, tx=tx_pin, rx=rx_pin)
        time.sleep(1)
        
    def send_command(self, command, timeout=1000):
        self.uart.write(command + '\r\n')
        time.sleep_ms(timeout)
        response = ""
        while self.uart.any():
            response += self.uart.read().decode('utf-8')
        return response
        
    def send_sms(self, phone_number, message):
        # Đặt module ở chế độ text
        self.send_command('AT+CMGF=1', 1000)
        # Đặt số điện thoại nhận tin nhắn
        self.send_command(f'AT+CMGS="{phone_number}"', 1000)
        # Gửi nội dung tin nhắn và kết thúc bằng Ctrl+Z (ký tự ASCII 26)
        response = self.send_command(message + chr(26), 10000)
        return "OK" in response
        
    def initialize(self):
        # Thử khởi tạo kết nối với module
        response = self.send_command("AT", 1000)
        if "OK" in response:
            print("GSM Module đã sẵn sàng")
            return True
        else:
            print("Không thể kết nối với GSM Module")
            return False 