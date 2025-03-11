import machine
import time
import json
import os
import socket
import random
import ubinascii

class Logger:
    def __init__(self, log_file=None):
        self.log_file = log_file
    
    def log(self, message):
        """Log a message to console and optionally to a file"""
        timestamp = time.localtime()
        time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            timestamp[0], timestamp[1], timestamp[2],
            timestamp[3], timestamp[4], timestamp[5]
        )
        log_message = f"[{time_str}] {message}"
        print(log_message)
        
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(log_message + '\n')
            except:
                pass

class EthernetManager:
    def __init__(self):
        self.logger = Logger()
        self.w5500 = None
        self.initialized = False
        self.ip_address = None
        self.subnet_mask = None
        self.gateway = None
        self.dns = None
        self.mac_address = None
        self.config = None
        self.dhcp_client = None
        self.dns_client = None
        self.last_dhcp_time = 0
        self._load_config()
    
    def _load_config(self):
        """Load Ethernet configuration from config file"""
        try:
            # Tải cấu hình từ config.json
            from config import load_config
            main_config = load_config()
            if main_config and 'ethernet' in main_config:
                self.config = main_config['ethernet']
            else:
                # Cấu hình mặc định
                self.config = {
                    'spi_id': 0,
                    'spi_sck': 18,
                    'spi_mosi': 19,
                    'spi_miso': 16,
                    'cs_pin': 17,
                    'reset_pin': 20,
                    'use_dhcp': True,
                    'static_ip': {
                        'ip': '192.168.1.100',
                        'subnet': '255.255.255.0',
                        'gateway': '192.168.1.1',
                        'dns': '8.8.8.8'
                    }
                }
        except:
            # Cấu hình mặc định nếu không đọc được
            self.config = {
                'spi_id': 0,
                'spi_sck': 18,
                'spi_mosi': 19,
                'spi_miso': 16,
                'cs_pin': 17,
                'reset_pin': 20,
                'use_dhcp': True,
                'static_ip': {
                    'ip': '192.168.1.100',
                    'subnet': '255.255.255.0',
                    'gateway': '192.168.1.1',
                    'dns': '8.8.8.8'
                }
            }
    
    def initialize(self, watchdog=None):
        """Initialize Ethernet connection"""
        self.logger.log("Initializing Ethernet...")
        
        try:
            # Initialize SPI
            spi = machine.SPI(self.config['spi_id'],
                             baudrate=10_000_000,
                             polarity=0,
                             phase=0,
                             bits=8,
                             firstbit=machine.SPI.MSB,
                             sck=machine.Pin(self.config['spi_sck']),
                             mosi=machine.Pin(self.config['spi_mosi']),
                             miso=machine.Pin(self.config['spi_miso']))
            
            # Initialize CS and Reset pins
            cs = machine.Pin(self.config['cs_pin'], machine.Pin.OUT)
            cs.value(1)  # Deselect chip initially
            
            reset_pin = machine.Pin(self.config['reset_pin'], machine.Pin.OUT)
            
            # Import W5500 module
            import w5500
            
            # Initialize W5500
            self.w5500 = w5500.W5500(spi, cs, reset_pin)
            
            # Generate MAC address if needed
            self.mac_address = self._generate_mac_address()
            self.w5500.set_mac_address(self.mac_address)
            
            self.logger.log(f"MAC Address: {':'.join([f'{b:02X}' for b in self.mac_address])}")
            
            # Wait for physical link
            timeout = 10  # seconds
            start_time = time.time()
            
            self.logger.log("Waiting for Ethernet link...")
            
            while not self.w5500.is_linked():
                if time.time() - start_time > timeout:
                    self.logger.log("Ethernet connection timeout")
                    return False
                    
                if watchdog:
                    watchdog.feed()
                    
                time.sleep(0.5)
            
            # Configure network
            if self.config['use_dhcp']:
                # Use DHCP
                self.logger.log("Using DHCP...")
                
                # Import DHCP client
                import dhcp
                
                # Create DHCP client
                hostname = f"pico-{ubinascii.hexlify(machine.unique_id()).decode()[-6:]}"
                self.dhcp_client = dhcp.DHCP(self.w5500, hostname=hostname, timeout=10)
                
                # Request IP address via DHCP
                if self.dhcp_client.request():
                    self.logger.log("DHCP configuration successful")
                    self.last_dhcp_time = time.time()
                else:
                    self.logger.log("DHCP failed, using static IP")
                    # Fall back to static IP
                    static_ip = self.config['static_ip']
                    ip = bytearray([int(x) for x in static_ip['ip'].split('.')])
                    subnet = bytearray([int(x) for x in static_ip['subnet'].split('.')])
                    gateway = bytearray([int(x) for x in static_ip['gateway'].split('.')])
                    dns = bytearray([int(x) for x in static_ip['dns'].split('.')])
                    
                    self.w5500.begin(ip, subnet, gateway, dns)
            else:
                # Use static IP
                self.logger.log("Using static IP...")
                
                static_ip = self.config['static_ip']
                ip = bytearray([int(x) for x in static_ip['ip'].split('.')])
                subnet = bytearray([int(x) for x in static_ip['subnet'].split('.')])
                gateway = bytearray([int(x) for x in static_ip['gateway'].split('.')])
                dns = bytearray([int(x) for x in static_ip['dns'].split('.')])
                
                self.w5500.begin(ip, subnet, gateway, dns)
            
            # Get network configuration
            self.ip_address = self.w5500.get_ip_address()
            self.subnet_mask = self.w5500.get_subnet_mask()
            self.gateway = self.w5500.get_gateway()
            self.dns = self.w5500.get_dns()
            
            self.logger.log(f"Ethernet connected. IP: {self.ip_address}, Subnet: {self.subnet_mask}, Gateway: {self.gateway}, DNS: {self.dns}")
            
            # Initialize socket library with W5500
            socket.set_interface(self.w5500)
            
            # Initialize DNS client
            import dns
            self.dns_client = dns.DNSClient(dns_server=self.dns)
            
            self.initialized = True
            return True
            
        except Exception as e:
            self.logger.log(f"Error initializing Ethernet: {e}")
            return False
    
    def _generate_mac_address(self):
        """Generate a MAC address based on the chip ID"""
        try:
            # Get unique ID from the RP2 chip
            id = ubinascii.hexlify(machine.unique_id()).decode()
            
            # Create a MAC address with a locally administered bit
            # First byte: 0x02 to indicate locally administered address
            mac = bytearray(6)
            mac[0] = 0x02  # Locally administered address
            
            # Use chip ID for remaining bytes
            for i in range(1, 6):
                if len(id) >= i*2:
                    mac[i] = int(id[(i-1)*2:i*2], 16)
                else:
                    mac[i] = random.randint(0, 255)
            
            return mac
        except:
            # Fallback to a random MAC if there's an error
            mac = bytearray(6)
            mac[0] = 0x02  # Locally administered address
            for i in range(1, 6):
                mac[i] = random.randint(0, 255)
            return mac
    
    def is_connected(self):
        """Check if Ethernet is connected"""
        if not self.initialized or not self.w5500:
            return False
        return self.w5500.is_linked()
    
    def get_ip_address(self):
        """Get the current IP address"""
        return self.ip_address
    
    def get_network_info(self):
        """Get network information"""
        return {
            'ip': self.ip_address,
            'subnet': self.subnet_mask,
            'gateway': self.gateway,
            'dns': self.dns,
            'mac': ':'.join([f'{b:02X}' for b in self.mac_address]) if self.mac_address else None,
            'connected': self.is_connected(),
            'dhcp_enabled': self.config['use_dhcp'],
            'dhcp_lease_time': self.dhcp_client.lease_time if self.dhcp_client else 0
        }
    
    def renew_dhcp(self):
        """Renew DHCP lease"""
        if not self.initialized or not self.w5500 or not self.dhcp_client:
            return False
        
        if not self.config['use_dhcp']:
            return False
        
        try:
            self.logger.log("Renewing DHCP lease...")
            
            if self.dhcp_client.renew():
                # Update network configuration
                self.ip_address = self.w5500.get_ip_address()
                self.subnet_mask = self.w5500.get_subnet_mask()
                self.gateway = self.w5500.get_gateway()
                self.dns = self.w5500.get_dns()
                
                # Update DNS client with new DNS server
                if self.dns_client:
                    self.dns_client.set_dns_server(self.dns)
                
                self.logger.log(f"DHCP renewed. IP: {self.ip_address}")
                self.last_dhcp_time = time.time()
                
                return True
            else:
                self.logger.log("DHCP renewal failed")
                return False
        except Exception as e:
            self.logger.log(f"Error renewing DHCP: {e}")
            return False
    
    def check_dhcp_lease(self):
        """Check if DHCP lease needs renewal"""
        if not self.initialized or not self.w5500 or not self.dhcp_client:
            return False
        
        if not self.config['use_dhcp']:
            return False
        
        # Check if it's time to renew DHCP lease
        # Typically renew at 50% of lease time
        if self.dhcp_client.lease_time > 0:
            elapsed = time.time() - self.last_dhcp_time
            if elapsed > (self.dhcp_client.renew_time):
                return self.renew_dhcp()
        
        return True
    
    def resolve_hostname(self, hostname):
        """Resolve hostname to IP address using DNS"""
        if not self.initialized or not self.dns_client:
            return None
        
        try:
            self.logger.log(f"Resolving hostname: {hostname}")
            ip = self.dns_client.resolve(hostname)
            if ip:
                self.logger.log(f"Resolved {hostname} to {ip}")
            else:
                self.logger.log(f"Failed to resolve {hostname}")
            return ip
        except Exception as e:
            self.logger.log(f"Error resolving hostname: {e}")
            return None
    
    def test_internet_connection(self, test_host="8.8.8.8", port=53, timeout=5):
        """Test internet connectivity by connecting to a known host"""
        if not self.initialized or not self.w5500:
            return False
        
        try:
            self.logger.log(f"Testing internet connection to {test_host}:{port}")
            
            # Create socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            
            # Connect to test host
            s.connect((test_host, port))
            
            # Close socket
            s.close()
            
            self.logger.log("Internet connection test successful")
            return True
        except Exception as e:
            self.logger.log(f"Internet connection test failed: {e}")
            return False
    
    def set_logger(self, logger):
        """Set the logger"""
        self.logger = logger 