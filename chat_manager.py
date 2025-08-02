import os
import json
import logging
from datetime import datetime, timezone
from flask import session
from flask_socketio import emit, join_room, leave_room, disconnect
from app import db, socketio
from models import User, Stream, ChatMessage, AdminSettings

# Import Gemini AI functionality
try:
    from google import genai
    from google.genai import types
    
    # Initialize Gemini client only if API key is available
    if os.environ.get("GEMINI_API_KEY"):
        gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
        gemini_client = None
        print("Warning: GEMINI_API_KEY not found. AI bot features disabled.")
except ImportError:
    GEMINI_AVAILABLE = False
    gemini_client = None
    print("Warning: Gemini AI not available. Install google-genai package for AI bot features.")

# Chat room management
active_users = {}  # {room_id: {user_id: {username, joined_at}}}
chat_stats = {}    # {room_id: {total_messages, active_users}}

class ChatManager:
    def __init__(self):
        self.banned_words = [
            "spam", "scam", "fake", "bot", "hack", "cheat", 
            # Add more moderation words as needed
        ]
        self.ai_bot_enabled = True
        self.auto_moderation = True
    
    def is_message_appropriate(self, message):
        """Check if message contains banned words or inappropriate content"""
        message_lower = message.lower()
        return not any(word in message_lower for word in self.banned_words)
    
    def moderate_with_ai(self, message, username):
        """Use Gemini AI to moderate chat messages"""
        if not GEMINI_AVAILABLE or not gemini_client:
            return True, ""
        
        try:
            # Moderation prompt for Gemini
            moderation_prompt = f"""
            Analyze this chat message for inappropriate content, spam, or toxicity:
            
            Message: "{message}"
            User: {username}
            
            Respond with JSON in this format:
            {{
                "is_appropriate": true/false,
                "reason": "explanation if inappropriate",
                "suggested_action": "allow/warn/timeout/ban"
            }}
            
            Consider:
            - Spam or repetitive content
            - Harassment or toxic behavior
            - Inappropriate language
            - Off-topic promotional content
            """
            
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=moderation_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                result = json.loads(response.text)
                return result.get("is_appropriate", True), result.get("reason", "")
            
        except Exception as e:
            logging.error(f"AI moderation error: {e}")
        
        return True, ""
    
    def generate_ai_response(self, message, stream_title=""):
        """Generate AI bot response for user questions"""
        if not GEMINI_AVAILABLE or not gemini_client:
            return None
        
        try:
            # Check if message is asking a question or needs help
            question_keywords = ["how", "what", "help", "support", "?", "streaming", "rtmp", "obs"]
            if not any(keyword in message.lower() for keyword in question_keywords):
                return None
            
            ai_prompt = f"""
            You are StrophenBot, a helpful AI assistant for StrophenBoost streaming platform.
            A user in the chat asked: "{message}"
            
            Current stream: {stream_title}
            
            Provide a helpful, concise response (max 150 characters) about:
            - Streaming setup and RTMP configuration
            - Platform features and navigation
            - Basic troubleshooting
            - General support
            
            Keep responses friendly, helpful, and brief for chat format.
            If you can't help with the specific question, suggest contacting support.
            """
            
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=ai_prompt
            )
            
            if response.text and len(response.text) <= 200:
                return response.text.strip()
            
        except Exception as e:
            logging.error(f"AI response generation error: {e}")
        
        return None

# Initialize chat manager
chat_manager = ChatManager()

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    """Handle user connection to chat"""
    user_id = session.get('user_id')
    username = session.get('username', 'Anonymous')
    
    if user_id:
        emit('connection_status', {
            'status': 'connected',
            'user_id': user_id,
            'username': username,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        logging.info(f"User {username} connected to chat")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle user disconnection from chat"""
    user_id = session.get('user_id')
    username = session.get('username', 'Anonymous')
    
    # Remove user from all active chat rooms
    for room_id in list(active_users.keys()):
        if user_id in active_users[room_id]:
            del active_users[room_id][user_id]
            if not active_users[room_id]:
                del active_users[room_id]
            
            # Notify room about user leaving
            emit('user_left', {
                'username': username,
                'user_count': len(active_users.get(room_id, {}))
            }, room=f"stream_{room_id}")
    
    logging.info(f"User {username} disconnected from chat")

@socketio.on('join_stream_chat')
def handle_join_stream_chat(data):
    """Handle user joining a stream chat room"""
    stream_id = data.get('stream_id')
    user_id = session.get('user_id')
    username = session.get('username', 'Anonymous')
    
    if not stream_id:
        emit('error', {'message': 'Stream ID required'})
        return
    
    # Verify stream exists
    stream = Stream.query.get(stream_id)
    if not stream:
        emit('error', {'message': 'Stream not found'})
        return
    
    room_name = f"stream_{stream_id}"
    join_room(room_name)
    
    # Track active users
    if stream_id not in active_users:
        active_users[stream_id] = {}
        chat_stats[stream_id] = {'total_messages': 0, 'active_users': 0}
    
    active_users[stream_id][user_id] = {
        'username': username,
        'joined_at': datetime.now(timezone.utc).isoformat()
    }
    
    chat_stats[stream_id]['active_users'] = len(active_users[stream_id])
    
    # Notify room about new user
    emit('user_joined', {
        'username': username,
        'user_count': len(active_users[stream_id]),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=room_name)
    
    # Send recent chat history
    recent_messages = ChatMessage.query.filter_by(stream_id=stream_id, is_deleted=False)\
                                     .order_by(ChatMessage.timestamp.desc())\
                                     .limit(50).all()
    
    emit('chat_history', {
        'messages': [{
            'id': msg.id,
            'username': msg.username,
            'message': msg.message,
            'timestamp': msg.timestamp.isoformat(),
            'is_bot': msg.username == 'StrophenBot'
        } for msg in reversed(recent_messages)]
    })
    
    emit('join_success', {
        'stream_id': stream_id,
        'stream_title': stream.title,
        'user_count': len(active_users[stream_id])
    })

@socketio.on('leave_stream_chat')
def handle_leave_stream_chat(data):
    """Handle user leaving a stream chat room"""
    stream_id = data.get('stream_id')
    user_id = session.get('user_id')
    username = session.get('username', 'Anonymous')
    
    if not stream_id:
        return
    
    room_name = f"stream_{stream_id}"
    leave_room(room_name)
    
    # Remove user from tracking
    if stream_id in active_users and user_id in active_users[stream_id]:
        del active_users[stream_id][user_id]
        
        if not active_users[stream_id]:
            del active_users[stream_id]
            if stream_id in chat_stats:
                del chat_stats[stream_id]
        else:
            chat_stats[stream_id]['active_users'] = len(active_users[stream_id])
            
            # Notify room about user leaving
            emit('user_left', {
                'username': username,
                'user_count': len(active_users[stream_id])
            }, room=room_name)

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a chat message"""
    stream_id = data.get('stream_id')
    message = data.get('message', '').strip()
    user_id = session.get('user_id')
    username = session.get('username', 'Anonymous')
    
    if not stream_id or not message:
        emit('error', {'message': 'Stream ID and message required'})
        return
    
    if len(message) > 500:
        emit('error', {'message': 'Message too long (max 500 characters)'})
        return
    
    # Verify user is in the chat room
    if stream_id not in active_users or user_id not in active_users[stream_id]:
        emit('error', {'message': 'You must join the chat first'})
        return
    
    # Basic moderation
    if not chat_manager.is_message_appropriate(message):
        emit('message_blocked', {'reason': 'Message contains inappropriate content'})
        return
    
    # AI moderation (if available)
    if chat_manager.auto_moderation:
        is_appropriate, reason = chat_manager.moderate_with_ai(message, username)
        if not is_appropriate:
            emit('message_blocked', {'reason': reason or 'Message blocked by AI moderation'})
            return
    
    # Save message to database
    try:
        chat_message = ChatMessage(
            stream_id=stream_id,
            user_id=user_id,
            username=username,
            message=message,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(chat_message)
        db.session.commit()
        
        # Update chat stats
        if stream_id in chat_stats:
            chat_stats[stream_id]['total_messages'] += 1
        
        # Broadcast message to room
        room_name = f"stream_{stream_id}"
        message_data = {
            'id': chat_message.id,
            'username': username,
            'message': message,
            'timestamp': chat_message.timestamp.isoformat(),
            'user_id': user_id,
            'is_bot': False
        }
        
        emit('new_message', message_data, room=room_name)
        
        # Generate AI response if appropriate
        if chat_manager.ai_bot_enabled:
            stream = Stream.query.get(stream_id)
            ai_response = chat_manager.generate_ai_response(
                message, 
                stream.title if stream else ""
            )
            
            if ai_response:
                # Add AI bot message
                bot_message = ChatMessage(
                    stream_id=stream_id,
                    user_id=None,
                    username='StrophenBot',
                    message=ai_response,
                    timestamp=datetime.now(timezone.utc)
                )
                db.session.add(bot_message)
                db.session.commit()
                
                # Broadcast bot response
                bot_message_data = {
                    'id': bot_message.id,
                    'username': 'StrophenBot',
                    'message': ai_response,
                    'timestamp': bot_message.timestamp.isoformat(),
                    'user_id': None,
                    'is_bot': True
                }
                
                emit('new_message', bot_message_data, room=room_name)
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving chat message: {e}")
        emit('error', {'message': 'Failed to send message'})

@socketio.on('delete_message')
def handle_delete_message(data):
    """Handle message deletion (moderators only)"""
    message_id = data.get('message_id')
    user_id = session.get('user_id')
    username = session.get('username')
    
    if not message_id:
        emit('error', {'message': 'Message ID required'})
        return
    
    # Check if user is admin or moderator
    user = User.query.get(user_id)
    if not user or username != 'admin':  # Extend this for other moderators
        emit('error', {'message': 'Insufficient permissions'})
        return
    
    try:
        message = ChatMessage.query.get(message_id)
        if message:
            message.is_deleted = True
            db.session.commit()
            
            # Notify room about deleted message
            emit('message_deleted', {
                'message_id': message_id
            }, room=f"stream_{message.stream_id}")
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting message: {e}")
        emit('error', {'message': 'Failed to delete message'})

@socketio.on('get_chat_stats')
def handle_get_chat_stats(data):
    """Get chat statistics for a stream"""
    stream_id = data.get('stream_id')
    
    if not stream_id:
        emit('error', {'message': 'Stream ID required'})
        return
    
    stats = chat_stats.get(stream_id, {'total_messages': 0, 'active_users': 0})
    active_user_list = [
        {'username': user_info['username'], 'joined_at': user_info['joined_at']}
        for user_info in active_users.get(stream_id, {}).values()
    ]
    
    emit('chat_stats', {
        'stream_id': stream_id,
        'total_messages': stats['total_messages'],
        'active_users_count': stats['active_users'],
        'active_users': active_user_list
    })