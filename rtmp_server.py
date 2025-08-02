import socket
import threading
import logging
import struct
import hashlib
import random
import time
from datetime import datetime
from app import db
from models import Stream, RTMPKey
from streaming import StreamManager
from ffmpeg_manager import FFmpegManager

class RTMPServer:
    def __init__(self, host='0.0.0.0', port=1935):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.stream_manager = StreamManager()
        self.ffmpeg_manager = FFmpegManager()
        self.active_streams = {}
        
        # RTMP protocol constants
        self.RTMP_VERSION = 3
        self.RTMP_HANDSHAKE_SIZE = 1536
        self.RTMP_DEFAULT_CHUNK_SIZE = 128
        
    def start(self):
        """Start the RTMP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            self.running = True
            
            logging.info(f"RTMP Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.socket.accept()
                    logging.info(f"RTMP connection from {client_address}")
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logging.error(f"Socket error: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to start RTMP server: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the RTMP server"""
        self.running = False
        if self.socket:
            self.socket.close()
        logging.info("RTMP Server stopped")
    
    def _handle_client(self, client_socket, client_address):
        """Handle RTMP client connection"""
        stream_key = None
        try:
            logging.info(f"Processing RTMP connection from {client_address}")
            
            # Set socket timeout for better connection handling
            client_socket.settimeout(30.0)
            
            # RTMP handshake (C0, C1, C2)
            if not self._rtmp_handshake(client_socket):
                logging.warning(f"RTMP handshake failed for {client_address}")
                return
            
            logging.info(f"RTMP handshake completed for {client_address}")
            
            # Handle RTMP commands and data
            stream_key = self._handle_rtmp_session(client_socket, client_address)
            
        except socket.timeout:
            logging.warning(f"RTMP connection timeout for {client_address}")
        except ConnectionResetError:
            logging.info(f"RTMP client {client_address} disconnected")
        except Exception as e:
            logging.error(f"Error handling RTMP client {client_address}: {e}")
        finally:
            if stream_key:
                self._cleanup_stream(stream_key)
            try:
                client_socket.close()
            except:
                pass
            logging.info(f"RTMP connection closed for {client_address}")
    
    def _rtmp_handshake(self, client_socket):
        """Perform RTMP handshake (compatible with OBS, vMix, etc.)"""
        try:
            # C0: Read version byte
            c0 = client_socket.recv(1)
            if len(c0) != 1 or c0[0] != self.RTMP_VERSION:
                logging.error(f"Invalid RTMP version: {c0[0] if c0 else 'None'}")
                return False
            
            # C1: Read 1536 bytes
            c1 = client_socket.recv(self.RTMP_HANDSHAKE_SIZE)
            if len(c1) != self.RTMP_HANDSHAKE_SIZE:
                logging.error(f"Invalid C1 size: {len(c1)}")
                return False
            
            # S0: Send version
            client_socket.send(bytes([self.RTMP_VERSION]))
            
            # S1: Send server handshake
            timestamp = int(time.time())
            s1 = struct.pack('>I', timestamp)  # 4 bytes timestamp
            s1 += b'\x00\x00\x00\x00'  # 4 bytes zero
            s1 += bytes([random.randint(0, 255) for _ in range(self.RTMP_HANDSHAKE_SIZE - 8)])
            client_socket.send(s1)
            
            # S2: Echo C1
            client_socket.send(c1)
            
            # C2: Read client response
            c2 = client_socket.recv(self.RTMP_HANDSHAKE_SIZE)
            if len(c2) != self.RTMP_HANDSHAKE_SIZE:
                logging.error(f"Invalid C2 size: {len(c2)}")
                return False
            
            logging.info("RTMP handshake completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"RTMP handshake error: {e}")
            return False
    
    def _handle_rtmp_session(self, client_socket, client_address):
        """Handle RTMP session after handshake"""
        stream_key = None
        app_name = None
        stream_name = None
        
        try:
            while self.running:
                # Read basic header
                try:
                    basic_header = client_socket.recv(1)
                    if not basic_header:
                        break
                except socket.timeout:
                    continue
                
                if len(basic_header) == 0:
                    break
                
                # Parse chunk stream ID and message type
                chunk_stream_id = basic_header[0] & 0x3F
                fmt = (basic_header[0] >> 6) & 0x03
                
                # Read message header based on format
                message_header = self._read_message_header(client_socket, fmt)
                if message_header is None:
                    continue
                
                # Read message payload
                payload = self._read_message_payload(client_socket, message_header)
                if payload is None:
                    continue
                
                # Process message based on type
                if message_header.get('message_type') == 20:  # AMF0 Command
                    result = self._handle_amf_command(payload, client_socket)
                    if result:
                        command, data = result
                        
                        if command == 'connect':
                            app_name = data.get('app', 'live')
                            self._send_connect_response(client_socket)
                            logging.info(f"RTMP connect to app '{app_name}' from {client_address}")
                            
                        elif command == 'publish':
                            stream_name = data.get('stream_name')
                            if stream_name:
                                stream_key = self._validate_stream_key(stream_name)
                                if stream_key:
                                    self._start_publishing(client_socket, stream_key, client_address)
                                    # Start FFmpeg process for this stream
                                    self.ffmpeg_manager.start_stream(stream_key)
                                    logging.info(f"Started publishing stream '{stream_name}' with key '{stream_key}'")
                                else:
                                    self._send_error_response(client_socket, "Invalid stream key")
                                    logging.warning(f"Invalid stream key '{stream_name}' from {client_address}")
                                    break
                                    
                elif message_header.get('message_type') in [8, 9]:  # Audio/Video data
                    if stream_key:
                        # Stream data is automatically handled by FFmpeg
                        # Update stream statistics
                        self._update_stream_stats(stream_key, len(payload))
                        
        except Exception as e:
            logging.error(f"Error in RTMP session for {client_address}: {e}")
        
        return stream_key
    
    def _read_message_header(self, client_socket, fmt):
        """Read RTMP message header based on format type"""
        try:
            if fmt == 0:  # 11 bytes
                data = client_socket.recv(11)
                if len(data) != 11:
                    return None
                timestamp = struct.unpack('>I', b'\x00' + data[0:3])[0]
                message_length = struct.unpack('>I', b'\x00' + data[3:6])[0]
                message_type = data[6]
                stream_id = struct.unpack('<I', data[7:11])[0]
                
                return {
                    'timestamp': timestamp,
                    'message_length': message_length,
                    'message_type': message_type,
                    'stream_id': stream_id
                }
            elif fmt == 1:  # 7 bytes
                data = client_socket.recv(7)
                if len(data) != 7:
                    return None
                timestamp = struct.unpack('>I', b'\x00' + data[0:3])[0]
                message_length = struct.unpack('>I', b'\x00' + data[3:6])[0]
                message_type = data[6]
                
                return {
                    'timestamp': timestamp,
                    'message_length': message_length,
                    'message_type': message_type,
                    'stream_id': 0
                }
            elif fmt == 2:  # 3 bytes
                data = client_socket.recv(3)
                if len(data) != 3:
                    return None
                timestamp = struct.unpack('>I', b'\x00' + data[0:3])[0]
                
                return {
                    'timestamp': timestamp,
                    'message_length': 0,
                    'message_type': 0,
                    'stream_id': 0
                }
            else:  # fmt == 3, no header
                return {
                    'timestamp': 0,
                    'message_length': 0,
                    'message_type': 0,
                    'stream_id': 0
                }
                
        except Exception as e:
            logging.error(f"Error reading message header: {e}")
            return None
    
    def _read_message_payload(self, client_socket, message_header):
        """Read RTMP message payload"""
        try:
            length = message_header.get('message_length', 0)
            if length == 0:
                return b''
            
            payload = client_socket.recv(length)
            if len(payload) != length:
                logging.warning(f"Expected {length} bytes, got {len(payload)}")
                return None
            
            return payload
            
        except Exception as e:
            logging.error(f"Error reading message payload: {e}")
            return None
    
    def _handle_amf_command(self, payload, client_socket):
        """Handle AMF0 command messages"""
        try:
            from rtmp_utils import AMF0
            
            offset = 0
            # Decode command name
            command_name, offset = AMF0.decode_string(payload, offset)
            
            # Decode transaction ID
            transaction_id, offset = AMF0.decode_number(payload, offset)
            
            # Decode command object (can be null)
            command_object, offset = AMF0.decode_value(payload, offset)
            
            data = {
                'transaction_id': transaction_id,
                'command_object': command_object
            }
            
            if command_name == 'connect':
                if isinstance(command_object, dict):
                    data['app'] = command_object.get('app', 'live')
                    data['flashVer'] = command_object.get('flashVer', '')
                    data['tcUrl'] = command_object.get('tcUrl', '')
            
            elif command_name == 'publish':
                # Decode stream name
                if offset < len(payload):
                    stream_name, offset = AMF0.decode_string(payload, offset)
                    data['stream_name'] = stream_name
            
            return command_name, data
            
        except Exception as e:
            logging.error(f"Error handling AMF command: {e}")
            return None
    
    def _send_connect_response(self, client_socket):
        """Send RTMP connect response"""
        try:
            from rtmp_utils import RTMPChunk, AMF0
            
            # Send basic protocol messages
            response = RTMPChunk.create_connect_response()
            client_socket.send(response)
            
            # Send _result command
            result_data = AMF0.encode_string("_result")
            result_data += AMF0.encode_number(1)  # Transaction ID
            
            # Properties object
            properties = {
                "fmsVer": "FMS/3,0,1,123",
                "capabilities": 31
            }
            result_data += AMF0.encode_object(properties)
            
            # Information object
            info = {
                "level": "status",
                "code": "NetConnection.Connect.Success",
                "description": "Connection succeeded.",
                "objectEncoding": 0
            }
            result_data += AMF0.encode_object(info)
            
            # Create message header
            message_length = len(result_data)
            header = struct.pack('>BBBBBIIII',
                0x03,  # Basic header
                0x00, 0x00, 0x00,  # Timestamp
                (message_length >> 16) & 0xFF,
                (message_length >> 8) & 0xFF,
                message_length & 0xFF,
                0x14,  # AMF0 Command
                0x00, 0x00, 0x00, 0x00  # Stream ID
            )
            
            client_socket.send(header + result_data)
            
        except Exception as e:
            logging.error(f"Error sending connect response: {e}")
    
    def _start_publishing(self, client_socket, stream_key, client_address):
        """Start publishing stream"""
        try:
            from rtmp_utils import RTMPChunk
            
            # Send publish response
            response = RTMPChunk.create_publish_response(stream_key)
            client_socket.send(response)
            
            # Mark stream as live in database
            from app import app
            with app.app_context():
                stream = Stream.query.filter_by(stream_key=stream_key).first()
                if stream:
                    stream.is_live = True
                    stream.start_time = datetime.utcnow()
                    stream.viewer_count = 0
                    db.session.commit()
                    logging.info(f"Stream {stream_key} is now live")
            
            # Register with stream manager
            self.active_streams[stream_key] = {
                'client_address': client_address,
                'start_time': datetime.utcnow(),
                'socket': client_socket
            }
            
        except Exception as e:
            logging.error(f"Error starting publishing: {e}")
    
    def _validate_stream_key(self, stream_name):
        """Validate stream key against database"""
        try:
            from app import app
            with app.app_context():
                rtmp_key = RTMPKey.query.filter_by(key=stream_name, is_active=True).first()
                if rtmp_key:
                    return rtmp_key.key
                    
                # Also check if stream_name matches a stream's stream_key
                stream = Stream.query.filter_by(stream_key=stream_name).first()
                if stream:
                    return stream.stream_key
                    
            return None
            
        except Exception as e:
            logging.error(f"Error validating stream key: {e}")
            return None
    
    def _send_error_response(self, client_socket, error_message):
        """Send error response to client"""
        try:
            from rtmp_utils import AMF0
            
            # Create error response
            error_data = AMF0.encode_string("onStatus")
            error_data += AMF0.encode_number(0)
            error_data += AMF0.encode_null()
            
            info = {
                "level": "error",
                "code": "NetStream.Publish.BadName",
                "description": error_message
            }
            error_data += AMF0.encode_object(info)
            
            # Send message
            message_length = len(error_data)
            header = struct.pack('>BBBBBIIII',
                0x03,  # Basic header
                0x00, 0x00, 0x00,  # Timestamp
                (message_length >> 16) & 0xFF,
                (message_length >> 8) & 0xFF,
                message_length & 0xFF,
                0x14,  # AMF0 Command
                0x01, 0x00, 0x00, 0x00  # Stream ID
            )
            
            client_socket.send(header + error_data)
            
        except Exception as e:
            logging.error(f"Error sending error response: {e}")
    
    def _cleanup_stream(self, stream_key):
        """Clean up stream when disconnected"""
        try:
            if stream_key in self.active_streams:
                del self.active_streams[stream_key]
            
            # Stop FFmpeg process
            self.ffmpeg_manager.stop_stream(stream_key)
            
            # Mark stream as offline in database
            from app import app
            with app.app_context():
                stream = Stream.query.filter_by(stream_key=stream_key).first()
                if stream:
                    stream.is_live = False
                    stream.end_time = datetime.utcnow()
                    db.session.commit()
                    logging.info(f"Stream {stream_key} is now offline")
                    
        except Exception as e:
            logging.error(f"Error cleaning up stream {stream_key}: {e}")
    
    def _update_stream_stats(self, stream_key, data_size):
        """Update stream statistics"""
        try:
            # This could be enhanced to track bandwidth, frame rates, etc.
            pass
        except Exception as e:
            logging.error(f"Error updating stream stats: {e}")
            
            # Send S0 + S1
            s0 = b'\x03'
            s1 = b'\x00' * 1536  # Simplified S1
            client_socket.send(s0 + s1)
            
            # C2
            c2 = client_socket.recv(1536)
            if len(c2) != 1536:
                return False
            
            # Send S2
            s2 = c0_c1[1:1537]  # Echo C1 as S2
            client_socket.send(s2)
            
            logging.info("RTMP handshake completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"RTMP handshake error: {e}")
            return False
    
    def _read_rtmp_message(self, client_socket):
        """Read an RTMP message from the client"""
        try:
            # Read basic header
            basic_header = client_socket.recv(1)
            if not basic_header:
                return None
            
            # This is a simplified RTMP message parser
            # In a production environment, you'd want a full RTMP implementation
            
            # For now, return a mock message structure
            return {
                'type': 'unknown',
                'data': b'',
                'timestamp': 0
            }
            
        except Exception as e:
            logging.error(f"Error reading RTMP message: {e}")
            return None
    
    def _handle_connect(self, client_socket, message):
        """Handle RTMP connect command"""
        logging.info("Handling RTMP connect")
        # Send connect response
        # This would typically involve sending proper RTMP responses
        pass
    
    def _handle_publish(self, client_socket, message):
        """Handle RTMP publish command"""
        # Extract stream key from publish command
        # This is simplified - in reality you'd parse the RTMP message properly
        stream_key = "example_stream_key"  # This should be extracted from the message
        
        logging.info(f"Handling RTMP publish for stream: {stream_key}")
        
        # Validate stream key
        with db.app.app_context():
            stream = Stream.query.filter_by(stream_key=stream_key).first()
            if not stream:
                logging.warning(f"Invalid stream key: {stream_key}")
                return None
            
            # Update stream status
            stream.is_live = True
            stream.started_at = datetime.utcnow()
            db.session.commit()
        
        return stream_key
    
    def _start_stream_processing(self, stream_key, client_socket):
        """Start processing stream data"""
        logging.info(f"Starting stream processing for: {stream_key}")
        
        # Register with stream manager
        self.stream_manager.register_stream(stream_key, {
            'client_socket': client_socket,
            'start_time': datetime.utcnow()
        })
        
        # This would typically start FFmpeg processing
        # For now, we'll just log the event
        rtmp_input = f"rtmp://localhost:1935/live/{stream_key}"
        self.ffmpeg_manager.start_stream(stream_key, rtmp_input)
    
    def _stop_stream_processing(self, stream_key):
        """Stop processing stream data"""
        logging.info(f"Stopping stream processing for: {stream_key}")
        
        # Update database
        with db.app.app_context():
            stream = Stream.query.filter_by(stream_key=stream_key).first()
            if stream:
                stream.is_live = False
                stream.ended_at = datetime.utcnow()
                stream.viewer_count = 0
                db.session.commit()
        
        # Unregister from stream manager
        self.stream_manager.unregister_stream(stream_key)
        
        # Stop FFmpeg processing
        self.ffmpeg_manager.stop_stream(stream_key)
    
    def _process_media_data(self, stream_key, message):
        """Process incoming media data"""
        # Update heartbeat
        self.stream_manager.update_stream_heartbeat(stream_key)
        
        # In a real implementation, you'd forward this data to FFmpeg
        # or handle it according to your streaming architecture
        pass

# Simple RTMP server runner (can be started separately)
def run_rtmp_server():
    """Run the RTMP server"""
    server = RTMPServer()
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("Shutting down RTMP server...")
        server.stop()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_rtmp_server()
