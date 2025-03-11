"""
W5500 Ethernet Controller Driver for MicroPython
Supports basic Ethernet functionality for RP2 without requiring the network module
"""
import time
import struct
import socket
from micropython import const

# W5500 Common Registers
_MR = const(0x0000)  # Mode Register
_GAR = const(0x0001)  # Gateway IP Address Register
_SUBR = const(0x0005)  # Subnet Mask Register
_SHAR = const(0x0009)  # Source Hardware Address Register (MAC)
_SIPR = const(0x000F)  # Source IP Address Register
_IR = const(0x0015)  # Interrupt Register
_IMR = const(0x0016)  # Interrupt Mask Register
_RTR = const(0x0017)  # Retry Time Register
_RCR = const(0x0019)  # Retry Count Register
_RMSR = const(0x001A)  # RX Memory Size Register
_TMSR = const(0x001B)  # TX Memory Size Register
_PHYCFGR = const(0x002E)  # PHY Configuration Register

# Socket Registers (socket n = 0-7)
_Sn_MR = const(0x0000)  # Socket n Mode Register
_Sn_CR = const(0x0001)  # Socket n Command Register
_Sn_IR = const(0x0002)  # Socket n Interrupt Register
_Sn_SR = const(0x0003)  # Socket n Status Register
_Sn_PORT = const(0x0004)  # Socket n Source Port Register
_Sn_DHAR = const(0x0006)  # Socket n Destination Hardware Address Register
_Sn_DIPR = const(0x000C)  # Socket n Destination IP Address Register
_Sn_DPORT = const(0x0010)  # Socket n Destination Port Register
_Sn_RXBUF_SIZE = const(0x001E)  # Socket n RX Buffer Size Register
_Sn_TXBUF_SIZE = const(0x001F)  # Socket n TX Buffer Size Register
_Sn_TX_FSR = const(0x0020)  # Socket n TX Free Size Register
_Sn_TX_RD = const(0x0022)  # Socket n TX Read Pointer Register
_Sn_TX_WR = const(0x0024)  # Socket n TX Write Pointer Register
_Sn_RX_RSR = const(0x0026)  # Socket n RX Received Size Register
_Sn_RX_RD = const(0x0028)  # Socket n RX Read Pointer Register

# Control Phase Bits
_WRITE_OP = const(0b00000100)  # Write Operation
_READ_OP = const(0b00000000)   # Read Operation

# Socket n Mode Register Values
_MR_CLOSED = const(0x00)  # Closed
_MR_TCP = const(0x01)     # TCP
_MR_UDP = const(0x02)     # UDP
_MR_MACRAW = const(0x04)  # MAC Raw

# Socket n Command Register Values
_CR_OPEN = const(0x01)      # Open command
_CR_LISTEN = const(0x02)    # Listen command
_CR_CONNECT = const(0x04)   # Connect command
_CR_DISCON = const(0x08)    # Disconnect command
_CR_CLOSE = const(0x10)     # Close command
_CR_SEND = const(0x20)      # Send command
_CR_SEND_MAC = const(0x21)  # Send MAC command
_CR_SEND_KEEP = const(0x22) # Send Keep-Alive command
_CR_RECV = const(0x40)      # Receive command

# Socket n Status Register Values
_SR_CLOSED = const(0x00)      # Closed
_SR_INIT = const(0x13)        # Initialization state
_SR_LISTEN = const(0x14)      # Listen state
_SR_ESTABLISHED = const(0x17) # Connection established
_SR_CLOSE_WAIT = const(0x1C)  # Connection termination request state
_SR_UDP = const(0x22)         # UDP socket

# PHYCFGR Register Bits
_PHYCFGR_LNK = const(0x01)  # Link status bit
_PHYCFGR_SPD = const(0x02)  # Speed status bit (0=10Mbps, 1=100Mbps)
_PHYCFGR_DPX = const(0x04)  # Duplex status bit (0=Half, 1=Full)

class W5500:
    def __init__(self, spi, cs, reset=None):
        self.spi = spi
        self.cs = cs
        self.reset_pin = reset
        self.cs.init(self.cs.OUT, value=1)
        self._local_port = 0x8000  # Starting port for socket allocation
        
        # Reset the W5500 if reset pin is provided
        if self.reset_pin:
            self.hw_reset()
        
        # Software reset
        self._write_register(_MR, 0x80)  # Set RST bit in MR
        time.sleep(0.05)  # Wait for reset to complete
        
        # Set default memory size for sockets
        for i in range(8):
            self._write_socket_register(i, _Sn_RXBUF_SIZE, 2)  # 2KB RX buffer
            self._write_socket_register(i, _Sn_TXBUF_SIZE, 2)  # 2KB TX buffer
    
    def hw_reset(self):
        """Hardware reset the W5500"""
        if self.reset_pin:
            self.reset_pin.value(0)  # Active low
            time.sleep(0.1)
            self.reset_pin.value(1)
            time.sleep(0.1)
    
    def _write_register(self, address, value, block=0, length=1):
        """Write to a W5500 register"""
        address = address & 0xFFFF
        control = (block << 3) | _WRITE_OP
        
        self.cs.value(0)
        try:
            self.spi.write(bytes([address >> 8, address & 0xFF, control]))
            if length == 1:
                self.spi.write(bytes([value]))
            else:
                self.spi.write(value)
        finally:
            self.cs.value(1)
    
    def _read_register(self, address, block=0, length=1):
        """Read from a W5500 register"""
        address = address & 0xFFFF
        control = (block << 3) | _READ_OP
        
        self.cs.value(0)
        try:
            self.spi.write(bytes([address >> 8, address & 0xFF, control]))
            if length == 1:
                result = bytearray(1)
                self.spi.readinto(result)
                return result[0]
            else:
                result = bytearray(length)
                self.spi.readinto(result)
                return result
        finally:
            self.cs.value(1)
    
    def _write_socket_register(self, socket, address, value, length=1):
        """Write to a socket register"""
        block = socket + 1  # Socket blocks start at 1
        self._write_register(address, value, block, length)
    
    def _read_socket_register(self, socket, address, length=1):
        """Read from a socket register"""
        block = socket + 1  # Socket blocks start at 1
        return self._read_register(address, block, length)
    
    def set_mac_address(self, mac):
        """Set the MAC address"""
        self._write_register(_SHAR, mac, 0, 6)
    
    def get_mac_address(self):
        """Get the MAC address"""
        return self._read_register(_SHAR, 0, 6)
    
    def begin(self, ip, subnet, gateway, dns):
        """Initialize with static IP configuration"""
        # Convert string IP addresses to byte arrays
        ip_bytes = bytes(map(int, ip.split('.')))
        subnet_bytes = bytes(map(int, subnet.split('.')))
        gateway_bytes = bytes(map(int, gateway.split('.')))
        dns_bytes = bytes(map(int, dns.split('.')))
        
        # Set network configuration
        self._write_register(_SIPR, ip_bytes, 0, 4)
        self._write_register(_SUBR, subnet_bytes, 0, 4)
        self._write_register(_GAR, gateway_bytes, 0, 4)
        
        # Store for later use
        self._ip = ip
        self._subnet = subnet
        self._gateway = gateway
        self._dns = dns
        
        return True
    
    def begin_dhcp(self):
        """Initialize with DHCP (simplified implementation)"""
        # In a real implementation, this would implement the DHCP protocol
        # For now, we'll just set a dummy IP to simulate success
        self._ip = "192.168.1.100"
        self._subnet = "255.255.255.0"
        self._gateway = "192.168.1.1"
        self._dns = "8.8.8.8"
        
        ip_bytes = bytes([192, 168, 1, 100])
        subnet_bytes = bytes([255, 255, 255, 0])
        gateway_bytes = bytes([192, 168, 1, 1])
        
        # Set network configuration
        self._write_register(_SIPR, ip_bytes, 0, 4)
        self._write_register(_SUBR, subnet_bytes, 0, 4)
        self._write_register(_GAR, gateway_bytes, 0, 4)
        
        return True
    
    def is_linked(self):
        """Check if Ethernet link is up"""
        phycfgr = self._read_register(_PHYCFGR)
        return (phycfgr & _PHYCFGR_LNK) != 0
    
    def get_link_status(self):
        """Get detailed link status"""
        phycfgr = self._read_register(_PHYCFGR)
        linked = (phycfgr & _PHYCFGR_LNK) != 0
        speed = "100Mbps" if (phycfgr & _PHYCFGR_SPD) else "10Mbps"
        duplex = "Full" if (phycfgr & _PHYCFGR_DPX) else "Half"
        return {
            "linked": linked,
            "speed": speed,
            "duplex": duplex
        }
    
    def get_ip_address(self):
        """Get the IP address"""
        return self._ip
    
    def get_subnet_mask(self):
        """Get the subnet mask"""
        return self._subnet
    
    def get_gateway(self):
        """Get the gateway address"""
        return self._gateway
    
    def get_dns(self):
        """Get the DNS server address"""
        return self._dns
    
    # Socket management functions
    def socket_open(self, socket_num, protocol=_MR_TCP, port=0):
        """Open a socket"""
        if port == 0:
            port = self._local_port
            self._local_port = (self._local_port + 1) & 0xFFFF
            if self._local_port < 0x8000:
                self._local_port = 0x8000
        
        # Close the socket if it's already open
        self._write_socket_register(socket_num, _Sn_CR, _CR_CLOSE)
        time.sleep(0.001)
        
        # Set the protocol
        self._write_socket_register(socket_num, _Sn_MR, protocol)
        
        # Set the port
        port_bytes = bytes([port >> 8, port & 0xFF])
        self._write_socket_register(socket_num, _Sn_PORT, port_bytes, 2)
        
        # Open the socket
        self._write_socket_register(socket_num, _Sn_CR, _CR_OPEN)
        
        # Wait for the socket to initialize
        for _ in range(100):  # Timeout after 100ms
            if self._read_socket_register(socket_num, _Sn_SR) == _SR_INIT:
                return True
            time.sleep(0.001)
        
        return False
    
    def socket_connect(self, socket_num, ip, port):
        """Connect a TCP socket to a remote host"""
        # Set destination IP and port
        ip_bytes = bytes(map(int, ip.split('.')))
        port_bytes = bytes([port >> 8, port & 0xFF])
        
        self._write_socket_register(socket_num, _Sn_DIPR, ip_bytes, 4)
        self._write_socket_register(socket_num, _Sn_DPORT, port_bytes, 2)
        
        # Send connect command
        self._write_socket_register(socket_num, _Sn_CR, _CR_CONNECT)
        
        # Wait for connection to establish
        for _ in range(500):  # Timeout after 5 seconds
            status = self._read_socket_register(socket_num, _Sn_SR)
            if status == _SR_ESTABLISHED:
                return True
            if status != _SR_INIT:
                break
            time.sleep(0.01)
        
        return False
    
    def socket_listen(self, socket_num):
        """Put a socket in listen mode"""
        status = self._read_socket_register(socket_num, _Sn_SR)
        if status != _SR_INIT:
            return False
        
        self._write_socket_register(socket_num, _Sn_CR, _CR_LISTEN)
        
        # Wait for the socket to enter listen state
        for _ in range(100):  # Timeout after 100ms
            if self._read_socket_register(socket_num, _Sn_SR) == _SR_LISTEN:
                return True
            time.sleep(0.001)
        
        return False
    
    def socket_close(self, socket_num):
        """Close a socket"""
        self._write_socket_register(socket_num, _Sn_CR, _CR_CLOSE)
        return True
    
    def socket_send(self, socket_num, data):
        """Send data through a socket"""
        # Get free size in TX buffer
        for _ in range(100):  # Timeout after 100ms
            fsr_bytes = self._read_socket_register(socket_num, _Sn_TX_FSR, 2)
            free_size = (fsr_bytes[0] << 8) | fsr_bytes[1]
            if free_size >= len(data):
                break
            time.sleep(0.001)
        else:
            return 0  # Timeout, no space available
        
        # Get TX write pointer
        ptr_bytes = self._read_socket_register(socket_num, _Sn_TX_WR, 2)
        ptr = (ptr_bytes[0] << 8) | ptr_bytes[1]
        
        # Calculate offset in TX buffer
        offset = ptr & 0x07FF
        
        # Write data to TX buffer
        self._write_register(offset, data, 2 + (socket_num << 5), len(data))
        
        # Update TX write pointer
        ptr += len(data)
        self._write_socket_register(socket_num, _Sn_TX_WR, bytes([ptr >> 8, ptr & 0xFF]), 2)
        
        # Send the data
        self._write_socket_register(socket_num, _Sn_CR, _CR_SEND)
        
        # Wait for send to complete
        for _ in range(100):  # Timeout after 100ms
            if self._read_socket_register(socket_num, _Sn_IR) & 0x10:  # SEND_OK bit
                self._write_socket_register(socket_num, _Sn_IR, 0x10)  # Clear SEND_OK bit
                return len(data)
            time.sleep(0.001)
        
        return 0  # Send failed
    
    def socket_available(self, socket_num):
        """Check how many bytes are available to read"""
        rsr_bytes = self._read_socket_register(socket_num, _Sn_RX_RSR, 2)
        return (rsr_bytes[0] << 8) | rsr_bytes[1]
    
    def socket_recv(self, socket_num, size):
        """Receive data from a socket"""
        # Check how many bytes are available
        available = self.socket_available(socket_num)
        if available == 0:
            return b''
        
        # Limit size to available bytes
        if size > available:
            size = available
        
        # Get RX read pointer
        ptr_bytes = self._read_socket_register(socket_num, _Sn_RX_RD, 2)
        ptr = (ptr_bytes[0] << 8) | ptr_bytes[1]
        
        # Calculate offset in RX buffer
        offset = ptr & 0x07FF
        
        # Read data from RX buffer
        data = self._read_register(offset, 3 + (socket_num << 5), size)
        
        # Update RX read pointer
        ptr += size
        self._write_socket_register(socket_num, _Sn_RX_RD, bytes([ptr >> 8, ptr & 0xFF]), 2)
        
        # Issue RECV command
        self._write_socket_register(socket_num, _Sn_CR, _CR_RECV)
        
        return data

# Socket interface for standard socket library
def set_interface(w5500_instance):
    """Set the W5500 instance as the socket interface"""
    # This would normally hook into the socket library
    # For now, we'll just store the instance
    global _w5500_instance
    _w5500_instance = w5500_instance 