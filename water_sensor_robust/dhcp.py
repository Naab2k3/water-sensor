"""
DHCP Client for W5500 Ethernet module
Compatible with MicroPython and Raspberry Pi Pico
"""

import time
import random
import socket
import struct

# DHCP Message Type
DHCPDISCOVER = 1
DHCPOFFER = 2
DHCPREQUEST = 3
DHCPDECLINE = 4
DHCPACK = 5
DHCPNAK = 6
DHCPRELEASE = 7
DHCPINFORM = 8

# DHCP Options
DHCP_OPT_SUBNET_MASK = 1
DHCP_OPT_ROUTER = 3
DHCP_OPT_DNS_SERVER = 6
DHCP_OPT_HOSTNAME = 12
DHCP_OPT_REQUESTED_IP = 50
DHCP_OPT_LEASE_TIME = 51
DHCP_OPT_MSG_TYPE = 53
DHCP_OPT_SERVER_ID = 54
DHCP_OPT_PARAM_REQUEST = 55
DHCP_OPT_END = 255

# DHCP States
DHCP_STATE_INIT = 0
DHCP_STATE_SELECTING = 1
DHCP_STATE_REQUESTING = 2
DHCP_STATE_BOUND = 3
DHCP_STATE_RENEWING = 4
DHCP_STATE_REBINDING = 5

class DHCP:
    def __init__(self, w5500, hostname=None, timeout=10):
        self.w5500 = w5500
        self.hostname = hostname or f"pico-{random.randint(1000, 9999)}"
        self.timeout = timeout
        self.xid = random.randint(1, 0xFFFFFFFF)  # Transaction ID
        self.server_ip = None
        self.offered_ip = None
        self.subnet_mask = None
        self.router_ip = None
        self.dns_server = None
        self.lease_time = 0
        self.renew_time = 0
        self.rebind_time = 0
        self.last_request_time = 0
        self.state = DHCP_STATE_INIT
        self.sock = None
    
    def request(self):
        """Request IP address via DHCP"""
        try:
            # Create UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(1)  # 1 second timeout for receiving
            
            # Bind to DHCP client port
            self.sock.bind(('0.0.0.0', 68))
            
            # Set socket to broadcast
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # DHCP Discover
            if not self._send_discover():
                print("DHCP Discover failed")
                self.sock.close()
                return False
            
            # DHCP Offer
            if not self._receive_offer():
                print("No DHCP Offer received")
                self.sock.close()
                return False
            
            # DHCP Request
            if not self._send_request():
                print("DHCP Request failed")
                self.sock.close()
                return False
            
            # DHCP Ack
            if not self._receive_ack():
                print("No DHCP Ack received")
                self.sock.close()
                return False
            
            # Configure network with received parameters
            self._configure_network()
            
            # Close socket
            self.sock.close()
            
            # Set state to bound
            self.state = DHCP_STATE_BOUND
            self.last_request_time = time.time()
            
            return True
        except Exception as e:
            print(f"DHCP request error: {e}")
            try:
                self.sock.close()
            except:
                pass
            return False
    
    def renew(self):
        """Renew DHCP lease"""
        if self.state != DHCP_STATE_BOUND and self.state != DHCP_STATE_RENEWING:
            return False
        
        try:
            # Create UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(1)  # 1 second timeout for receiving
            
            # Bind to DHCP client port
            self.sock.bind(('0.0.0.0', 68))
            
            # Set state to renewing
            self.state = DHCP_STATE_RENEWING
            
            # Generate new transaction ID
            self.xid = random.randint(1, 0xFFFFFFFF)
            
            # Send DHCP Request to renew
            if not self._send_renew_request():
                print("DHCP Renew Request failed")
                self.sock.close()
                return False
            
            # Receive DHCP Ack
            if not self._receive_ack():
                print("No DHCP Ack received for renewal")
                self.sock.close()
                return False
            
            # Configure network with received parameters
            self._configure_network()
            
            # Close socket
            self.sock.close()
            
            # Set state to bound
            self.state = DHCP_STATE_BOUND
            self.last_request_time = time.time()
            
            return True
        except Exception as e:
            print(f"DHCP renew error: {e}")
            try:
                self.sock.close()
            except:
                pass
            return False
    
    def _send_discover(self):
        """Send DHCP Discover message"""
        try:
            # Create DHCP Discover packet
            packet = bytearray(548)  # DHCP packet size
            
            # BOOTP header
            packet[0] = 0x01  # Message type: Boot Request
            packet[1] = 0x01  # Hardware type: Ethernet
            packet[2] = 0x06  # Hardware address length: 6 bytes
            packet[3] = 0x00  # Hops: 0
            
            # Transaction ID
            packet[4:8] = struct.pack(">I", self.xid)
            
            # Seconds elapsed: 0
            packet[8:10] = b'\x00\x00'
            
            # Bootp flags: 0x8000 (broadcast)
            packet[10:12] = b'\x80\x00'
            
            # Client IP address: 0.0.0.0
            packet[12:16] = b'\x00\x00\x00\x00'
            
            # Your IP address: 0.0.0.0
            packet[16:20] = b'\x00\x00\x00\x00'
            
            # Next server IP address: 0.0.0.0
            packet[20:24] = b'\x00\x00\x00\x00'
            
            # Relay agent IP address: 0.0.0.0
            packet[24:28] = b'\x00\x00\x00\x00'
            
            # Client MAC address
            mac = self.w5500.get_mac_address()
            packet[28:34] = mac
            
            # Client hardware address padding
            packet[34:44] = b'\x00' * 10
            
            # Server host name
            packet[44:108] = b'\x00' * 64
            
            # Boot file name
            packet[108:236] = b'\x00' * 128
            
            # Magic cookie
            packet[236:240] = b'\x63\x82\x53\x63'
            
            # DHCP Message Type: DISCOVER
            packet[240:243] = bytes([53, 1, DHCPDISCOVER])
            
            # Client Identifier
            packet[243:251] = bytes([61, 7, 1]) + mac
            
            # Host Name
            hostname_bytes = self.hostname.encode('ascii')
            hostname_len = len(hostname_bytes)
            packet[251:253+hostname_len] = bytes([12, hostname_len]) + hostname_bytes
            
            # Parameter Request List
            packet[253+hostname_len:262+hostname_len] = bytes([55, 4, 1, 3, 6, 15])
            
            # End Option
            packet[262+hostname_len] = 255
            
            # Send packet
            self.sock.sendto(packet, ('255.255.255.255', 67))
            
            return True
        except Exception as e:
            print(f"Error sending DHCP Discover: {e}")
            return False
    
    def _receive_offer(self):
        """Receive DHCP Offer message"""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                data, addr = self.sock.recvfrom(1024)
                
                # Check if this is a BOOTP response
                if data[0] != 0x02:  # Message type: Boot Reply
                    continue
                
                # Check transaction ID
                if data[4:8] != struct.pack(">I", self.xid):
                    continue
                
                # Check for DHCP magic cookie
                if data[236:240] != b'\x63\x82\x53\x63':
                    continue
                
                # Parse DHCP options
                i = 240
                msg_type = None
                
                while i < len(data):
                    if data[i] == DHCP_OPT_END:
                        break
                    
                    if i + 1 >= len(data):
                        break
                    
                    opt_len = data[i + 1]
                    
                    if i + 2 + opt_len > len(data):
                        break
                    
                    if data[i] == DHCP_OPT_MSG_TYPE and opt_len == 1:
                        msg_type = data[i + 2]
                    elif data[i] == DHCP_OPT_SERVER_ID and opt_len == 4:
                        self.server_ip = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_SUBNET_MASK and opt_len == 4:
                        self.subnet_mask = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_ROUTER and opt_len >= 4:
                        self.router_ip = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_DNS_SERVER and opt_len >= 4:
                        self.dns_server = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_LEASE_TIME and opt_len == 4:
                        self.lease_time = struct.unpack(">I", data[i+2:i+6])[0]
                        self.renew_time = self.lease_time // 2
                        self.rebind_time = self.lease_time * 7 // 8
                    
                    i += 2 + opt_len
                
                # Check if this is a DHCP Offer
                if msg_type == DHCPOFFER:
                    # Get offered IP address
                    self.offered_ip = f"{data[16]}.{data[17]}.{data[18]}.{data[19]}"
                    
                    # Set state to requesting
                    self.state = DHCP_STATE_REQUESTING
                    
                    return True
            except socket.timeout:
                # Socket timeout, continue waiting
                pass
            except Exception as e:
                print(f"Error receiving DHCP Offer: {e}")
                return False
        
        return False
    
    def _send_request(self):
        """Send DHCP Request message"""
        try:
            # Create DHCP Request packet
            packet = bytearray(548)  # DHCP packet size
            
            # BOOTP header
            packet[0] = 0x01  # Message type: Boot Request
            packet[1] = 0x01  # Hardware type: Ethernet
            packet[2] = 0x06  # Hardware address length: 6 bytes
            packet[3] = 0x00  # Hops: 0
            
            # Transaction ID
            packet[4:8] = struct.pack(">I", self.xid)
            
            # Seconds elapsed: 0
            packet[8:10] = b'\x00\x00'
            
            # Bootp flags: 0x8000 (broadcast)
            packet[10:12] = b'\x80\x00'
            
            # Client IP address: 0.0.0.0
            packet[12:16] = b'\x00\x00\x00\x00'
            
            # Your IP address: 0.0.0.0
            packet[16:20] = b'\x00\x00\x00\x00'
            
            # Next server IP address: 0.0.0.0
            packet[20:24] = b'\x00\x00\x00\x00'
            
            # Relay agent IP address: 0.0.0.0
            packet[24:28] = b'\x00\x00\x00\x00'
            
            # Client MAC address
            mac = self.w5500.get_mac_address()
            packet[28:34] = mac
            
            # Client hardware address padding
            packet[34:44] = b'\x00' * 10
            
            # Server host name
            packet[44:108] = b'\x00' * 64
            
            # Boot file name
            packet[108:236] = b'\x00' * 128
            
            # Magic cookie
            packet[236:240] = b'\x63\x82\x53\x63'
            
            # DHCP Message Type: REQUEST
            packet[240:243] = bytes([53, 1, DHCPREQUEST])
            
            # Client Identifier
            packet[243:251] = bytes([61, 7, 1]) + mac
            
            # Requested IP Address
            ip_parts = [int(x) for x in self.offered_ip.split('.')]
            packet[251:257] = bytes([50, 4, ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3]])
            
            # Server Identifier
            server_ip_parts = [int(x) for x in self.server_ip.split('.')]
            packet[257:263] = bytes([54, 4, server_ip_parts[0], server_ip_parts[1], server_ip_parts[2], server_ip_parts[3]])
            
            # Host Name
            hostname_bytes = self.hostname.encode('ascii')
            hostname_len = len(hostname_bytes)
            packet[263:265+hostname_len] = bytes([12, hostname_len]) + hostname_bytes
            
            # Parameter Request List
            packet[265+hostname_len:274+hostname_len] = bytes([55, 4, 1, 3, 6, 15])
            
            # End Option
            packet[274+hostname_len] = 255
            
            # Send packet
            self.sock.sendto(packet, ('255.255.255.255', 67))
            
            return True
        except Exception as e:
            print(f"Error sending DHCP Request: {e}")
            return False
    
    def _send_renew_request(self):
        """Send DHCP Request message for renewal"""
        try:
            # Create DHCP Request packet
            packet = bytearray(548)  # DHCP packet size
            
            # BOOTP header
            packet[0] = 0x01  # Message type: Boot Request
            packet[1] = 0x01  # Hardware type: Ethernet
            packet[2] = 0x06  # Hardware address length: 6 bytes
            packet[3] = 0x00  # Hops: 0
            
            # Transaction ID
            packet[4:8] = struct.pack(">I", self.xid)
            
            # Seconds elapsed: 0
            packet[8:10] = b'\x00\x00'
            
            # Bootp flags: 0x0000 (unicast)
            packet[10:12] = b'\x00\x00'
            
            # Client IP address: current IP
            ip_parts = [int(x) for x in self.offered_ip.split('.')]
            packet[12:16] = bytes(ip_parts)
            
            # Your IP address: 0.0.0.0
            packet[16:20] = b'\x00\x00\x00\x00'
            
            # Next server IP address: 0.0.0.0
            packet[20:24] = b'\x00\x00\x00\x00'
            
            # Relay agent IP address: 0.0.0.0
            packet[24:28] = b'\x00\x00\x00\x00'
            
            # Client MAC address
            mac = self.w5500.get_mac_address()
            packet[28:34] = mac
            
            # Client hardware address padding
            packet[34:44] = b'\x00' * 10
            
            # Server host name
            packet[44:108] = b'\x00' * 64
            
            # Boot file name
            packet[108:236] = b'\x00' * 128
            
            # Magic cookie
            packet[236:240] = b'\x63\x82\x53\x63'
            
            # DHCP Message Type: REQUEST
            packet[240:243] = bytes([53, 1, DHCPREQUEST])
            
            # Client Identifier
            packet[243:251] = bytes([61, 7, 1]) + mac
            
            # Host Name
            hostname_bytes = self.hostname.encode('ascii')
            hostname_len = len(hostname_bytes)
            packet[251:253+hostname_len] = bytes([12, hostname_len]) + hostname_bytes
            
            # Parameter Request List
            packet[253+hostname_len:262+hostname_len] = bytes([55, 4, 1, 3, 6, 15])
            
            # End Option
            packet[262+hostname_len] = 255
            
            # Send packet to DHCP server
            server_ip_parts = [int(x) for x in self.server_ip.split('.')]
            server_ip = f"{server_ip_parts[0]}.{server_ip_parts[1]}.{server_ip_parts[2]}.{server_ip_parts[3]}"
            self.sock.sendto(packet, (server_ip, 67))
            
            return True
        except Exception as e:
            print(f"Error sending DHCP Renew Request: {e}")
            return False
    
    def _receive_ack(self):
        """Receive DHCP Ack message"""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                data, addr = self.sock.recvfrom(1024)
                
                # Check if this is a BOOTP response
                if data[0] != 0x02:  # Message type: Boot Reply
                    continue
                
                # Check transaction ID
                if data[4:8] != struct.pack(">I", self.xid):
                    continue
                
                # Check for DHCP magic cookie
                if data[236:240] != b'\x63\x82\x53\x63':
                    continue
                
                # Parse DHCP options
                i = 240
                msg_type = None
                
                while i < len(data):
                    if data[i] == DHCP_OPT_END:
                        break
                    
                    if i + 1 >= len(data):
                        break
                    
                    opt_len = data[i + 1]
                    
                    if i + 2 + opt_len > len(data):
                        break
                    
                    if data[i] == DHCP_OPT_MSG_TYPE and opt_len == 1:
                        msg_type = data[i + 2]
                    elif data[i] == DHCP_OPT_SERVER_ID and opt_len == 4:
                        self.server_ip = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_SUBNET_MASK and opt_len == 4:
                        self.subnet_mask = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_ROUTER and opt_len >= 4:
                        self.router_ip = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_DNS_SERVER and opt_len >= 4:
                        self.dns_server = f"{data[i+2]}.{data[i+3]}.{data[i+4]}.{data[i+5]}"
                    elif data[i] == DHCP_OPT_LEASE_TIME and opt_len == 4:
                        self.lease_time = struct.unpack(">I", data[i+2:i+6])[0]
                        self.renew_time = self.lease_time // 2
                        self.rebind_time = self.lease_time * 7 // 8
                    
                    i += 2 + opt_len
                
                # Check if this is a DHCP Ack
                if msg_type == DHCPACK:
                    # Get assigned IP address
                    self.offered_ip = f"{data[16]}.{data[17]}.{data[18]}.{data[19]}"
                    
                    return True
                elif msg_type == DHCPNAK:
                    # DHCP Nak received, restart DHCP process
                    self.state = DHCP_STATE_INIT
                    return False
            except socket.timeout:
                # Socket timeout, continue waiting
                pass
            except Exception as e:
                print(f"Error receiving DHCP Ack: {e}")
                return False
        
        return False
    
    def _configure_network(self):
        """Configure network with received DHCP parameters"""
        try:
            # Convert IP addresses to byte arrays
            ip = bytearray([int(x) for x in self.offered_ip.split('.')])
            subnet = bytearray([int(x) for x in self.subnet_mask.split('.')])
            gateway = bytearray([int(x) for x in self.router_ip.split('.')]) if self.router_ip else bytearray([0, 0, 0, 0])
            dns = bytearray([int(x) for x in self.dns_server.split('.')]) if self.dns_server else bytearray([0, 0, 0, 0])
            
            # Configure W5500
            self.w5500.begin(ip, subnet, gateway, dns)
            
            return True
        except Exception as e:
            print(f"Error configuring network: {e}")
            return False 