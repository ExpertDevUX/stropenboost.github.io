from app import app, socketio
import logging
import threading
from rtmp_server import RTMPServer

def start_rtmp_server():
    """Start RTMP server in a separate thread"""
    try:
        rtmp_server = RTMPServer(host='0.0.0.0', port=1935)
        logging.info("Starting RTMP server for OBS/vMix compatibility...")
        rtmp_server.start()
    except Exception as e:
        logging.error(f"RTMP server error: {e}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting StrophenBoost streaming platform...")
    
    # Start RTMP server in background thread
    rtmp_thread = threading.Thread(target=start_rtmp_server, daemon=True)
    rtmp_thread.start()
    
    # Start main Flask-SocketIO application
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    
    # Initialize database tables
    with app.app_context():
        import models
        db.create_all()
        logging.info("Database tables initialized")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True, use_reloader=False, log_output=True)
