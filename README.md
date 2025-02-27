# Hệ thống giám sát mực nước và nhiệt độ hồ chứa nước

Dự án này tạo một hệ thống giám sát mực nước và nhiệt độ cho hồ chứa nước, sử dụng Raspberry Pi Pico và các cảm biến. Hệ thống cho phép truy cập dữ liệu từ xa qua điện thoại hoặc bất kỳ thiết bị nào có trình duyệt web.

## Thiết bị sử dụng

- Level Transmitter QDY30A-B (phạm vi 0-3m, RS485, DC 24V)
- Cảm biến nhiệt độ MAX31855 (thermocouple)
- Cảm biến nhiệt độ/độ ẩm DHT22
- Raspberry Pi Pico (Maker Pi Pico)
- Nguồn điện SDR-120-24 (24V)
- Iriv IO Controller (IR4.0 Industrial I/O Controller)

## Sơ đồ kết nối

### Cấp nguồn
- SDR-120-24 cung cấp nguồn 24V cho Level Transmitter QDY30A-B và Iriv IO Controller
- Maker Pi Pico sử dụng nguồn USB hoặc nguồn DC 5V

### Level Transmitter QDY30A-B (RS485)
- VCC: Kết nối với nguồn 24V từ SDR-120-24
- GND: Kết nối với GND chung
- A (485+): Kết nối với A trên bộ chuyển đổi RS485-UART
- B (485-): Kết nối với B trên bộ chuyển đổi RS485-UART

Bộ chuyển đổi RS485-UART:
- TX: Kết nối với GP8 (UART1 TX) trên Raspberry Pi Pico
- RX: Kết nối với GP9 (UART1 RX) trên Raspberry Pi Pico
- VCC: Kết nối với 3.3V từ Raspberry Pi Pico
- GND: Kết nối với GND chung

### MAX31855 (SPI)
- VCC: Kết nối với 3.3V từ Raspberry Pi Pico
- GND: Kết nối với GND chung
- SCK: Kết nối với GP18 (SPI0 SCK) trên Raspberry Pi Pico
- MISO: Kết nối với GP16 (SPI0 MISO) trên Raspberry Pi Pico
- CS: Kết nối với GP17 trên Raspberry Pi Pico

### DHT22
- VCC: Kết nối với 3.3V từ Raspberry Pi Pico
- GND: Kết nối với GND chung
- DATA: Kết nối với GP15 trên Raspberry Pi Pico

### Iriv IO Controller
- Cấp nguồn 24V từ SDR-120-24
- Kết nối với mạng WiFi cục bộ
- Cấu hình theo hướng dẫn của nhà sản xuất để tích hợp với hệ thống

## Cài đặt phần mềm

1. Cài đặt MicroPython trên Raspberry Pi Pico:
   - Tải phiên bản MicroPython mới nhất cho Raspberry Pi Pico từ trang chủ MicroPython
   - Giữ nút BOOTSEL trên Pico trong khi cắm vào máy tính qua cổng USB
   - Kéo và thả file UF2 vào thiết bị để cài đặt MicroPython

2. Cài đặt Thonny IDE:
   - Tải Thonny từ trang web chính thức: https://thonny.org/
   - Cài đặt theo hướng dẫn cho hệ điều hành của bạn

3. Tải các file mã nguồn:
   - main.py - File chính của dự án
   - water_level.py - Module xử lý cảm biến mực nước
   - temperature.py - Module xử lý cảm biến nhiệt độ
   - web_server.py - Module web server

4. Cấu hình WiFi:
   - Mở file main.py
   - Tìm và chỉnh sửa biến `WIFI_SSID` và `WIFI_PASSWORD` thành thông tin WiFi của bạn

5. Tải mã lên Raspberry Pi Pico:
   - Mở Thonny IDE
   - Kết nối với Raspberry Pi Pico
   - Mở các file dự án trong Thonny
   - Lưu từng file vào Raspberry Pi Pico (File > Save as... > Raspberry Pi Pico)

## Sử dụng

1. Đảm bảo tất cả các kết nối phần cứng đã được thực hiện theo hướng dẫn
2. Cấp nguồn cho hệ thống
3. Raspberry Pi Pico sẽ tự động chạy file main.py và kết nối với mạng WiFi
4. Khi kết nối thành công, màn hình sẽ hiển thị địa chỉ IP của web server
5. Truy cập địa chỉ IP đó từ trình duyệt web trên điện thoại hoặc máy tính của bạn
6. Web server sẽ hiển thị dữ liệu mực nước và nhiệt độ theo thời gian thực

## API

Hệ thống cung cấp API đơn giản để tích hợp với các ứng dụng khác:

- GET `/`: Trả về giao diện web
- GET `/api/data`: Trả về dữ liệu cảm biến dạng JSON

## Xử lý sự cố

1. **Hệ thống không kết nối được với WiFi**
   - Kiểm tra tên và mật khẩu WiFi đã nhập đúng chưa
   - Đảm bảo Raspberry Pi Pico nằm trong phạm vi WiFi

2. **Không đọc được dữ liệu từ cảm biến mực nước**
   - Kiểm tra kết nối RS485
   - Xác minh cảm biến đã được cấp nguồn 24V
   - Kiểm tra cấu hình Modbus (địa chỉ slave, tốc độ truyền, v.v.)

3. **Không đọc được nhiệt độ từ MAX31855**
   - Kiểm tra kết nối SPI
   - Xác minh thermocouple đã được kết nối đúng

4. **Không đọc được dữ liệu từ DHT22**
   - Kiểm tra kết nối dữ liệu
   - Đảm bảo điện trở kéo lên 10k đã được kết nối (nếu không có sẵn)

5. **Web server không hoạt động**
   - Kiểm tra kết nối WiFi
   - Khởi động lại Raspberry Pi Pico
   - Kiểm tra cổng tường lửa nếu kết nối từ bên ngoài mạng LAN

## Bảo trì

- Kiểm tra định kỳ các kết nối dây
- Cập nhật mã nguồn khi cần thiết
- Sao lưu mã nguồn trước khi thực hiện bất kỳ thay đổi nào

## Mở rộng

Hệ thống có thể mở rộng thêm các tính năng như:

1. Thêm các cảm biến khác (pH, độ dẫn, v.v.)
2. Thêm chức năng cảnh báo khi mực nước hoặc nhiệt độ vượt ngưỡng
3. Lưu trữ dữ liệu lịch sử trên thẻ SD
4. Tích hợp với các nền tảng IoT như Blynk, ThingSpeak, v.v.

## Tác giả

Hệ thống được phát triển bởi [Tên của bạn]

## Giấy phép

Dự án này được phân phối theo giấy phép MIT. 