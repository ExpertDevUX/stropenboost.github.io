#!/usr/bin/env python3
"""
StrophenBoost RTMP Server Starter
Starts the RTMP server for receiving streams from OBS, vMix, and other streaming software
"""

import logging
import threading
import signal
import sys
from rtmp_server import RTMPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rtmp_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info("Received shutdown signal, stopping RTMP server...")
    if rtmp_server:
        rtmp_server.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start RTMP server
    rtmp_server = RTMPServer(host='0.0.0.0', port=1935)
    
    logging.info("Starting StrophenBoost RTMP Server...")
    logging.info("Server will accept streams from OBS, vMix, and other compatible software")
    logging.info("RTMP URL format: rtmp://your-domain:1935/live/YOUR_STREAM_KEY")
    
    try:
        # Start server in main thread
        rtmp_server.start()
    except KeyboardInterrupt:
        logging.info("Server interrupted by user")
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        if rtmp_server:
            rtmp_server.stop()
        logging.info("RTMP Server stopped")