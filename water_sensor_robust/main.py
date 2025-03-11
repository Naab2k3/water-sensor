import machine
import time
import socket
import sys
from config import load_config
from ethernet_manager import EthernetManager
from mqtt_client import MQTTManager
from qdy30a_sensor import QDY30ASensor
from data_processor import DataProcessor
from web_server import start_web_server
from logger import Logger
from watchdog import WatchdogTimer

# Định nghĩa LED tích hợp trên Pico 2 W
LED = machine.Pin("LED", machine.Pin.OUT)

def blink_led(times=3, delay=0.2):
    """Nhấp nháy LED để chỉ thị trạng thái"""
    for _ in range(times):
        LED.on()
        time.sleep(delay)
        LED.off()
        time.sleep(delay)

def main():
    # Khởi tạo logger
    logger = Logger()
    logger.log("Starting water sensor system with Pico 2 W and W5500", console=True)
    
    # Nhấp nháy LED để chỉ thị khởi động
    blink_led(3, 0.1)
    
    try:
        # Tải cấu hình
        config = load_config()
        if not config:
            logger.log("Failed to load configuration. Rebooting...", console=True)
            blink_led(5, 0.5)  # Nhấp nháy nhanh để chỉ thị lỗi
            time.sleep(5)
            machine.reset()
        
        # Khởi tạo watchdog timer
        watchdog = WatchdogTimer(timeout_ms=8388)  # Thời gian tối đa cho phép
        
        # Khởi tạo kết nối Ethernet với W5500
        logger.log("Initializing Ethernet connection with W5500...", console=True)
        ethernet_manager = EthernetManager()
        
        # Khởi tạo Ethernet, sử dụng DHCP nếu được cấu hình
        if not ethernet_manager.initialize(watchdog):
            logger.log("Failed to initialize Ethernet. Rebooting...", console=True)
            blink_led(5, 0.5) 
            time.sleep(5)
            machine.reset()
        
        # Lấy thông tin mạng
        network_info = ethernet_manager.get_network_info()
        logger.log(f"Ethernet initialized successfully. IP: {network_info['ip']}", console=True)
        
        # Kiểm tra kết nối internet
        if ethernet_manager.test_internet_connection():
            logger.log("Internet connection test successful", console=True)
            blink_led(2, 0.5)  # Nhấp nháy 2 lần để chỉ thị kết nối thành công
        else:
            logger.log("Internet connection test failed", console=True)
            blink_led(4, 0.2)  # Nhấp nháy 4 lần để chỉ thị lỗi kết nối internet
        
        # Khởi tạo cảm biến QDY30A-B qua RS485
        logger.log("Initializing QDY30A-B sensor...", console=True)
        qdy30a_sensor = QDY30ASensor(
            uart_id=config.get("rs485_uart_id", 1),
            tx_pin=config.get("rs485_tx_pin", 24),
            rx_pin=config.get("rs485_rx_pin", 25),
            baudrate=config.get("rs485_baudrate", 9600),
            sensor_address=config.get("qdy30a_sensor_address", 1)
        )
        logger.log("QDY30A-B sensor initialized", console=True)
        
        # Khởi tạo bộ xử lý dữ liệu
        data_processor = DataProcessor(
            config["tank_height_cm"], config["tank_length_cm"], config["tank_width_cm"]
        )
        
        # Kết nối đến MQTT server
        logger.log("Connecting to MQTT server...", console=True)
        mqtt_manager = MQTTManager(config, qdy30a_sensor, data_processor, watchdog)
        
        # Đăng tải thông tin mạng
        mqtt_manager.publish_ip_address(
            network_info['ip'], 
            network_info['subnet'], 
            network_info['gateway'], 
            network_info['dns']
        )
        logger.log(f"Published network info: IP={network_info['ip']}", console=True)
        
        # Khởi động web server
        logger.log("Starting web server...", console=True)
        web_server = start_web_server(qdy30a_sensor, data_processor, watchdog, config, logger)
        logger.log(f"Web server started at http://{network_info['ip']}/", console=True)
        
        logger.log("Starting main application loop...", console=True)
        
        last_sensor_update = time.ticks_ms()
        last_dhcp_check = time.ticks_ms()
        sensor_update_interval = 5000  # 5 giây
        dhcp_check_interval = 60000    # 60 giây
        
        # Vòng lặp chính
        while True:
            try:
                current_time = time.ticks_ms()
                watchdog.feed()
                
                # Cập nhật web server
                web_server.update()
                
                # Kiểm tra và gia hạn DHCP nếu cần
                if ethernet_manager.config['use_dhcp'] and time.ticks_diff(current_time, last_dhcp_check) >= dhcp_check_interval:
                    ethernet_manager.check_dhcp_lease()
                    last_dhcp_check = current_time
                
                # Cập nhật cảm biến và MQTT
                if time.ticks_diff(current_time, last_sensor_update) >= sensor_update_interval:
                    # Đọc mức nước từ cảm biến QDY30A-B
                    level = qdy30a_sensor.read_level(watchdog)
                    
                    # Đăng tải dữ liệu nếu đọc thành công
                    if level is not None:
                        logger.log(f"Level reading: {level:.2f} cm", console=True)
                        publish_result = mqtt_manager.publish_data()
                        mqtt_manager.publish_uptime()
                        
                        # Nhấp nháy LED để chỉ thị đọc thành công
                        LED.on()
                        time.sleep(0.05)
                        LED.off()
                    else:
                        logger.log("Failed to read level from sensor", console=True)
                        # Nhấp nháy LED để chỉ thị lỗi đọc cảm biến
                        blink_led(2, 0.1)
                    
                    last_sensor_update = current_time
                
                time.sleep(0.05)  # Ngủ ngắn để tránh vòng lặp chặt
                
            except Exception as e:
                logger.log(f"Error in main loop: {e}", console=True)
                # Nhấp nháy LED để chỉ thị lỗi
                blink_led(3, 0.2)
                time.sleep(1)
    
    except Exception as e:
        # Xử lý lỗi toàn cục
        sys.print_exception(e)
        print(f"Critical error: {e}")
        blink_led(10, 0.1)  # Nhấp nháy nhanh nhiều lần để chỉ thị lỗi nghiêm trọng
        time.sleep(5)
        machine.reset()

if __name__ == "__main__":
    main()
