import time
import network
import socket
import json
from machine import Pin, SPI, UART
import umail
import dht
import max31855
import config

# Import các module tùy chỉnh
from water_level import WaterLevelSensor
from temperature import MAX31855Sensor, DHT22Sensor
from web_server import WebServer
from gsm_module import GSM
from wifi_module import WifiModule


# Cấu hình mạng WiFi
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# Khởi tạo các cảm biến
# QDY30A-B Level Transmitter (RS485)
uart = UART(1, baudrate=9600, tx=Pin(8), rx=Pin(9))
water_level_sensor = WaterLevelSensor(uart, max_range=3.0)  # Range 0-3m

# MAX31855 Temperature Sensors
spi = SPI(0, baudrate=5000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19), miso=Pin(16))
cs1 = Pin(17, Pin.OUT)
cs2 = Pin(20, Pin.OUT)  # Chân CS cho cảm biến thứ hai
max31855_1 = MAX31855Sensor(spi, cs1)
max31855_2 = MAX31855Sensor(spi, cs2)  # Cảm biến thứ hai

# DHT22 Temperature/Humidity Sensor
dht22 = DHT22Sensor(Pin(15))

# LED chỉ thị
led = Pin(25, Pin.OUT)

# Khởi tạo module GSM - điều chỉnh UART ID và pins cho phù hợp
gsm = GSM(uart_id=1, tx_pin=8, rx_pin=9)

# Thêm biến lưu trữ thời gian gửi cảnh báo gần nhất
last_alert_time = 0
ALERT_COOLDOWN = 3600  # Thời gian chờ giữa các cảnh báo (giây) - ở đây là 1 giờ

# Khởi tạo kết nối WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Kết nối WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Chờ kết nối hoặc thất bại
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Đang chờ kết nối...")
            time.sleep(1)
            
    if wlan.isconnected():
        print("Kết nối WiFi thành công!")
        print("IP:", wlan.ifconfig()[0])
        return True
    else:
        print("Kết nối WiFi thất bại!")
        return False

# Hàm đọc dữ liệu từ tất cả cảm biến
def read_sensor_data():
    try:
        water_level = water_level_sensor.read_level()
        max_temp1 = max31855_1.read_temp()
        max_temp2 = max31855_2.read_temp()  # Đọc nhiệt độ từ cảm biến thứ hai
        dht_temp, humidity = dht22.read()
        
        return {
            "water_level": water_level,
            "max_temperature_1": max_temp1,
            "max_temperature_2": max_temp2,  # Thêm dữ liệu từ cảm biến thứ hai
            "avg_max_temperature": (max_temp1 + max_temp2) / 2,  # Nhiệt độ trung bình
            "dht_temperature": dht_temp,
            "humidity": humidity,
            "timestamp": time.time()
        }
    except Exception as e:
        print("Lỗi khi đọc cảm biến:", e)
        return None

# Hàm gửi SMS cảnh báo
def send_sms_alert(message):
    try:
        if gsm.initialize():
            result = gsm.send_sms(config.PHONE_NUMBER, message)
            if result:
                print("SMS cảnh báo đã được gửi!")
                return True
            else:
                print("Không thể gửi SMS")
        else:
            print("GSM Module chưa sẵn sàng")
    except Exception as e:
        print(f"Lỗi khi gửi SMS: {e}")
    return False

# Hàm gửi email cảnh báo
def send_email_alert(subject, message):
    try:
        if connect_wifi():
            smtp = umail.SMTP(config.SMTP_SERVER, config.SMTP_PORT, ssl=True)
            smtp.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            
            msg = f"From: {config.EMAIL_SENDER}\r\nTo: {config.EMAIL_RECIPIENT}\r\nSubject: {subject}\r\n\r\n{message}"
            smtp.write(config.EMAIL_RECIPIENT, msg)
            smtp.quit()
            print("Email cảnh báo đã được gửi!")
            return True
    except Exception as e:
        print(f"Lỗi khi gửi email: {e}")
    return False

# Thêm vào hàm kiểm tra và gửi cảnh báo
def check_and_send_alerts(water_level, temperature, humidity):
    # Thiết lập ngưỡng cảnh báo
    WATER_LEVEL_HIGH = 2.5  # m
    WATER_LEVEL_LOW = 0.5   # m
    TEMP_HIGH = 35.0        # °C
    
    # Kiểm tra mực nước
    if water_level > WATER_LEVEL_HIGH:
        send_email_alert(
            "CẢNH BÁO: Mực nước cao", 
            f"Mực nước hiện tại ({water_level}m) vượt ngưỡng cảnh báo ({WATER_LEVEL_HIGH}m)!"
        )
    elif water_level < WATER_LEVEL_LOW:
        send_email_alert(
            "CẢNH BÁO: Mực nước thấp", 
            f"Mực nước hiện tại ({water_level}m) dưới ngưỡng cảnh báo ({WATER_LEVEL_LOW}m)!"
        )
    
    # Kiểm tra nhiệt độ
    if temperature > TEMP_HIGH:
        send_email_alert(
            "CẢNH BÁO: Nhiệt độ cao", 
            f"Nhiệt độ hiện tại ({temperature}°C) vượt ngưỡng cảnh báo ({TEMP_HIGH}°C)!"
        )

# Hàm chính
def main():
    # Kết nối WiFi
    if not connect_wifi():
        return
    
    # Khởi tạo web server
    web_server = WebServer()
    web_server.start()
    
    # Vòng lặp chính
    while True:
        try:
            # Đọc dữ liệu
            data = read_sensor_data()
            if data:
                # Cập nhật dữ liệu cho web server
                web_server.update_data(data)
                
                # Hiển thị dữ liệu
                print("Mực nước:", data["water_level"], "m")
                print("Nhiệt độ (MAX31855 #1):", data["max_temperature_1"], "°C")
                print("Nhiệt độ (MAX31855 #2):", data["max_temperature_2"], "°C")
                print("Nhiệt độ trung bình (MAX31855):", data["avg_max_temperature"], "°C")
                print("Nhiệt độ (DHT22):", data["dht_temperature"], "°C")
                print("Độ ẩm:", data["humidity"], "%")
                
                # Nhấp nháy LED để biết hệ thống đang chạy
                led.toggle()
            
            # Kiểm tra và gửi cảnh báo sử dụng nhiệt độ trung bình
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                if check_and_send_alerts(data["water_level"], data["avg_max_temperature"], data["humidity"]):
                    last_alert_time = current_time
            
            time.sleep(5)  # Đọc dữ liệu mỗi 5 giây
            
        except Exception as e:
            print(f"Lỗi: {e}")
            time.sleep(10)  # Đợi 10 giây nếu gặp lỗi

# Chạy chương trình
if __name__ == "__main__":
    main() 