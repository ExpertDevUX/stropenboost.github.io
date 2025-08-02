from app import db
from flask_login import UserMixin
from datetime import datetime
import secrets
import string

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_broadcaster = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Profile fields
    display_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    location = db.Column(db.String(100))
    website = db.Column(db.String(200))
    avatar_url = db.Column(db.String(200))
    
    # Statistics
    followers_count = db.Column(db.Integer, default=0)
    total_views = db.Column(db.Integer, default=0)
    
    # Settings and preferences (stored as JSON)
    preferences = db.Column(db.JSON)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    
    # Streaming settings
    default_stream_title = db.Column(db.String(200))
    default_stream_description = db.Column(db.Text)
    default_category = db.Column(db.String(50), default='other')
    stream_key = db.Column(db.String(128), unique=True)
    
    # Relationships
    streams = db.relationship('Stream', backref='broadcaster', lazy=True, cascade='all, delete-orphan')
    rtmp_keys = db.relationship('RTMPKey', backref='user', lazy=True, cascade='all, delete-orphan')

class Stream(db.Model):
    __tablename__ = 'stream'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    hashtags = db.Column(db.String(500))  # Comma-separated hashtags
    stream_key = db.Column(db.String(128), unique=True, nullable=False)
    is_live = db.Column(db.Boolean, default=False)
    viewer_count = db.Column(db.Integer, default=0, nullable=False)
    max_viewers = db.Column(db.Integer, default=0, nullable=False)
    total_views = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    
    # Stream settings
    allow_embedding = db.Column(db.Boolean, default=True)
    chat_enabled = db.Column(db.Boolean, default=True)
    chat_moderated = db.Column(db.Boolean, default=False)
    
    # Technical settings
    rtmp_url = db.Column(db.String(500))
    hls_url = db.Column(db.String(500))
    dash_url = db.Column(db.String(500))
    webrtc_url = db.Column(db.String(500))
    
    # Stream quality settings
    quality_settings = db.Column(db.JSON)  # Store multiple quality levels
    
    # Foreign key
    broadcaster_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    chat_messages = db.relationship('ChatMessage', backref='stream', lazy=True, cascade='all, delete-orphan')
    analytics = db.relationship('StreamAnalytics', backref='stream', lazy=True, cascade='all, delete-orphan')

class RTMPKey(db.Model):
    __tablename__ = 'rtmp_key'
    id = db.Column(db.Integer, primary_key=True)
    key_name = db.Column(db.String(100), nullable=False)
    rtmp_key = db.Column(db.String(128), unique=True, nullable=False)
    rtmp_url = db.Column(db.String(500), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_external = db.Column(db.Boolean, default=False)  # True for external RTMP sources
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def generate_key(self):
        """Generate a secure RTMP key"""
        alphabet = string.ascii_letters + string.digits
        self.rtmp_key = ''.join(secrets.choice(alphabet) for _ in range(32))

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_moderated = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Foreign key
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)

class StreamAnalytics(db.Model):
    __tablename__ = 'stream_analytics'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    viewer_count = db.Column(db.Integer, default=0)
    bandwidth_usage = db.Column(db.Float, default=0.0)  # MB/s
    quality = db.Column(db.String(20))  # 1080p, 720p, etc.
    
    # Foreign key
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)

class EmbedSettings(db.Model):
    __tablename__ = 'embed_settings'
    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey('stream.id'), nullable=False)
    width = db.Column(db.Integer, default=800)
    height = db.Column(db.Integer, default=450)
    autoplay = db.Column(db.Boolean, default=False)
    show_chat = db.Column(db.Boolean, default=True)
    show_controls = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(20), default='dark')  # dark, light
    
    # Relationship
    stream = db.relationship('Stream', backref='embed_settings', uselist=False)


class AdminSettings(db.Model):
    __tablename__ = 'admin_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_setting(key, default=None):
        setting = AdminSettings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set_setting(key, value, category='general', description=None):
        setting = AdminSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = AdminSettings(
                key=key,
                value=value,
                category=category,
                description=description
            )
            db.session.add(setting)
        db.session.commit()

    @staticmethod
    def get_category_settings(category):
        settings = AdminSettings.query.filter_by(category=category).all()
        return {s.key: s.value for s in settings}

    @staticmethod
    def get_all_settings():
        settings = AdminSettings.query.all()
        result = {}
        for setting in settings:
            result[setting.key] = setting.value
        return result
