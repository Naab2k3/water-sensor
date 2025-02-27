import socket
import json
import time
import _thread

class WebServer:
    """
    Class cung cấp web server đơn giản để truy cập dữ liệu từ điện thoại
    """
    
    def __init__(self, port=80):
        """
        Khởi tạo web server
        
        Tham số:
        - port: Cổng lắng nghe (mặc định là 80)
        """
        self.port = port
        self.socket = None
        self.running = False
        self.sensor_data = {}
        self.last_update = 0
    
    def _generate_html(self):
        """
        Tạo trang HTML với dữ liệu mới nhất
        """
        water_level = self.sensor_data.get("water_level", "N/A")
        max_temp = self.sensor_data.get("max_temperature", "N/A")
        dht_temp = self.sensor_data.get("dht_temperature", "N/A")
        humidity = self.sensor_data.get("humidity", "N/A")
        timestamp = self.sensor_data.get("timestamp", time.time())
        
        # Chuyển timestamp thành chuỗi thời gian
        time_str = time.localtime(timestamp)
        formatted_time = "{:02d}:{:02d}:{:02d} {:02d}/{:02d}/{:04d}".format(
            time_str[3], time_str[4], time_str[5],
            time_str[2], time_str[1], time_str[0]
        )
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hệ thống giám sát hồ nước</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f0f2f5;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                header {{
                    background-color: #0078d7;
                    color: white;
                    padding: 15px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .dashboard {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-top: 20px;
                }}
                .card {{
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    flex: 1;
                    min-width: 200px;
                    padding: 20px;
                    text-align: center;
                }}
                .value {{
                    font-size: 32px;
                    font-weight: bold;
                    margin: 15px 0;
                    color: #0078d7;
                }}
                .label {{
                    color: #666;
                    font-size: 16px;
                }}
                .time {{
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                }}
                .refresh {{
                    display: block;
                    width: 100%;
                    padding: 10px;
                    background-color: #0078d7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                    margin-top: 20px;
                }}
                .refresh:hover {{
                    background-color: #006cc1;
                }}
                @media (max-width: 600px) {{
                    .card {{
                        min-width: 100%;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <h1>Hệ thống giám sát hồ nước</h1>
                </header>
                
                <div class="dashboard">
                    <div class="card">
                        <div class="label">Mực nước</div>
                        <div class="value">{water_level} m</div>
                    </div>
                    
                    <div class="card">
                        <div class="label">Nhiệt độ (MAX31855)</div>
                        <div class="value">{max_temp} °C</div>
                    </div>
                    
                    <div class="card">
                        <div class="label">Nhiệt độ (DHT22)</div>
                        <div class="value">{dht_temp} °C</div>
                    </div>
                    
                    <div class="card">
                        <div class="label">Độ ẩm</div>
                        <div class="value">{humidity} %</div>
                    </div>
                </div>
                
                <div class="time">
                    <p>Cập nhật lúc: {formatted_time}</p>
                </div>
                
                <button class="refresh" onclick="location.reload()">Làm mới dữ liệu</button>
                
                <script>
                    // Tự động làm mới trang sau 60 giây
                    setTimeout(function() {{
                        location.reload();
                    }}, 60000);
                </script>
            </div>
        </body>
        </html>
        """
        return html
    
    def _generate_json(self):
        """
        Tạo phản hồi JSON với dữ liệu mới nhất
        """
        return json.dumps(self.sensor_data)
    
    def update_data(self, data):
        """
        Cập nhật dữ liệu mới nhất từ các cảm biến
        
        Tham số:
        - data: Dictionary chứa dữ liệu từ các cảm biến
        """
        self.sensor_data = data
        self.last_update = time.time()
    
    def _handle_client(self, client_socket, addr):
        """
        Xử lý kết nối từ client
        """
        try:
            # Nhận dữ liệu yêu cầu
            request = client_socket.recv(1024)
            
            # Phân tích yêu cầu HTTP
            request_str = request.decode('utf-8')
            request_lines = request_str.split('\r\n')
            method, path, _ = request_lines[0].split(' ')
            
            # Chuẩn bị phản hồi
            if path == '/':
                # Trang chủ - gửi HTML
                response = "HTTP/1.1 200 OK\r\n"
                response += "Content-Type: text/html; charset=UTF-8\r\n"
                response += "Connection: close\r\n\r\n"
                response += self._generate_html()
            elif path == '/api/data':
                # API endpoint - gửi JSON
                response = "HTTP/1.1 200 OK\r\n"
                response += "Content-Type: application/json\r\n"
                response += "Connection: close\r\n\r\n"
                response += self._generate_json()
            else:
                # Không tìm thấy trang
                response = "HTTP/1.1 404 Not Found\r\n"
                response += "Content-Type: text/plain\r\n"
                response += "Connection: close\r\n\r\n"
                response += "404 Not Found"
            
            # Gửi phản hồi
            client_socket.send(response.encode('utf-8'))
        except Exception as e:
            print("Lỗi xử lý client:", e)
        finally:
            # Đóng kết nối
            client_socket.close()
    
    def _server_loop(self):
        """
        Vòng lặp chính của web server
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # Gắn socket với cổng
            self.socket.bind(('0.0.0.0', self.port))
            
            # Lắng nghe kết nối
            self.socket.listen(5)
            print(f"Web server đang chạy trên cổng {self.port}")
            
            self.running = True
            while self.running:
                try:
                    # Chấp nhận kết nối mới
                    client, addr = self.socket.accept()
                    # Xử lý client trong thread riêng
                    _thread.start_new_thread(self._handle_client, (client, addr))
                except Exception as e:
                    if self.running:
                        print("Lỗi chấp nhận kết nối:", e)
        except Exception as e:
            print("Lỗi khởi động web server:", e)
        finally:
            if self.socket:
                self.socket.close()
                self.socket = None
    
    def start(self):
        """
        Bắt đầu web server trong một thread riêng
        """
        if not self.running:
            _thread.start_new_thread(self._server_loop, ())
    
    def stop(self):
        """
        Dừng web server
        """
        self.running = False
        if self.socket:
            # Đóng socket để ngắt vòng lặp accept()
            self.socket.close()
            self.socket = None 