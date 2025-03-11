from umqtt.robust import MQTTClient
import time, json 
from logger import Logger
from watchdog import WatchdogTimer


class MQTTManager:
    def __init__(self, config, qdy30a_sensor, data_processor, watchdog):
        self.logger = Logger()
        self.config = config
        self.qdy30a_sensor = qdy30a_sensor
        self.data_processor = data_processor
        self.client = None
        self.last_ping = 0
        self.ping_interval = 60  # Ping every 60 seconds
        self.start_time = time.time()  # Track the start time
        self.base_topic = f"{self.config['mqtt_base_topic']}/{self.config['mqtt_tank_number']}"
        self.watchdog = watchdog
        self.reconnect_with_backoff()

    def _setup_mqtt(self):
        try:
            self.watchdog.feed()  # Feed before attempting to connect
            client = MQTTClient('IRIV-IOC-WaterSensor', self.config['mqtt_server'],
                                port=self.config['mqtt_port'],
                                user=self.config['mqtt_user'],
                                password=self.config['mqtt_password'],
                                keepalive=60)  # Reduced keepalive to 60 seconds
            client.connect()
            self.watchdog.feed()  # Feed after successful connection
            self.logger.log("Connected to MQTT server.")
            return client
        except Exception as e:
            self.logger.log(f"Failed to connect to MQTT server: {e}")
            return None

    def _ping_mqtt(self):
        current_time = time.time()
        if current_time - self.last_ping >= self.ping_interval:
            try:
                self.client.ping()
                self.last_ping = current_time
                return True
            except Exception as e:
                self.logger.log(f"MQTT ping failed: {e}")
                return False
        return True

    def reconnect_with_backoff(self, initial_delay=1, max_delay=4, factor=2):
        delay = initial_delay
        while True:
            self.client = self._setup_mqtt()
            if self.client:
                return True
            
            self.logger.log(f"Retrying MQTT connection in {delay} seconds...")
            time.sleep(delay)
            delay = min(delay * factor, max_delay)
            self.watchdog.feed()

    def publish_data(self):
        if not self.client:
            success = self.reconnect_with_backoff()
            if not success:
                return False

        try:
            # Check MQTT connection with ping
            if not self._ping_mqtt():
                self.client = None  # Force reconnection on next attempt
                return False

            # Get level from QDY30A-B sensor
            level = self.qdy30a_sensor.get_level()
            
            if level is None:
                self.logger.log("No valid level reading available")
                return False
                
            # Calculate water volume based on level
            # For QDY30A-B, the level is already in cm, so we can use it directly
            volume_liters = self.data_processor.calculate_volume(level)
            
            # Prepare data payload
            data = {
                "level_cm": level,
                "volume_liters": volume_liters,
                "tank_size_liters": self.data_processor.calculate_tank_size(),
                "timestamp": time.time()
            }
            
            # Convert to JSON and publish
            json_data = json.dumps(data)
            self.client.publish(f"{self.base_topic}/data", json_data)
            self.logger.log(f"Published data: Level={level:.2f}cm, Volume={volume_liters:.2f}L")
            
            return True
            
        except Exception as e:
            self.logger.log(f"Error publishing data: {e}")
            self.client = None  # Force reconnection on next attempt
            return False

    def publish_uptime(self):
        if not self.client:
            success = self.reconnect_with_backoff()
            if not success:
                return False

        try:
            uptime_seconds = time.time() - self.start_time
            uptime_data = {
                "uptime_seconds": uptime_seconds,
                "timestamp": time.time()
            }
            
            json_data = json.dumps(uptime_data)
            self.client.publish(f"{self.base_topic}/uptime", json_data)
            return True
            
        except Exception as e:
            self.logger.log(f"Error publishing uptime: {e}")
            self.client = None  # Force reconnection on next attempt
            return False

    def publish_ip_address(self, ip, subnet, gateway, dns):
        if not self.client:
            success = self.reconnect_with_backoff()
            if not success:
                return False

        try:
            network_data = {
                "ip": ip,
                "subnet": subnet,
                "gateway": gateway,
                "dns": dns,
                "timestamp": time.time()
            }
            
            json_data = json.dumps(network_data)
            self.client.publish(f"{self.base_topic}/network", json_data)
            self.logger.log(f"Published network info: IP={ip}")
            return True
            
        except Exception as e:
            self.logger.log(f"Error publishing network info: {e}")
            self.client = None  # Force reconnection on next attempt
            return False