import secrets
import string
import hashlib
import os
from datetime import datetime, timedelta
import logging

def generate_stream_key(length=32):
    """Generate a secure stream key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_rtmp_key(length=32):
    """Generate a secure RTMP key"""
    alphabet = string.ascii_letters + string.digits + '-_'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_stream_key(stream_key):
    """Validate stream key format"""
    if not stream_key:
        return False
    
    if len(stream_key) < 16 or len(stream_key) > 64:
        return False
    
    # Check for valid characters
    valid_chars = set(string.ascii_letters + string.digits + '-_')
    return all(c in valid_chars for c in stream_key)

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if seconds is None:
        return "N/A"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def format_bandwidth(bytes_per_second):
    """Format bandwidth in bytes/second to human readable format"""
    if bytes_per_second is None:
        return "N/A"
    
    # Convert to appropriate unit
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.1f} B/s"
    elif bytes_per_second < 1024 * 1024:
        return f"{bytes_per_second / 1024:.1f} KB/s"
    elif bytes_per_second < 1024 * 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bytes_per_second / (1024 * 1024 * 1024):.1f} GB/s"

def sanitize_filename(filename):
    """Sanitize filename for safe file system operations"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing whitespace and periods
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed'
    
    return filename

def get_file_hash(filepath):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except FileNotFoundError:
        return None

def ensure_directory(directory):
    """Ensure directory exists, create if it doesn't"""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except OSError as e:
        logging.error(f"Failed to create directory {directory}: {e}")
        return False

def get_client_ip(request):
    """Get client IP address from request, considering proxies"""
    # Check for forwarded IP first (common with load balancers/proxies)
    forwarded_ips = request.headers.get('X-Forwarded-For')
    if forwarded_ips:
        # Take the first IP in the chain (original client)
        return forwarded_ips.split(',')[0].strip()
    
    # Check other common headers
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # Fall back to remote address
    return request.remote_addr

def log_user_action(user_id, action, details=None):
    """Log user action for audit purposes"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': user_id,
        'action': action,
        'details': details or {}
    }
    
    logging.info(f"User action: {log_entry}")
    
    # In a production environment, you might want to store this in a separate
    # audit log table or send to a logging service

def calculate_stream_uptime(started_at, ended_at=None):
    """Calculate stream uptime"""
    if not started_at:
        return 0
    
    end_time = ended_at or datetime.utcnow()
    uptime = end_time - started_at
    return int(uptime.total_seconds())

def is_valid_rtmp_url(url):
    """Validate RTMP URL format"""
    if not url:
        return False
    
    # Basic RTMP URL validation
    valid_protocols = ['rtmp://', 'rtmps://']
    return any(url.startswith(protocol) for protocol in valid_protocols)

def parse_quality_from_resolution(width, height):
    """Parse quality string from resolution"""
    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    elif height >= 360:
        return "360p"
    else:
        return "240p"

def generate_embed_token(stream_id, expires_in_hours=24):
    """Generate a temporary token for embed authentication"""
    # Create a simple token based on stream_id and expiration
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    
    # Create token data
    token_data = f"{stream_id}:{expires_at.timestamp()}"
    
    # Simple encoding (in production, use proper JWT or similar)
    token = hashlib.sha256(token_data.encode()).hexdigest()
    
    return token, expires_at

def verify_embed_token(token, stream_id):
    """Verify embed token validity"""
    # This is a simplified implementation
    # In production, use proper token validation with JWT or similar
    try:
        # For now, just check if token exists and is not empty
        return bool(token and len(token) == 64)  # SHA-256 hex length
    except Exception:
        return False

def clean_old_files(directory, max_age_hours=24):
    """Clean old files from a directory"""
    if not os.path.exists(directory):
        return
    
    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
    cutoff_timestamp = cutoff_time.timestamp()
    
    try:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_timestamp:
                    os.remove(filepath)
                    logging.info(f"Cleaned old file: {filepath}")
    except Exception as e:
        logging.error(f"Error cleaning old files from {directory}: {e}")
