import subprocess
import threading
import os
import logging
import signal
from pathlib import Path

class FFmpegManager:
    def __init__(self):
        self.processes = {}
        self.output_dir = os.path.join(os.getcwd(), 'stream_output')
        self.ensure_output_directory()
    
    def ensure_output_directory(self):
        """Ensure output directories exist"""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(self.output_dir, 'hls')).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(self.output_dir, 'dash')).mkdir(parents=True, exist_ok=True)
    
    def start_stream(self, stream_key, rtmp_input=None):
        """Start FFmpeg processing for a stream (OBS/vMix compatible)"""
        if stream_key in self.processes:
            logging.warning(f"Stream {stream_key} already has an active process")
            return True
        
        try:
            # Create output directories for this stream
            hls_output_dir = os.path.join(self.output_dir, 'hls', stream_key)
            dash_output_dir = os.path.join(self.output_dir, 'dash', stream_key)
            
            Path(hls_output_dir).mkdir(parents=True, exist_ok=True)
            Path(dash_output_dir).mkdir(parents=True, exist_ok=True)
            
            # If no RTMP input specified, create RTMP server input
            if not rtmp_input:
                rtmp_input = f"rtmp://localhost:1935/live/{stream_key}"
            
            # FFmpeg command optimized for OBS/vMix streaming
            cmd = [
                'ffmpeg',
                '-f', 'flv',  # Specify FLV format for RTMP input
                '-listen', '1',  # Listen for incoming RTMP connections
                '-i', rtmp_input,
                
                # Video encoding settings (optimized for streaming)
                '-c:v', 'libx264',
                '-preset', 'veryfast',  # Balance between speed and quality
                '-tune', 'zerolatency',  # Optimize for low latency
                '-profile:v', 'baseline',  # Ensure compatibility
                '-level', '3.1',
                '-pix_fmt', 'yuv420p',
                '-g', '60',  # GOP size (2 seconds at 30fps)
                '-keyint_min', '60',
                '-sc_threshold', '0',
                '-b:v', '2500k',  # Video bitrate
                '-maxrate', '2500k',
                '-bufsize', '5000k',
                
                # Audio encoding settings
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '2',
                
                # Multiple output formats
                # HLS output for web playback
                '-f', 'hls',
                '-hls_time', '4',
                '-hls_list_size', '6',
                '-hls_flags', 'delete_segments+independent_segments',
                '-hls_segment_type', 'mpegts',
                '-hls_segment_filename', os.path.join(hls_output_dir, 'segment_%03d.ts'),
                '-hls_playlist_type', 'event',
                os.path.join(hls_output_dir, 'index.m3u8'),
                
                # Additional options for stability
                '-reconnect', '1',
                '-reconnect_at_eof', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-loglevel', 'info',
                '-y'  # Overwrite output files
            ]
            
            # Start FFmpeg process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group for clean termination
            )
            
            self.processes[stream_key] = {
                'process': process,
                'cmd': cmd,
                'hls_dir': hls_output_dir,
                'dash_dir': dash_output_dir
            }
            
            # Start monitoring thread for this process
            monitor_thread = threading.Thread(
                target=self._monitor_process,
                args=(stream_key, process)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            logging.info(f"FFmpeg process started for stream: {stream_key}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start FFmpeg for stream {stream_key}: {e}")
            return False
    
    def stop_stream(self, stream_key):
        """Stop FFmpeg processing for a stream"""
        if stream_key not in self.processes:
            logging.warning(f"No active process found for stream: {stream_key}")
            return False
        
        try:
            process_info = self.processes[stream_key]
            process = process_info['process']
            
            # Terminate the process group
            if process.poll() is None:  # Process is still running
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                # Wait for graceful termination
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
            
            del self.processes[stream_key]
            logging.info(f"FFmpeg process stopped for stream: {stream_key}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to stop FFmpeg for stream {stream_key}: {e}")
            return False
    
    def _monitor_process(self, stream_key, process):
        """Monitor FFmpeg process and handle output"""
        try:
            # Read stderr for FFmpeg output
            for line in iter(process.stderr.readline, b''):
                if line:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    logging.debug(f"FFmpeg [{stream_key}]: {line_str}")
                    
                    # You could parse FFmpeg output here for additional metrics
                    # like bitrate, fps, dropped frames, etc.
            
            # Process has ended
            return_code = process.wait()
            
            if stream_key in self.processes:
                del self.processes[stream_key]
                
            if return_code == 0:
                logging.info(f"FFmpeg process ended normally for stream: {stream_key}")
            else:
                logging.warning(f"FFmpeg process ended with error code {return_code} for stream: {stream_key}")
                
        except Exception as e:
            logging.error(f"Error monitoring FFmpeg process for stream {stream_key}: {e}")
    
    def is_stream_active(self, stream_key):
        """Check if FFmpeg is actively processing a stream"""
        if stream_key not in self.processes:
            return False
        
        process = self.processes[stream_key]['process']
        return process.poll() is None
    
    def get_stream_stats(self, stream_key):
        """Get statistics for a stream"""
        if stream_key not in self.processes:
            return None
        
        process_info = self.processes[stream_key]
        process = process_info['process']
        
        return {
            'is_running': process.poll() is None,
            'pid': process.pid,
            'hls_dir': process_info['hls_dir'],
            'dash_dir': process_info['dash_dir'],
            'cmd': ' '.join(process_info['cmd'])
        }
    
    def cleanup(self):
        """Clean up all FFmpeg processes"""
        logging.info("Cleaning up FFmpeg processes...")
        
        for stream_key in list(self.processes.keys()):
            self.stop_stream(stream_key)
        
        logging.info("FFmpeg cleanup completed")
    
    def get_active_streams(self):
        """Get list of active stream keys"""
        return list(self.processes.keys())
    
    def restart_stream(self, stream_key, rtmp_input):
        """Restart FFmpeg processing for a stream"""
        logging.info(f"Restarting stream: {stream_key}")
        self.stop_stream(stream_key)
        return self.start_stream(stream_key, rtmp_input)
