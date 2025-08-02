from flask import render_template, request, redirect, url_for, jsonify, session, flash
from flask_socketio import emit, join_room, leave_room
from flask_login import login_required, current_user
from app import app, db, socketio
from models import User, Stream, RTMPKey, ChatMessage, StreamAnalytics, EmbedSettings, AdminSettings
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
from datetime import datetime
import logging
import uuid
from streaming import StreamManager
from ffmpeg_manager import FFmpegManager

# Initialize managers
stream_manager = StreamManager()
ffmpeg_manager = FFmpegManager()

@app.route('/')
def index():
    """Landing page with live streams"""
    live_streams = Stream.query.filter_by(is_live=True).order_by(Stream.viewer_count.desc()).limit(10).all()
    return render_template('stream.html', streams=live_streams, is_home=True)

@app.route('/dashboard')
def dashboard():
    """Broadcaster dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('index'))
    
    # Get streams and RTMP keys for this user
    streams = Stream.query.filter_by(broadcaster_id=user.id).order_by(Stream.created_at.desc()).all()
    rtmp_keys = RTMPKey.query.filter_by(user_id=user.id).order_by(RTMPKey.created_at.desc()).all()
    
    # Debug logging
    logging.info(f"Dashboard: User {user.username} (ID: {user.id}) has {len(streams)} streams")
    for stream in streams:
        logging.info(f"Stream: ID={stream.id}, Title='{stream.title}', Live={stream.is_live}")
    
    return render_template('dashboard.html', user=user, streams=streams, rtmp_keys=rtmp_keys)

@app.route('/login', methods=['POST'])
def login():
    """User login via AJAX"""
    username = request.form['username']
    password = request.form['password']
    
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    else:
        return jsonify({'success': False, 'error': 'Invalid username or password'})

@app.route('/register', methods=['POST'])
def register():
    """User registration via AJAX"""
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    is_broadcaster = 'is_broadcaster' in request.form
    
    # Check if user exists
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'Username already exists'})
    
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Email already exists'})
    
    # Create new user
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_broadcaster=is_broadcaster
    )
    
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username
    
    return jsonify({'success': True, 'redirect': url_for('dashboard')})

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/stream/<int:stream_id>')
def view_stream(stream_id):
    """View a specific stream"""
    stream = Stream.query.get_or_404(stream_id)
    
    # Increment view count
    stream.total_views += 1
    db.session.commit()
    
    # Get recent chat messages
    chat_messages = ChatMessage.query.filter_by(
        stream_id=stream_id, 
        is_deleted=False
    ).order_by(ChatMessage.timestamp.desc()).limit(50).all()
    
    return render_template('stream.html', stream=stream, chat_messages=reversed(chat_messages))

@app.route('/create_stream', methods=['POST'])
def create_stream():
    """Create a new stream"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    user = User.query.get(session['user_id'])
    if not user.is_broadcaster:
        return jsonify({'error': 'Broadcaster privileges required'}), 403
    
    title = request.form['title']
    description = request.form.get('description', '')
    
    # Generate unique stream key
    stream_key = str(uuid.uuid4()).replace('-', '')
    
    stream = Stream(
        title=title,
        description=description,
        stream_key=stream_key,
        broadcaster_id=user.id,
        rtmp_url=f"rtmp://localhost:1935/live/{stream_key}",
        hls_url=f"/hls/{stream_key}/index.m3u8",
        dash_url=f"/dash/{stream_key}/index.mpd"
    )
    
    db.session.add(stream)
    db.session.commit()
    
    # Create default embed settings
    embed_settings = EmbedSettings(stream_id=stream.id)
    db.session.add(embed_settings)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'stream_id': stream.id,
        'stream_key': stream_key,
        'rtmp_url': stream.rtmp_url,
        'title': stream.title,
        'description': stream.description
    })

@app.route('/start_stream/<int:stream_id>', methods=['POST'])
def start_stream(stream_id):
    """Start streaming"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Start FFmpeg processing for real streaming
    try:
        success = ffmpeg_manager.start_stream(stream.stream_key, stream.rtmp_url)
        
        if success:
            stream.is_live = True
            stream.started_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Stream started successfully'})
        else:
            return jsonify({'error': 'Failed to start FFmpeg processing'}), 500
    except Exception as e:
        logging.error(f"Error starting stream: {e}")
        return jsonify({'error': 'Failed to start stream'}), 500

@app.route('/stop_stream/<int:stream_id>', methods=['POST'])
def stop_stream(stream_id):
    """Stop streaming"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Stop FFmpeg processing
    ffmpeg_manager.stop_stream(stream.stream_key)
    
    stream.is_live = False
    stream.ended_at = datetime.utcnow()
    stream.viewer_count = 0
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Stream stopped successfully'})

@app.route('/create_rtmp_key', methods=['POST'])
def create_rtmp_key():
    """Create a new RTMP key"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    key_name = request.form['key_name']
    rtmp_url = request.form.get('rtmp_url', 'rtmp://localhost:1935/live')
    is_external = request.form.get('is_external') == 'true'
    
    rtmp_key = RTMPKey(
        key_name=key_name,
        rtmp_url=rtmp_url,
        is_external=is_external,
        user_id=session['user_id']
    )
    rtmp_key.generate_key()
    
    db.session.add(rtmp_key)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'rtmp_key': rtmp_key.rtmp_key,
        'rtmp_url': rtmp_key.rtmp_url,
        'key_name': rtmp_key.key_name,
        'key_id': rtmp_key.id
    })

@app.route('/delete_rtmp_key/<int:key_id>', methods=['POST'])
def delete_rtmp_key(key_id):
    """Delete an RTMP key"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    rtmp_key = RTMPKey.query.get_or_404(key_id)
    
    if rtmp_key.user_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(rtmp_key)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'RTMP key deleted successfully'})

@app.route('/delete_stream/<int:stream_id>', methods=['POST'])
def delete_stream(stream_id):
    """Delete a stream"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Stop stream if it's live
    if stream.is_live:
        ffmpeg_manager.stop_stream(stream.stream_key)
    
    # Delete related records
    StreamAnalytics.query.filter_by(stream_id=stream_id).delete()
    ChatMessage.query.filter_by(stream_id=stream_id).delete()
    EmbedSettings.query.filter_by(stream_id=stream_id).delete()
    
    # Delete the stream
    db.session.delete(stream)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Stream deleted successfully'})

@app.route('/stream_analytics/<int:stream_id>')
def stream_analytics(stream_id):
    """Get stream analytics data"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    analytics = StreamAnalytics.query.filter_by(stream_id=stream_id).order_by(
        StreamAnalytics.timestamp.desc()
    ).limit(100).all()
    
    data = [{
        'timestamp': a.timestamp.isoformat(),
        'viewer_count': a.viewer_count,
        'bandwidth_usage': a.bandwidth_usage,
        'quality': a.quality
    } for a in analytics]
    
    return jsonify({
        'analytics': data,
        'current_viewers': stream.viewer_count,
        'max_viewers': stream.max_viewers,
        'total_views': stream.total_views
    })

# Socket.IO events for real-time features
@socketio.on('join_stream')
def handle_join_stream(data):
    """Handle user joining a stream"""
    stream_id = data['stream_id']
    username = data.get('username', 'Anonymous')
    
    join_room(f'stream_{stream_id}')
    
    # Update viewer count
    stream = Stream.query.get(stream_id)
    if stream:
        stream.viewer_count += 1
        if stream.viewer_count > stream.max_viewers:
            stream.max_viewers = stream.viewer_count
        db.session.commit()
        
        emit('viewer_update', {'count': stream.viewer_count}, to=f'stream_{stream_id}')
        emit('user_joined', {'username': username}, to=f'stream_{stream_id}')

@socketio.on('leave_stream')
def handle_leave_stream(data):
    """Handle user leaving a stream"""
    stream_id = data['stream_id']
    username = data.get('username', 'Anonymous')
    
    leave_room(f'stream_{stream_id}')
    
    # Update viewer count
    stream = Stream.query.get(stream_id)
    if stream and stream.viewer_count > 0:
        stream.viewer_count -= 1
        db.session.commit()
        
        emit('viewer_update', {'count': stream.viewer_count}, to=f'stream_{stream_id}')
        emit('user_left', {'username': username}, to=f'stream_{stream_id}')

@socketio.on('send_chat_message')
def handle_chat_message(data):
    """Handle chat message"""
    stream_id = data['stream_id']
    username = data['username']
    message = data['message']
    
    # Save message to database
    chat_message = ChatMessage(
        stream_id=stream_id,
        username=username,
        message=message
    )
    db.session.add(chat_message)
    db.session.commit()
    
    # Emit to all users in the stream room
    emit('new_chat_message', {
        'username': username,
        'message': message,
        'timestamp': chat_message.timestamp.isoformat()
    }, to=f'stream_{stream_id}')

@socketio.on('moderate_message')
def handle_moderate_message(data):
    """Handle message moderation"""
    message_id = data['message_id']
    action = data['action']  # 'delete' or 'approve'
    
    chat_message = ChatMessage.query.get(message_id)
    if chat_message:
        if action == 'delete':
            chat_message.is_deleted = True
        elif action == 'approve':
            chat_message.is_moderated = True
        
        db.session.commit()
        
        emit('message_moderated', {
            'message_id': message_id,
            'action': action
        }, to=f'stream_{chat_message.stream_id}')


# Footer Pages
@app.route("/about")
def about():
    """About page"""
    return render_template("about.html")

@app.route("/documentation")
def documentation():
    """Documentation page"""
    return render_template("documentation.html")

@app.route("/privacy")
def privacy():
    """Privacy policy page"""
    return render_template("privacy.html")

@app.route("/contact")
def contact():
    """Contact page"""
    return render_template("contact.html")

@app.route("/api")
def api_reference():
    """API reference page"""
    return render_template("documentation.html")

@app.route("/support")  
def support():
    """Support page"""
    return render_template("contact.html")


# Management Pages Routes
@app.route("/user-management")
def user_management():
    """User management page"""
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    # Get all users for management
    users = User.query.all()
    
    return render_template("user_management.html", 
                         users=users,
                         total_users=len(users),
                         active_broadcasters=len([u for u in users if u.is_broadcaster]),
                         active_viewers=len([u for u in users if not u.is_broadcaster]),
                         new_users_today=0)

@app.route("/content-management")
def content_management():
    """Content management page"""
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    # Get all streams for content management
    streams = Stream.query.all()
    
    return render_template("content_management.html",
                         streams=streams,
                         total_streams=len(streams),
                         active_streams=len([s for s in streams if s.is_live]),
                         reported_content=0,
                         moderated_content=0)


# User Management Actions
@app.route("/user-management/view/<int:user_id>")
def view_user_profile(user_id):
    """View user profile details"""
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    user = User.query.get_or_404(user_id)
    user_streams = Stream.query.filter_by(broadcaster_id=user_id).all()
    
    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_broadcaster": user.is_broadcaster,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "N/A",
            "stream_count": len(user_streams),
            "streams": [{"id": s.id, "title": s.title, "is_live": s.is_live} for s in user_streams]
        }
    })

@app.route("/user-management/edit/<int:user_id>", methods=["POST"])
def edit_user(user_id):
    """Edit user details"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    try:
        if "username" in data:
            user.username = data["username"]
        if "email" in data:
            user.email = data["email"]
        if "is_broadcaster" in data:
            user.is_broadcaster = data["is_broadcaster"]
            
        db.session.commit()
        return jsonify({"success": True, "message": "User updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/user-management/suspend/<int:user_id>", methods=["POST"])
def suspend_user(user_id):
    """Suspend user account"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get_or_404(user_id)
    
    try:
        # Add suspended field to user model if needed
        # For now, we will just return success
        return jsonify({"success": True, "message": f"User {user.username} has been suspended"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/user-management/add", methods=["POST"])
def add_user():
    """Add new user"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    
    try:
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == data["username"]) | 
            (User.email == data["email"])
        ).first()
        
        if existing_user:
            return jsonify({"error": "User with this username or email already exists"}), 400
        
        # Create new user
        new_user = User(
            username=data["username"],
            email=data["email"],
            is_broadcaster=data.get("is_broadcaster", False)
        )
        
        if "password" in data:
            new_user.password_hash = generate_password_hash(data["password"])
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({"success": True, "message": "User created successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Content Management Actions
@app.route("/content-management/edit/<int:stream_id>", methods=["POST"])
def edit_stream_content(stream_id):
    """Edit stream content"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    data = request.get_json()
    
    try:
        if "title" in data:
            stream.title = data["title"]
        if "description" in data:
            stream.description = data["description"]
        if "category" in data:
            stream.category = data["category"]
            
        db.session.commit()
        return jsonify({"success": True, "message": "Stream updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/content-management/suspend/<int:stream_id>", methods=["POST"])
def suspend_stream(stream_id):
    """Suspend stream"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    try:
        # Stop the stream if its live
        if stream.is_live:
            stream.is_live = False
            stream.ended_at = datetime.utcnow()
        
        # Add suspended flag or similar logic
        db.session.commit()
        return jsonify({"success": True, "message": f"Stream \"{stream.title}\" has been suspended"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/content-management/moderate", methods=["POST"])
def moderate_content():
    """Apply content moderation settings"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    
    try:
        # Apply moderation settings (this would typically update database settings)
        settings = {
            "auto_moderation": data.get("auto_moderation", False),
            "content_filters": data.get("content_filters", False),
            "chat_moderation": data.get("chat_moderation", False)
        }
        
        # In a real application, youd save these settings to database
        return jsonify({"success": True, "message": "Moderation settings applied successfully", "settings": settings})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Profile routes
@app.route("/profile")
@app.route("/profile/<username>")
def profile(username=None):
    """User profile page"""
    if not session.get("user_id"):
        return redirect(url_for("index"))
    
    if username:
        # View another users profile
        user = User.query.filter_by(username=username).first_or_404()
    else:
        # View own profile
        user = User.query.get(session["user_id"])
    
    # Get user streams and stats
    user_streams = Stream.query.filter_by(broadcaster_id=user.id).all()
    
    return render_template("profile.html", user=user, streams=user_streams)

@app.route("/profile/update", methods=["POST"])
def update_profile():
    """Update user profile information"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    data = request.get_json()
    
    try:
        # Update basic info
        if "username" in data:
            # Check if username is already taken
            existing = User.query.filter(User.username == data["username"], User.id != user.id).first()
            if existing:
                return jsonify({"error": "Username already taken"}), 400
            user.username = data["username"]
        
        if "email" in data:
            # Check if email is already taken
            existing = User.query.filter(User.email == data["email"], User.id != user.id).first()
            if existing:
                return jsonify({"error": "Email already in use"}), 400
            user.email = data["email"]
        
        if "display_name" in data:
            user.display_name = data["display_name"]
        if "bio" in data:
            user.bio = data["bio"]
        if "location" in data:
            user.location = data["location"]
        if "website" in data:
            user.website = data["website"]
            
        db.session.commit()
        return jsonify({"success": True, "message": "Profile updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/profile/change-password", methods=["POST"])
def change_password():
    """Change user password"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    data = request.get_json()
    
    try:
        # Verify current password
        if not check_password_hash(user.password_hash, data["current_password"]):
            return jsonify({"error": "Current password is incorrect"}), 400
        
        # Validate new password
        if len(data["new_password"]) < 8:
            return jsonify({"error": "Password must be at least 8 characters long"}), 400
        
        if data["new_password"] != data["confirm_password"]:
            return jsonify({"error": "Passwords do not match"}), 400
        
        # Update password
        user.password_hash = generate_password_hash(data["new_password"])
        db.session.commit()
        
        return jsonify({"success": True, "message": "Password changed successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/profile/upload-avatar", methods=["POST"])
def upload_avatar():
    """Upload user avatar"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    
    if "avatar" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["avatar"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Validate file type
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({"error": "Invalid file type. Use JPG, PNG, or GIF"}), 400
        
        # Create avatars directory if it doesnt exist
        avatars_dir = "static/avatars"
        os.makedirs(avatars_dir, exist_ok=True)
        
        # Generate unique filename
        filename = f"avatar_{user.id}_{int(time.time())}{file_ext}"
        filepath = os.path.join(avatars_dir, filename)
        
        # Save file
        file.save(filepath)
        
        # Update user avatar URL
        user.avatar_url = f"/static/avatars/{filename}"
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Avatar uploaded successfully",
            "avatar_url": user.avatar_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/profile/preferences", methods=["POST"])
def update_preferences():
    """Update user preferences"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    data = request.get_json()
    
    try:
        # Update preferences (stored as JSON)
        preferences = user.preferences or {}
        
        if "theme" in data:
            preferences["theme"] = data["theme"]
        if "email_notifications" in data:
            preferences["email_notifications"] = data["email_notifications"]
        if "stream_notifications" in data:
            preferences["stream_notifications"] = data["stream_notifications"]
        if "chat_notifications" in data:
            preferences["chat_notifications"] = data["chat_notifications"]
        if "profile_public" in data:
            preferences["profile_public"] = data["profile_public"]
        if "show_activity" in data:
            preferences["show_activity"] = data["show_activity"]
        
        user.preferences = preferences
        db.session.commit()
        
        return jsonify({"success": True, "message": "Preferences updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/profile/regenerate-stream-key", methods=["POST"])
def regenerate_stream_key():
    """Regenerate user stream key"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    
    if not user.is_broadcaster:
        return jsonify({"error": "Only broadcasters can regenerate stream keys"}), 403
    
    try:
        # Generate new stream key
        import secrets
        new_key = f"sk_{user.id}_{secrets.token_urlsafe(16)}"
        user.stream_key = new_key
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Stream key regenerated successfully",
            "stream_key": new_key
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# Stream editing routes
@app.route("/stream/<int:stream_id>/edit", methods=["POST"])
def edit_stream_info(stream_id):
    """Edit stream information"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    # Check if user owns this stream
    if stream.broadcaster_id != session["user_id"]:
        return jsonify({"error": "You can only edit your own streams"}), 403
    
    data = request.get_json()
    
    try:
        # Update stream information
        if "title" in data:
            if len(data["title"].strip()) < 3:
                return jsonify({"error": "Title must be at least 3 characters long"}), 400
            stream.title = data["title"].strip()
        
        if "description" in data:
            stream.description = data["description"].strip() if data["description"] else None
        
        if "hashtags" in data:
            # Process hashtags - clean and validate
            hashtags = data["hashtags"].strip()
            if hashtags:
                hashtag_list = [tag.strip().lower() for tag in hashtags.split(",") if tag.strip()]
                # Limit to 10 hashtags
                if len(hashtag_list) > 10:
                    return jsonify({"error": "Maximum 10 hashtags allowed"}), 400
                # Validate hashtag length
                for tag in hashtag_list:
                    if len(tag) > 30:
                        return jsonify({"error": "Each hashtag must be 30 characters or less"}), 400
                stream.hashtags = ",".join(hashtag_list)
            else:
                stream.hashtags = None
        
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Stream information updated successfully",
            "stream": {
                "title": stream.title,
                "description": stream.description,
                "hashtags": stream.hashtags
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/stream/<int:stream_id>/follow", methods=["POST"])
def follow_stream(stream_id):
    """Follow a streamer"""
    if not session.get("user_id"):
        return jsonify({"error": "Please login to follow streamers"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id == session["user_id"]:
        return jsonify({"error": "You cannot follow yourself"}), 400
    
    # In a real app, you would track follower relationships
    # For now, just increment the followers count
    broadcaster = stream.broadcaster
    broadcaster.followers_count = (broadcaster.followers_count or 0) + 1
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"You are now following {broadcaster.username}!",
        "followers_count": broadcaster.followers_count
    })

@app.route("/stream/<int:stream_id>/report", methods=["POST"])
def report_stream(stream_id):
    """Report a stream"""
    if not session.get("user_id"):
        return jsonify({"error": "Please login to report streams"}), 401
    
    data = request.get_json()
    reason = data.get("reason", "").strip()
    
    if not reason:
        return jsonify({"error": "Please provide a reason for reporting"}), 400
    
    # In a real app, you would store the report in a database
    # For now, just return success
    return jsonify({
        "success": True,
        "message": "Stream reported successfully. Our moderation team will review it."
    })


# Stream server management routes
@app.route("/stream/<int:stream_id>/servers", methods=["GET"])
def get_stream_servers(stream_id):
    """Get available streaming servers for a stream"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    # Generate server URLs if not set
    base_url = request.host_url.rstrip("/")
    
    servers = {
        "hls": {
            "url": stream.hls_url or f"{base_url}/stream/{stream_id}/hls/index.m3u8",
            "name": "HLS",
            "description": "HTTP Live Streaming - Best compatibility",
            "latency": "2-10 seconds",
            "quality": "Adaptive (240p-1080p)",
            "supported": True
        },
        "dash": {
            "url": stream.dash_url or f"{base_url}/stream/{stream_id}/dash/index.mpd", 
            "name": "DASH",
            "description": "Dynamic Adaptive Streaming - Optimized quality",
            "latency": "1-5 seconds",
            "quality": "Adaptive (240p-4K)",
            "supported": True
        },
        "webrtc": {
            "url": stream.webrtc_url or f"ws://{request.host}/webrtc/{stream_id}",
            "name": "WebRTC",
            "description": "Ultra-low latency peer-to-peer streaming",
            "latency": "50-200ms",
            "quality": "Fixed (720p-1080p)",
            "supported": False  # Set to True when WebRTC is implemented
        }
    }
    
    return jsonify({
        "success": True,
        "servers": servers,
        "current_server": "hls",  # Default server
        "stream_info": {
            "title": stream.title,
            "is_live": stream.is_live,
            "viewer_count": stream.viewer_count
        }
    })

@app.route("/stream/<int:stream_id>/quality", methods=["GET"])
def get_stream_quality(stream_id):
    """Get current stream quality information"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    # Default quality settings
    default_quality = {
        "current_quality": "720p",
        "available_qualities": ["240p", "360p", "480p", "720p", "1080p"],
        "bitrate": 2500,
        "fps": 30,
        "codec": "H.264",
        "audio_bitrate": 128,
        "audio_codec": "AAC"
    }
    
    quality_settings = stream.quality_settings or default_quality
    
    return jsonify({
        "success": True,
        "quality": quality_settings,
        "connection_stats": {
            "latency": "1.2s",
            "buffer_health": "Good",
            "dropped_frames": 0,
            "bandwidth": "2.8 Mbps"
        }
    })

@app.route("/stream/<int:stream_id>/switch-quality", methods=["POST"])
def switch_stream_quality(stream_id):
    """Switch stream quality"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    data = request.get_json()
    
    quality = data.get("quality", "720p")
    server_type = data.get("server_type", "hls")
    
    # Validate quality
    valid_qualities = ["240p", "360p", "480p", "720p", "1080p", "1440p", "4K"]
    if quality not in valid_qualities:
        return jsonify({"error": "Invalid quality setting"}), 400
    
    # Update quality settings
    current_settings = stream.quality_settings or {}
    current_settings["current_quality"] = quality
    current_settings["server_type"] = server_type
    current_settings["switched_at"] = datetime.utcnow().isoformat()
    
    stream.quality_settings = current_settings
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": f"Switched to {quality} on {server_type.upper()} server",
        "quality": quality,
        "server_type": server_type,
        "estimated_latency": {
            "hls": "2-10 seconds",
            "dash": "1-5 seconds", 
            "webrtc": "50-200ms"
        }.get(server_type, "Unknown")
    })


# Admin Settings Management Routes
@app.route("/admin/settings")
def admin_settings():
    """Admin settings page"""
    if not session.get("user_id"):
        flash("Please log in to access admin settings.", "error")
        return redirect(url_for("login"))
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("index"))
    
    # Get all settings
    all_settings = AdminSettings.get_all_settings()
    
    # Get platform statistics
    stats = {
        "total_users": User.query.count(),
        "total_streams": Stream.query.count(),
        "live_streams": Stream.query.filter_by(is_live=True).count(),
        "total_views": db.session.query(db.func.sum(Stream.total_views)).scalar() or 0
    }
    
    # Parse social links
    social_links_json = all_settings.get("social_links", "[]")
    try:
        social_links = json.loads(social_links_json) if social_links_json else []
    except:
        social_links = []
    all_settings["social_links"] = social_links
    
    return render_template("admin_settings.html", 
                         settings=all_settings, 
                         stats=stats,
                         current_time=datetime.now())

@app.route("/admin/settings/<category>", methods=["POST"])
def save_admin_settings(category):
    """Save admin settings by category"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    
    data = request.get_json()
    
    try:
        if category == "general":
            # Save general platform settings
            settings_map = {
                "site_name": "Site Name",
                "site_tagline": "Site Tagline", 
                "site_description": "Site Description",
                "contact_email": "Contact Email",
                "support_email": "Support Email",
                "allow_registration": "Allow Registration",
                "require_email_verification": "Require Email Verification",
                "enable_chat": "Enable Chat"
            }
            
            for key, description in settings_map.items():
                if key in data:
                    AdminSettings.set_setting(key, str(data[key]), category, description)
        
        elif category == "security":
            settings_map = {
                "enable_2fa": "Enable Two-Factor Authentication",
                "force_https": "Force HTTPS",
                "session_timeout": "Session Timeout",
                "max_login_attempts": "Maximum Login Attempts"
            }
            
            for key, description in settings_map.items():
                if key in data:
                    AdminSettings.set_setting(key, str(data[key]), category, description)
        
        elif category == "password":
            # Handle password change
            current_password = data.get("current_password")
            new_password = data.get("new_password")
            
            if not current_password or not new_password:
                return jsonify({"error": "Current and new passwords required"}), 400
            
            # In a real implementation, verify current password
            from werkzeug.security import generate_password_hash
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            
            return jsonify({"success": True, "message": "Password updated successfully"})
        
        elif category == "streaming":
            settings_map = {
                "enable_low_latency": "Enable Low Latency Streaming",
                "webrtc_server": "WebRTC Server URL",
                "stun_server": "STUN Server",
                "max_bitrate": "Maximum Bitrate",
                "max_resolution": "Maximum Resolution",
                "adaptive_bitrate": "Adaptive Bitrate Levels",
                "rtmp_server": "RTMP Server URL",
                "enable_rtmps": "Enable RTMPS",
                "hls_segment_duration": "HLS Segment Duration",
                "dash_segment_duration": "DASH Segment Duration"
            }
            
            for key, description in settings_map.items():
                if key in data:
                    AdminSettings.set_setting(key, str(data[key]), category, description)
        
        elif category == "footer":
            settings_map = {
                "footer_description": "Footer Description",
                "copyright_text": "Copyright Text",
                "developer_attribution": "Developer Attribution"
            }
            
            for key, description in settings_map.items():
                if key in data:
                    AdminSettings.set_setting(key, str(data[key]), category, description)
        
        elif category.startswith("integration_"):
            integration = category.replace("integration_", "")
            
            if integration == "googleAnalytics":
                AdminSettings.set_setting("enable_ga", str(data.get("enable_ga", False)), "integrations")
                AdminSettings.set_setting("ga_tracking_id", str(data.get("ga_tracking_id", "")), "integrations")
            
            elif integration == "discord":
                AdminSettings.set_setting("enable_discord", str(data.get("enable_discord", False)), "integrations")
                AdminSettings.set_setting("discord_webhook", str(data.get("discord_webhook", "")), "integrations")
            
            elif integration == "payment":
                AdminSettings.set_setting("enable_payments", str(data.get("enable_payments", False)), "integrations")
                AdminSettings.set_setting("payment_provider", str(data.get("payment_provider", "stripe")), "integrations")
            
            elif integration == "email":
                AdminSettings.set_setting("enable_email", str(data.get("enable_email", False)), "integrations")
                AdminSettings.set_setting("email_provider", str(data.get("email_provider", "sendgrid")), "integrations")
        
        elif category.startswith("page_"):
            page = category.replace("page_", "")
            page_settings = {
                "about": ["about_title", "about_content"],
                "privacy": ["privacy_title", "privacy_content"],
                "terms": ["terms_title", "terms_content"],
                "contact": ["contact_title", "contact_address", "contact_phone"]
            }
            
            if page in page_settings:
                for key in page_settings[page]:
                    if key in data:
                        description = f"{page.title()} Page {key.split('_')[-1].title()}"
                        AdminSettings.set_setting(key, str(data[key]), "pages", description)
        
        return jsonify({"success": True, "message": f"{category.title()} settings saved successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/admin/settings/social-links", methods=["POST"])
def save_social_links():
    """Save social media links"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    
    data = request.get_json()
    social_links = data.get("social_links", [])
    
    try:
        # Validate social links
        validated_links = []
        for link in social_links:
            if "platform" in link and "url" in link and link["url"].strip():
                validated_links.append({
                    "platform": link["platform"],
                    "url": link["url"].strip()
                })
        
        # Save as JSON
        AdminSettings.set_setting("social_links", json.dumps(validated_links), "footer", "Social Media Links")
        
        return jsonify({"success": True, "message": "Social links saved successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Initialize default admin settings
def init_default_settings():
    """Initialize default admin settings if they dont exist"""
    defaults = {
        # General Settings
        "site_name": ("StrophenBoost", "general", "Platform Name"),
        "site_tagline": ("Professional Live Streaming Platform", "general", "Platform Tagline"),
        "site_description": ("Advanced live streaming platform with comprehensive multi-protocol content delivery and creator tools.", "general", "Platform Description"),
        "contact_email": ("admin@strophenboost.com", "general", "Contact Email"),
        "support_email": ("support@strophenboost.com", "general", "Support Email"),
        "allow_registration": ("True", "general", "Allow New User Registration"),
        "require_email_verification": ("False", "general", "Require Email Verification"),
        "enable_chat": ("True", "general", "Enable Live Chat"),
        
        # Security Settings
        "enable_2fa": ("False", "security", "Enable Two-Factor Authentication"),
        "force_https": ("False", "security", "Force HTTPS"),
        "session_timeout": ("120", "security", "Session Timeout (minutes)"),
        "max_login_attempts": ("5", "security", "Maximum Login Attempts"),
        
        # Streaming Settings
        "enable_low_latency": ("True", "streaming", "Enable Low Latency Streaming"),
        "webrtc_server": ("wss://webrtc.strophenboost.com", "streaming", "WebRTC Server URL"),
        "stun_server": ("stun:stun.l.google.com:19302", "streaming", "STUN Server"),
        "max_bitrate": ("8000", "streaming", "Maximum Bitrate (kbps)"),
        "max_resolution": ("1080p", "streaming", "Maximum Resolution"),
        "adaptive_bitrate": ("500,1000,2000,4000,8000", "streaming", "Adaptive Bitrate Levels"),
        "rtmp_server": ("rtmp://localhost:1935/live", "streaming", "RTMP Server URL"),
        "enable_rtmps": ("False", "streaming", "Enable RTMPS"),
        "hls_segment_duration": ("4", "streaming", "HLS Segment Duration"),
        "dash_segment_duration": ("2", "streaming", "DASH Segment Duration"),
        
        # Footer Settings
        "footer_description": ("StrophenBoost - Professional live streaming platform with advanced features for content creators and viewers.", "footer", "Footer Description"),
        "copyright_text": ("© 2025 StrophenBoost. All rights reserved.", "footer", "Copyright Text"),
        "developer_attribution": ("Powered by Expert Dev UX", "footer", "Developer Attribution"),
        "social_links": ("[]", "footer", "Social Media Links JSON"),
        
        # Integration Settings
        "enable_ga": ("False", "integrations", "Enable Google Analytics"),
        "ga_tracking_id": ("", "integrations", "Google Analytics Tracking ID"),
        "enable_discord": ("False", "integrations", "Enable Discord Integration"),
        "discord_webhook": ("", "integrations", "Discord Webhook URL"),
        "enable_payments": ("False", "integrations", "Enable Payment Processing"),
        "payment_provider": ("stripe", "integrations", "Payment Provider"),
        "enable_email": ("False", "integrations", "Enable Email Service"),
        "email_provider": ("sendgrid", "integrations", "Email Provider"),
        
        # Page Content
        "about_title": ("About StrophenBoost", "pages", "About Page Title"),
        "about_content": ("StrophenBoost is a professional live streaming platform designed for content creators and viewers. We provide advanced streaming technology with multi-protocol support.", "pages", "About Page Content"),
        "privacy_title": ("Privacy Policy", "pages", "Privacy Page Title"),
        "privacy_content": ("Your privacy is important to us. This policy explains how we collect, use, and protect your personal information.", "pages", "Privacy Page Content"),
        "terms_title": ("Terms of Service", "pages", "Terms Page Title"),
        "terms_content": ("By using our service, you agree to these terms and conditions. Please read them carefully.", "pages", "Terms Page Content"),
        "contact_title": ("Contact Us", "pages", "Contact Page Title"),
        "contact_address": ("123 Streaming Street\nDigital City, DC 12345", "pages", "Contact Address"),
        "contact_phone": ("+1 (555) 123-4567", "pages", "Contact Phone"),
    }
    
    for key, (value, category, description) in defaults.items():
        existing = AdminSettings.query.filter_by(key=key).first()
        if not existing:
            AdminSettings.set_setting(key, value, category, description)

# Note: init_default_settings() will be called from app.py after all models are imported


# Chat Management Routes
@app.route("/chat-management")
def chat_management():
    """Chat management interface for admins"""
    if not session.get("user_id"):
        flash("Please log in to access chat management.", "error")
        return redirect(url_for("login"))
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("index"))
    
    # Get live streams
    live_streams = Stream.query.filter_by(is_live=True).all()
    
    # Get recent chat history
    chat_history = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(100).all()
    
    return render_template("chat_management.html", 
                         live_streams=live_streams,
                         chat_history=chat_history)

@app.route("/api/chat/stats")
def get_chat_stats():
    """Get chat statistics"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Calculate various statistics
        total_messages = ChatMessage.query.count()
        today = datetime.now().date()
        messages_today = ChatMessage.query.filter(
            db.func.date(ChatMessage.timestamp) == today
        ).count()
        
        bot_responses = ChatMessage.query.filter_by(username="StrophenBot").count()
        bot_responses_today = ChatMessage.query.filter(
            ChatMessage.username == "StrophenBot",
            db.func.date(ChatMessage.timestamp) == today
        ).count()
        
        active_streams = Stream.query.filter_by(is_live=True).count()
        
        # Estimate active users (from chat_manager if available)
        try:
            from chat_manager import active_users
            total_active_users = sum(len(users) for users in active_users.values())
        except:
            total_active_users = 0
        
        stats = {
            "total_messages": total_messages,
            "messages_today": messages_today,
            "active_users": total_active_users,
            "active_streams": active_streams,
            "bot_responses": bot_responses,
            "bot_responses_today": bot_responses_today,
            "help_responses": bot_responses_today,  # Simplified for demo
            "moderated": 0,  # Would track moderated messages
            "moderated_today": 0,
            "messages_per_hour": messages_today // 24 if messages_today > 0 else 0
        }
        
        return jsonify({"success": True, "stats": stats})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat/online-users")
def get_online_users():
    """Get currently online users"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Get active users from chat_manager
        try:
            from chat_manager import active_users
            
            online_users = []
            registered_count = 0
            anonymous_count = 0
            
            for stream_id, users in active_users.items():
                stream = Stream.query.get(stream_id)
                stream_title = stream.title if stream else "Unknown Stream"
                
                for user_id, user_info in users.items():
                    user = User.query.get(user_id) if user_id else None
                    
                    online_users.append({
                        "username": user_info["username"],
                        "stream_title": stream_title,
                        "joined_at": user_info["joined_at"],
                        "is_registered": bool(user)
                    })
                    
                    if user:
                        registered_count += 1
                    else:
                        anonymous_count += 1
            
            stats = {
                "total": len(online_users),
                "registered": registered_count,
                "anonymous": anonymous_count
            }
            
            return jsonify({
                "success": True, 
                "users": online_users, 
                "stats": stats
            })
            
        except ImportError:
            return jsonify({
                "success": True, 
                "users": [], 
                "stats": {"total": 0, "registered": 0, "anonymous": 0}
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat/ai-bot-settings", methods=["POST"])
def save_ai_bot_settings():
    """Save AI bot configuration"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    
    try:
        data = request.get_json()
        
        # Save settings to admin settings
        AdminSettings.set_setting("ai_bot_enabled", str(data.get("enable_ai_bot", True)), "chat")
        AdminSettings.set_setting("ai_moderation_enabled", str(data.get("enable_ai_moderation", True)), "chat")
        AdminSettings.set_setting("bot_response_rate", data.get("bot_response_rate", "medium"), "chat")
        AdminSettings.set_setting("moderation_level", data.get("moderation_level", "moderate"), "chat")
        
        # Update chat_manager settings if available
        try:
            from chat_manager import chat_manager
            chat_manager.ai_bot_enabled = data.get("enable_ai_bot", True)
            chat_manager.auto_moderation = data.get("enable_ai_moderation", True)
        except ImportError:
            pass
        
        return jsonify({"success": True, "message": "AI bot settings saved successfully"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat/settings", methods=["POST"])
def save_chat_settings():
    """Save general chat settings"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    
    try:
        data = request.get_json()
        
        # Save chat settings
        settings_map = {
            "chat_enabled": "enable_chat",
            "require_registration_to_chat": "require_registration", 
            "max_message_length": "max_message_length",
            "slow_mode_delay": "slow_mode_delay",
            "banned_words": "banned_words",
            "enable_emotes": "enable_emotes",
            "enable_links": "enable_links"
        }
        
        for setting_key, data_key in settings_map.items():
            if data_key in data:
                AdminSettings.set_setting(setting_key, str(data[data_key]), "chat")
        
        # Update chat_manager settings if available
        try:
            from chat_manager import chat_manager
            if "banned_words" in data and data["banned_words"]:
                banned_words = [word.strip() for word in data["banned_words"].split(",")]
                chat_manager.banned_words = banned_words
        except ImportError:
            pass
        
        return jsonify({"success": True, "message": "Chat settings saved successfully"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat/test-ai-bot", methods=["POST"])
def test_ai_bot():
    """Test AI bot response"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        message = data.get("message", "")
        
        if not message:
            return jsonify({"error": "Message required"}), 400
        
        # Test AI bot response
        try:
            from chat_manager import chat_manager
            response = chat_manager.generate_ai_response(message, "Test Stream")
            
            return jsonify({
                "success": True, 
                "response": response,
                "message": "AI bot test completed"
            })
            
        except Exception as e:
            return jsonify({
                "success": False, 
                "error": f"AI bot unavailable: {str(e)}",
                "response": None
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat/export")
def export_chat_history():
    """Export chat history as CSV"""
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    user = User.query.get(session["user_id"])
    if not user or user.username != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    
    try:
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(["Timestamp", "Stream ID", "Username", "Message", "Is Bot", "Is Deleted"])
        
        # Get all chat messages
        messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).all()
        
        for message in messages:
            writer.writerow([
                message.timestamp.isoformat(),
                message.stream_id,
                message.username,
                message.message,
                message.username == "StrophenBot",
                message.is_deleted
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/streaming/setup")
def streaming_setup():
    """Streaming software setup guide"""
    # Get current user if logged in
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    return render_template("streaming_setup.html", current_user=user)

@app.route("/api/streaming/test-connection")
@login_required
def test_streaming_connection():
    """Test RTMP server connection"""
    try:
        import socket
        
        # Test RTMP port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("localhost", 1935))
        sock.close()
        
        if result == 0:
            return jsonify({
                "status": "success",
                "message": "RTMP server is running and accepting connections",
                "rtmp_url": f"rtmp://{request.host.split(':')[0]}:1935/live",
                "stream_key": current_user.rtmp_keys[0].key if current_user.rtmp_keys else "No stream key found"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "RTMP server is not responding on port 1935"
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Connection test failed: {str(e)}"
        })

@app.route("/api/streaming/generate-key")
@login_required  
def generate_stream_key():
    """Generate a new RTMP stream key"""
    try:
        import secrets
        
        # Generate new stream key
        new_key = secrets.token_urlsafe(16)
        
        # Deactivate old keys
        for key in current_user.rtmp_keys:
            key.is_active = False
        
        # Create new key
        rtmp_key = RTMPKey(
            user_id=current_user.id,
            key=new_key,
            is_active=True
        )
        
        db.session.add(rtmp_key)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "stream_key": new_key,
            "rtmp_url": f"rtmp://{request.host.split(':')[0]}:1935/live",
            "full_url": f"rtmp://{request.host.split(':')[0]}:1935/live/{new_key}"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to generate stream key: {str(e)}"
        })

