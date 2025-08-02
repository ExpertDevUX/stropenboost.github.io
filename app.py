import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_cors import CORS
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
socketio = SocketIO()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Enable CORS for embedding
CORS(app, origins="*", supports_credentials=True)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///strophenboost.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)
# Initialize SocketIO for real-time chat functionality
socketio.init_app(app, cors_allowed_origins="*", async_mode='threading', 
                  ping_timeout=10, ping_interval=5)

# Create tables and initialize default settings
with app.app_context():
    # Import models to ensure they are registered
    import models
    
    # Create all tables
    db.create_all()

# Import routes after app initialization
import routes
import embed
import chat_manager  # Import chat manager for SocketIO events

# Initialize default admin settings after routes are imported
with app.app_context():
    try:
        from routes import init_default_settings
        init_default_settings()
    except Exception as e:
        print(f"Warning: Could not initialize default settings: {e}")
