import socket
import machine
import select
import time
from logger import Logger
from qdy30a_sensor import QDY30ASensor
from data_processor import DataProcessor
import json
import config

class WebServer:
    def __init__(self, qdy30a_sensor, data_processor, watchdog, config, logger):
        self.qdy30a_sensor = qdy30a_sensor
        self.data_processor = data_processor
        self.watchdog = watchdog
        self.config = config
        self.logger = logger
        self.tank_size = self.data_processor.calculate_tank_size()
        self.s = socket.socket()
        self.s.bind(('0.0.0.0', 80))
        self.s.listen(5)
        self.s.setblocking(False)
        self.s.settimeout(3)  # Set a timeout of 3 seconds
        self.connections = []
        self.start_time = time.time()

    def update(self):
        self.watchdog.feed()
        try:
            conn, addr = self.s.accept()
            conn.setblocking(False)
            self.connections.append(conn)
        except OSError:
            pass

        if self.connections:
            readable, writable, _ = select.select(self.connections, self.connections, [], 0)
            
            for conn in readable:
                try:
                    request = conn.recv(1024)
                    if request:
                        self.watchdog.feed()
                        if b'GET /reset' in request:
                            self._send_reset_response(conn)
                        elif b'GET /status.json' in request:  
                            self._serve_json_status(conn)
                        else:
                            self._serve_status_page(conn)
                    else:
                        self.connections.remove(conn)
                        conn.close()
                except Exception as e:
                    self.logger.log(f"Error handling connection: {e}")
                    try:
                        self.connections.remove(conn)
                        conn.close()
                    except:
                        pass

    def _send_reset_response(self, conn):
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
        response += "<html><body><h1>Resetting device...</h1></body></html>"
        conn.send(response)
        conn.close()
        self.connections.remove(conn)
        time.sleep(1)
        machine.reset()

    def _serve_json_status(self, conn):
        level = self.qdy30a_sensor.get_level()
        volume = self.data_processor.calculate_volume(level) if level is not None else None
        
        status = {
            "level_cm": level,
            "volume_liters": volume,
            "tank_size_liters": self.tank_size,
            "uptime_seconds": time.time() - self.start_time,
            "timestamp": time.time()
        }
        
        json_response = json.dumps(status)
        
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Access-Control-Allow-Origin: *\r\n"
        response += f"Content-Length: {len(json_response)}\r\n\r\n"
        response += json_response
        
        conn.send(response)
        conn.close()
        self.connections.remove(conn)

    def _serve_status_page(self, conn):
        level = self.qdy30a_sensor.get_level()
        volume = self.data_processor.calculate_volume(level) if level is not None else None
        
        uptime_seconds = time.time() - self.start_time
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>IRIV IOC Water Level Monitor</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .header {{ background-color: #0066cc; color: white; padding: 10px; text-align: center; border-radius: 5px; }}
                .card {{ background-color: #f0f0f0; border-radius: 5px; padding: 15px; margin-top: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .level-indicator {{ height: 30px; background-color: #0066cc; border-radius: 5px; margin-top: 10px; }}
                .footer {{ margin-top: 20px; text-align: center; font-size: 0.8em; color: #666; }}
                .button {{ background-color: #cc0000; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>IRIV IOC Water Level Monitor</h1>
                </div>
                
                <div class="card">
                    <h2>Tank Status</h2>
                    <p><strong>Level:</strong> {level:.2f} cm</p>
                    <p><strong>Volume:</strong> {volume:.2f} liters</p>
                    <p><strong>Tank Capacity:</strong> {self.tank_size:.2f} liters</p>
                    <p><strong>Fill Percentage:</strong> {(volume / self.tank_size * 100) if volume is not None else 0:.1f}%</p>
                    
                    <div class="level-indicator" style="width: {(volume / self.tank_size * 100) if volume is not None else 0}%;"></div>
                </div>
                
                <div class="card">
                    <h2>System Information</h2>
                    <p><strong>Uptime:</strong> {uptime_str}</p>
                    <p><strong>Tank Number:</strong> {self.config.get('mqtt_tank_number', 'N/A')}</p>
                    <p><strong>Tank Dimensions:</strong> {self.config.get('tank_length_cm', 'N/A')} x {self.config.get('tank_width_cm', 'N/A')} x {self.config.get('tank_height_cm', 'N/A')} cm</p>
                </div>
                
                <div class="card" style="text-align: center;">
                    <form action="/reset" method="get">
                        <button class="button" type="submit">Reset Device</button>
                    </form>
                </div>
                
                <div class="footer">
                    <p>IRIV IOC Water Level Monitor | Firmware v1.0</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/html\r\n"
        response += f"Content-Length: {len(html)}\r\n\r\n"
        response += html
        
        conn.send(response)
        conn.close()
        self.connections.remove(conn)


def start_web_server(qdy30a_sensor, data_processor, watchdog, config, logger):
    return WebServer(qdy30a_sensor, data_processor, watchdog, config, logger)