// Real-time Chat System for StrophenBoost
let socket;
let isConnectedToChat = false;
let currentStreamId = null;

function initializeChat(streamId) {
    currentStreamId = streamId;
    
    if (typeof io === 'undefined') {
        console.error('Socket.IO not loaded');
        showChatError('Chat unavailable - Socket.IO not loaded');
        return;
    }
    
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to chat server');
        showChatStatus('Connected to chat!', 'success');
        
        // Join the stream chat room
        socket.emit('join_stream_chat', {stream_id: streamId});
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from chat server');
        isConnectedToChat = false;
        updateChatUserCount(0);
        showChatError('Disconnected from chat');
    });
    
    socket.on('join_success', function(data) {
        console.log('Successfully joined chat:', data);
        isConnectedToChat = true;
        updateChatUserCount(data.user_count || 0);
        hideChatPlaceholder();
    });
    
    socket.on('chat_history', function(data) {
        console.log('Received chat history:', data);
        
        if (data.messages && data.messages.length > 0) {
            hideChatPlaceholder();
            
            data.messages.forEach(message => {
                addChatMessage(message.username, message.message, message.timestamp, message.is_bot);
            });
        } else {
            showChatPlaceholder('No messages yet. Start the conversation!');
        }
    });
    
    socket.on('new_message', function(data) {
        console.log('New message:', data);
        addChatMessage(data.username, data.message, data.timestamp, data.is_bot);
        hideChatPlaceholder();
    });
    
    socket.on('user_joined', function(data) {
        console.log('User joined:', data);
        updateChatUserCount(data.user_count || 0);
        addSystemMessage(`${data.username} joined the chat`);
    });
    
    socket.on('user_left', function(data) {
        console.log('User left:', data);
        updateChatUserCount(data.user_count || 0);
        addSystemMessage(`${data.username} left the chat`);
    });
    
    socket.on('message_blocked', function(data) {
        showAlert('warning', `Message blocked: ${data.reason}`);
    });
    
    socket.on('message_deleted', function(data) {
        removeMessage(data.message_id);
    });
    
    socket.on('error', function(data) {
        console.error('Chat error:', data);
        showAlert('danger', `Chat error: ${data.message}`);
    });
    
    // Enable enter key for sending messages
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
}

function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    if (!isConnectedToChat) {
        showAlert('warning', 'Not connected to chat. Please refresh the page.');
        return;
    }
    
    if (message.length > 500) {
        showAlert('warning', 'Message too long (max 500 characters)');
        return;
    }
    
    // Send message via WebSocket
    socket.emit('send_message', {
        stream_id: currentStreamId,
        message: message
    });
    
    // Clear input
    input.value = '';
}

function addChatMessage(username, message, timestamp, isBot = false) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;
    
    hideChatPlaceholder();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message mb-2';
    messageDiv.setAttribute('data-timestamp', timestamp);
    
    const time = new Date(timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const avatarClass = isBot ? 'bg-success' : 'bg-primary';
    const nameClass = isBot ? 'text-success' : 'text-primary';
    const iconClass = isBot ? 'fas fa-robot' : 'fas fa-user';
    
    messageDiv.innerHTML = `
        <div class="d-flex align-items-start gap-2">
            <div class="flex-shrink-0">
                <div class="avatar-sm ${avatarClass} rounded-circle d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                    <i class="${iconClass} text-white" style="font-size: 12px;"></i>
                </div>
            </div>
            <div class="flex-grow-1">
                <div class="d-flex align-items-center gap-2 mb-1">
                    <strong class="${nameClass}" style="font-size: 14px;">${username}</strong>
                    <small class="text-muted" style="font-size: 11px;">${time}</small>
                </div>
                <p class="mb-0" style="font-size: 13px; line-height: 1.4;">${escapeHtml(message)}</p>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    
    // Auto-scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Limit messages (keep last 100)
    const messages = messagesContainer.querySelectorAll('.chat-message');
    if (messages.length > 100) {
        messages[0].remove();
    }
}

function addSystemMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'system-message text-center mb-2';
    messageDiv.innerHTML = `
        <small class="text-muted fst-italic" style="font-size: 11px;">
            <i class="fas fa-info-circle me-1"></i>${escapeHtml(message)}
        </small>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeMessage(messageId) {
    const messageElements = document.querySelectorAll('.chat-message');
    messageElements.forEach(element => {
        if (element.dataset.messageId === messageId) {
            element.classList.add('text-muted');
            element.querySelector('p').innerHTML = '<em>[Message deleted]</em>';
        }
    });
}

function updateChatUserCount(count) {
    const userCountElement = document.getElementById('chatUserCount');
    if (userCountElement) {
        userCountElement.textContent = count;
    }
}

function showChatPlaceholder(message) {
    const placeholder = document.getElementById('chatPlaceholder');
    if (placeholder) {
        placeholder.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-comments fa-2x mb-2"></i>
                <p class="mb-0">${message}</p>
            </div>
        `;
        placeholder.style.display = 'block';
    }
}

function hideChatPlaceholder() {
    const placeholder = document.getElementById('chatPlaceholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
}

function showChatStatus(message, type = 'info') {
    const placeholder = document.getElementById('chatPlaceholder');
    if (placeholder) {
        const iconClass = type === 'success' ? 'fas fa-check-circle' : 
                         type === 'error' ? 'fas fa-exclamation-triangle' : 'fas fa-info-circle';
        const textClass = type === 'success' ? 'text-success' : 
                         type === 'error' ? 'text-danger' : 'text-info';
        
        placeholder.innerHTML = `
            <div class="text-center ${textClass} py-4">
                <i class="${iconClass} fa-2x mb-2"></i>
                <p class="mb-0">${message}</p>
            </div>
        `;
        placeholder.style.display = 'block';
    }
}

function showChatError(message) {
    showChatStatus(message, 'error');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Alert helper function (if not already defined)
if (typeof showAlert === 'undefined') {
    function showAlert(type, message) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
}

// Export functions for global access
window.initializeChat = initializeChat;
window.sendChatMessage = sendChatMessage;