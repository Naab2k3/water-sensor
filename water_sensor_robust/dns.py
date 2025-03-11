"""
DNS Client for W5500 Ethernet module
Compatible with MicroPython and Raspberry Pi Pico
"""

import socket
import struct
import random
import time

# DNS Query Types
DNS_QUERY_TYPE_A = 1      # IPv4 address record
DNS_QUERY_TYPE_AAAA = 28  # IPv6 address record
DNS_QUERY_TYPE_CNAME = 5  # Canonical name record
DNS_QUERY_TYPE_MX = 15    # Mail exchange record
DNS_QUERY_TYPE_NS = 2     # Name server record
DNS_QUERY_TYPE_TXT = 16   # Text record

# DNS Response Codes
DNS_RCODE_NO_ERROR = 0
DNS_RCODE_FORMAT_ERROR = 1
DNS_RCODE_SERVER_FAILURE = 2
DNS_RCODE_NAME_ERROR = 3
DNS_RCODE_NOT_IMPLEMENTED = 4
DNS_RCODE_REFUSED = 5

class DNSClient:
    def __init__(self, dns_server=None, timeout=5):
        """Initialize DNS client
        
        Args:
            dns_server: DNS server IP address (string). If None, uses '8.8.8.8' (Google DNS)
            timeout: Timeout for DNS queries in seconds
        """
        self.dns_server = dns_server or '8.8.8.8'
        self.timeout = timeout
        self.sock = None
        self.query_id = random.randint(0, 65535)
    
    def resolve(self, hostname, query_type=DNS_QUERY_TYPE_A):
        """Resolve hostname to IP address
        
        Args:
            hostname: Hostname to resolve
            query_type: DNS query type (default: A record)
            
        Returns:
            IP address as string, or None if resolution failed
        """
        try:
            # Create UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(self.timeout)
            
            # Generate new query ID
            self.query_id = random.randint(0, 65535)
            
            # Create DNS query packet
            packet = self._create_dns_query(hostname, query_type)
            
            # Send DNS query
            self.sock.sendto(packet, (self.dns_server, 53))
            
            # Receive DNS response
            response, _ = self.sock.recvfrom(512)
            
            # Parse DNS response
            ip_address = self._parse_dns_response(response, query_type)
            
            # Close socket
            self.sock.close()
            
            return ip_address
        except Exception as e:
            print(f"DNS resolution error: {e}")
            try:
                self.sock.close()
            except:
                pass
            return None
    
    def _create_dns_query(self, hostname, query_type):
        """Create DNS query packet
        
        Args:
            hostname: Hostname to query
            query_type: DNS query type
            
        Returns:
            DNS query packet as bytes
        """
        # DNS Header
        # ID: 2 bytes
        packet = struct.pack('>H', self.query_id)
        
        # Flags: 2 bytes
        # QR (1 bit): 0 for query
        # OPCODE (4 bits): 0 for standard query
        # AA (1 bit): 0 (not authoritative)
        # TC (1 bit): 0 (not truncated)
        # RD (1 bit): 1 (recursion desired)
        # RA (1 bit): 0 (recursion not available)
        # Z (3 bits): 0 (reserved)
        # RCODE (4 bits): 0 (no error)
        packet += struct.pack('>H', 0x0100)  # 0x0100 = 0000 0001 0000 0000
        
        # QDCOUNT: 1 question
        packet += struct.pack('>H', 1)
        
        # ANCOUNT: 0 answers
        packet += struct.pack('>H', 0)
        
        # NSCOUNT: 0 authority records
        packet += struct.pack('>H', 0)
        
        # ARCOUNT: 0 additional records
        packet += struct.pack('>H', 0)
        
        # Convert hostname to DNS format (length-prefixed labels)
        labels = hostname.split('.')
        for label in labels:
            label_len = len(label)
            packet += struct.pack('B', label_len)
            packet += label.encode('ascii')
        
        # Terminating zero length
        packet += struct.pack('B', 0)
        
        # QTYPE
        packet += struct.pack('>H', query_type)
        
        # QCLASS: 1 for IN (Internet)
        packet += struct.pack('>H', 1)
        
        return packet
    
    def _parse_dns_response(self, response, query_type):
        """Parse DNS response packet
        
        Args:
            response: DNS response packet as bytes
            query_type: DNS query type
            
        Returns:
            IP address as string, or None if parsing failed
        """
        try:
            # Check if response is too short
            if len(response) < 12:
                return None
            
            # Extract header fields
            header = struct.unpack('>HHHHHH', response[:12])
            
            # Check if ID matches
            if header[0] != self.query_id:
                return None
            
            # Check response code
            rcode = header[1] & 0x000F
            if rcode != DNS_RCODE_NO_ERROR:
                return None
            
            # Check if response has answers
            ancount = header[3]
            if ancount == 0:
                return None
            
            # Skip question section
            offset = 12
            
            # Skip QNAME
            while True:
                length = response[offset]
                offset += 1
                
                if length == 0:
                    break
                
                offset += length
            
            # Skip QTYPE and QCLASS
            offset += 4
            
            # Parse answer section
            for _ in range(ancount):
                # Check for compression pointer
                if (response[offset] & 0xC0) == 0xC0:
                    offset += 2  # Skip compression pointer
                else:
                    # Skip NAME
                    while True:
                        length = response[offset]
                        offset += 1
                        
                        if length == 0:
                            break
                        
                        offset += length
                
                # Get TYPE, CLASS, TTL, RDLENGTH
                ans_type, ans_class, ttl, rdlength = struct.unpack('>HHIH', response[offset:offset+10])
                offset += 10
                
                # Check if this is the record type we're looking for
                if ans_type == query_type and ans_class == 1:  # CLASS IN
                    if query_type == DNS_QUERY_TYPE_A:
                        # IPv4 address (4 bytes)
                        if rdlength == 4:
                            return f"{response[offset]}.{response[offset+1]}.{response[offset+2]}.{response[offset+3]}"
                    elif query_type == DNS_QUERY_TYPE_AAAA:
                        # IPv6 address (16 bytes)
                        if rdlength == 16:
                            ipv6_parts = struct.unpack('>8H', response[offset:offset+16])
                            return ':'.join(f'{part:04x}' for part in ipv6_parts)
                
                # Skip RDATA
                offset += rdlength
            
            return None
        except Exception as e:
            print(f"Error parsing DNS response: {e}")
            return None
    
    def set_dns_server(self, dns_server):
        """Set DNS server IP address
        
        Args:
            dns_server: DNS server IP address (string)
        """
        self.dns_server = dns_server 