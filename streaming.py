import logging
import threading
import time
from datetime import datetime
from app import db, socketio
from models import Stream, StreamAnalytics

class StreamManager:
    def __init__(self):
        self.active_streams = {}
        self.monitoring_thread = None
        self.running = True
        self.start_monitoring()
    
    def start_monitoring(self):
        """Start the stream monitoring thread"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self._monitor_streams)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logging.info("Stream monitoring started")
    
    def _monitor_streams(self):
        """Monitor active streams and collect analytics"""
        from app import app
        while self.running:
            try:
                with app.app_context():
                    live_streams = Stream.query.filter_by(is_live=True).all()
                    
                    for stream in live_streams:
                        # Collect analytics data
                        analytics = StreamAnalytics(
                            stream_id=stream.id,
                            viewer_count=stream.viewer_count,
                            bandwidth_usage=self._calculate_bandwidth(stream),
                            quality=self._detect_quality(stream)
                        )
                        
                        db.session.add(analytics)
                        
                        # Real-time updates temporarily disabled for performance
                        # socketio.emit('stream_analytics', {
                        #     'stream_id': stream.id,
                        #     'viewer_count': stream.viewer_count,
                        #     'bandwidth': analytics.bandwidth_usage,
                        #     'quality': analytics.quality
                        # }, to=f'stream_{stream.id}')
                    
                    db.session.commit()
                    
            except Exception as e:
                logging.error(f"Error in stream monitoring: {e}")
            
            time.sleep(10)  # Monitor every 10 seconds
    
    def _calculate_bandwidth(self, stream):
        """Calculate bandwidth usage for a stream"""
        # This would typically integrate with your streaming server
        # For now, return a simulated value based on viewer count
        base_bandwidth = 2.5  # MB/s for 720p
        return base_bandwidth * max(1, stream.viewer_count * 0.1)
    
    def _detect_quality(self, stream):
        """Detect stream quality"""
        # This would typically integrate with FFmpeg or streaming server
        # For now, return a default quality
        return "720p"
    
    def register_stream(self, stream_key, stream_info):
        """Register a new active stream"""
        self.active_streams[stream_key] = {
            'info': stream_info,
            'start_time': datetime.utcnow(),
            'last_seen': datetime.utcnow()
        }
        logging.info(f"Stream registered: {stream_key}")
    
    def unregister_stream(self, stream_key):
        """Unregister a stream"""
        if stream_key in self.active_streams:
            del self.active_streams[stream_key]
            logging.info(f"Stream unregistered: {stream_key}")
    
    def is_stream_active(self, stream_key):
        """Check if a stream is active"""
        return stream_key in self.active_streams
    
    def update_stream_heartbeat(self, stream_key):
        """Update stream heartbeat"""
        if stream_key in self.active_streams:
            self.active_streams[stream_key]['last_seen'] = datetime.utcnow()
    
    def get_stream_info(self, stream_key):
        """Get information about an active stream"""
        return self.active_streams.get(stream_key)
    
    def cleanup_stale_streams(self):
        """Clean up streams that haven't been seen recently"""
        now = datetime.utcnow()
        stale_streams = []
        
        for stream_key, info in self.active_streams.items():
            if (now - info['last_seen']).seconds > 60:  # 1 minute timeout
                stale_streams.append(stream_key)
        
        for stream_key in stale_streams:
            self.unregister_stream(stream_key)
            
            # Update database
            with db.app.app_context():
                stream = Stream.query.filter_by(stream_key=stream_key).first()
                if stream:
                    stream.is_live = False
                    stream.ended_at = datetime.utcnow()
                    stream.viewer_count = 0
                    db.session.commit()
                    
                    logging.info(f"Stream marked as offline: {stream_key}")
    
    def stop(self):
        """Stop the stream manager"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
