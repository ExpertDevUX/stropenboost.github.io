"""
RTMP Protocol Utilities for OBS, vMix, and other streaming software compatibility
"""
import struct
import logging
from typing import Dict, Any, Optional, Tuple

class AMF0:
    """AMF0 (Action Message Format) encoding/decoding for RTMP compatibility"""
    
    # AMF0 data types
    NUMBER = 0x00
    BOOLEAN = 0x01
    STRING = 0x02
    OBJECT = 0x03
    NULL = 0x05
    UNDEFINED = 0x06
    REFERENCE = 0x07
    ARRAY = 0x08
    OBJECT_END = 0x09
    STRICT_ARRAY = 0x0A
    DATE = 0x0B
    LONG_STRING = 0x0C
    
    @staticmethod
    def encode_string(value: str) -> bytes:
        """Encode string in AMF0 format"""
        data = value.encode('utf-8')
        return struct.pack('>BH', AMF0.STRING, len(data)) + data
    
    @staticmethod
    def encode_number(value: float) -> bytes:
        """Encode number in AMF0 format"""
        return struct.pack('>Bd', AMF0.NUMBER, value)
    
    @staticmethod
    def encode_boolean(value: bool) -> bytes:
        """Encode boolean in AMF0 format"""
        return struct.pack('>BB', AMF0.BOOLEAN, 1 if value else 0)
    
    @staticmethod
    def encode_null() -> bytes:
        """Encode null in AMF0 format"""
        return struct.pack('>B', AMF0.NULL)
    
    @staticmethod
    def encode_object(obj: Dict[str, Any]) -> bytes:
        """Encode object in AMF0 format"""
        data = struct.pack('>B', AMF0.OBJECT)
        for key, value in obj.items():
            # Property name (without type marker)
            prop_name = key.encode('utf-8')
            data += struct.pack('>H', len(prop_name)) + prop_name
            
            # Property value
            if isinstance(value, str):
                prop_data = value.encode('utf-8')
                data += struct.pack('>BH', AMF0.STRING, len(prop_data)) + prop_data
            elif isinstance(value, (int, float)):
                data += struct.pack('>Bd', AMF0.NUMBER, float(value))
            elif isinstance(value, bool):
                data += struct.pack('>BB', AMF0.BOOLEAN, 1 if value else 0)
            elif value is None:
                data += struct.pack('>B', AMF0.NULL)
        
        # Object end marker
        data += struct.pack('>HB', 0, AMF0.OBJECT_END)
        return data
    
    @staticmethod
    def decode_string(data: bytes, offset: int = 0) -> Tuple[str, int]:
        """Decode string from AMF0 format"""
        if offset >= len(data) or data[offset] != AMF0.STRING:
            raise ValueError("Invalid AMF0 string")
        
        length = struct.unpack('>H', data[offset+1:offset+3])[0]
        value = data[offset+3:offset+3+length].decode('utf-8')
        return value, offset + 3 + length
    
    @staticmethod
    def decode_number(data: bytes, offset: int = 0) -> Tuple[float, int]:
        """Decode number from AMF0 format"""
        if offset >= len(data) or data[offset] != AMF0.NUMBER:
            raise ValueError("Invalid AMF0 number")
        
        value = struct.unpack('>d', data[offset+1:offset+9])[0]
        return value, offset + 9
    
    @staticmethod
    def decode_value(data: bytes, offset: int = 0) -> Tuple[Any, int]:
        """Decode any AMF0 value"""
        if offset >= len(data):
            return None, offset
        
        data_type = data[offset]
        
        if data_type == AMF0.STRING:
            return AMF0.decode_string(data, offset)
        elif data_type == AMF0.NUMBER:
            return AMF0.decode_number(data, offset)
        elif data_type == AMF0.BOOLEAN:
            value = data[offset + 1] != 0
            return value, offset + 2
        elif data_type == AMF0.NULL:
            return None, offset + 1
        elif data_type == AMF0.OBJECT:
            return AMF0.decode_object(data, offset)
        else:
            logging.warning(f"Unsupported AMF0 type: {data_type}")
            return None, offset + 1
    
    @staticmethod
    def decode_object(data: bytes, offset: int = 0) -> Tuple[Dict[str, Any], int]:
        """Decode object from AMF0 format"""
        if offset >= len(data) or data[offset] != AMF0.OBJECT:
            raise ValueError("Invalid AMF0 object")
        
        obj = {}
        offset += 1
        
        while offset < len(data):
            # Read property name length
            if offset + 2 > len(data):
                break
            
            name_length = struct.unpack('>H', data[offset:offset+2])[0]
            offset += 2
            
            # Check for object end
            if name_length == 0 and offset < len(data) and data[offset] == AMF0.OBJECT_END:
                offset += 1
                break
            
            # Read property name
            if offset + name_length > len(data):
                break
            
            name = data[offset:offset+name_length].decode('utf-8')
            offset += name_length
            
            # Read property value
            value, offset = AMF0.decode_value(data, offset)
            obj[name] = value
        
        return obj, offset


class RTMPMessage:
    """RTMP Message structure"""
    
    def __init__(self, message_type: int, timestamp: int, stream_id: int, payload: bytes):
        self.message_type = message_type
        self.timestamp = timestamp
        self.stream_id = stream_id
        self.payload = payload
        self.length = len(payload)


class RTMPChunk:
    """RTMP Chunk handling"""
    
    # Message types
    SET_CHUNK_SIZE = 1
    ABORT_MESSAGE = 2
    ACKNOWLEDGEMENT = 3
    USER_CONTROL = 4
    WINDOW_ACK_SIZE = 5
    SET_PEER_BANDWIDTH = 6
    AUDIO = 8
    VIDEO = 9
    AMF3_DATA = 15
    AMF3_SHARED_OBJECT = 16
    AMF3_COMMAND = 17
    AMF0_DATA = 18
    AMF0_SHARED_OBJECT = 19
    AMF0_COMMAND = 20
    AGGREGATE = 22
    
    @staticmethod
    def create_connect_response() -> bytes:
        """Create RTMP connect response for OBS/vMix compatibility"""
        # Window Acknowledgement Size
        window_ack = struct.pack('>BBBBBIIII', 
            0x02,  # Basic header (fmt=0, cs_id=2)
            0x00, 0x00, 0x00,  # Message header timestamp
            0x00, 0x00, 0x04,  # Message length (4 bytes)
            0x05,  # Message type (Window Ack Size)
            0x00, 0x00, 0x00, 0x00,  # Message stream ID
            0x00, 0x4C, 0x4B, 0x40  # Window size (5000000)
        )
        
        # Set Peer Bandwidth
        peer_bandwidth = struct.pack('>BBBBBIIIIB',
            0x02,  # Basic header
            0x00, 0x00, 0x00,  # Timestamp
            0x00, 0x00, 0x05,  # Message length (5 bytes)
            0x06,  # Message type (Set Peer Bandwidth)
            0x00, 0x00, 0x00, 0x00,  # Stream ID
            0x00, 0x4C, 0x4B, 0x40,  # Window size
            0x02  # Limit type (dynamic)
        )
        
        # Set Chunk Size
        chunk_size = struct.pack('>BBBBBIIII',
            0x02,  # Basic header
            0x00, 0x00, 0x00,  # Timestamp  
            0x00, 0x00, 0x04,  # Message length
            0x01,  # Message type (Set Chunk Size)
            0x00, 0x00, 0x00, 0x00,  # Stream ID
            0x00, 0x00, 0x10, 0x00  # Chunk size (4096)
        )
        
        return window_ack + peer_bandwidth + chunk_size
    
    @staticmethod
    def create_publish_response(stream_name: str) -> bytes:
        """Create publish response for stream start"""
        # Create AMF0 command response
        response_data = AMF0.encode_string("onStatus")
        response_data += AMF0.encode_number(0)  # Transaction ID
        response_data += AMF0.encode_null()  # Command object
        
        # Status info object
        info = {
            "level": "status",
            "code": "NetStream.Publish.Start",
            "description": f"Started publishing stream {stream_name}",
            "details": stream_name
        }
        response_data += AMF0.encode_object(info)
        
        # Create RTMP message
        message_length = len(response_data)
        header = struct.pack('>BBBBBIIII',
            0x03,  # Basic header (fmt=0, cs_id=3)
            0x00, 0x00, 0x00,  # Timestamp
            (message_length >> 16) & 0xFF,
            (message_length >> 8) & 0xFF,
            message_length & 0xFF,  # Message length
            0x14,  # Message type (AMF0 Command)
            0x01, 0x00, 0x00, 0x00  # Stream ID
        )
        
        return header + response_data


def validate_rtmp_url(url: str) -> Optional[Dict[str, str]]:
    """Validate and parse RTMP URL for OBS/vMix compatibility"""
    try:
        if not url.startswith('rtmp://'):
            return None
        
        # Remove rtmp:// prefix
        url_part = url[7:]
        
        # Split host and path
        if '/' not in url_part:
            return None
        
        host_port, path = url_part.split('/', 1)
        
        # Parse host and port
        if ':' in host_port:
            host, port = host_port.split(':')
            port = int(port)
        else:
            host = host_port
            port = 1935
        
        # Parse app and stream
        path_parts = path.split('/')
        if len(path_parts) < 2:
            return None
        
        app = path_parts[0]
        stream = '/'.join(path_parts[1:])
        
        return {
            'host': host,
            'port': port,
            'app': app,
            'stream': stream
        }
        
    except Exception as e:
        logging.error(f"Error parsing RTMP URL {url}: {e}")
        return None


def create_stream_url(host: str, port: int, app: str, stream_key: str) -> str:
    """Create RTMP URL for streaming software"""
    return f"rtmp://{host}:{port}/{app}/{stream_key}"