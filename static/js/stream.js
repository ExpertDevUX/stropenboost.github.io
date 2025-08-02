/**
 * StrophenBoost Stream JavaScript
 * Handles stream viewing, player controls, and real-time features
 */

// Global variables
let videoPlayer = null;
let socket = null;
let currentStreamId = null;
let isConnected = false;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeStreamPage();
});

/**
 * Initialize stream page functionality
 */
function initializeStreamPage() {
    // Socket.IO temporarily disabled for performance
    // socket = io();
    
    // Socket events temporarily disabled
    // setupSocketEvents();
    
    // Initialize video player if present
    const videoElement = document.getElementById('streamPlayer');
    if (videoElement) {
        initializeVideoPlayer();
    }
    
    // Setup stream card interactions
    setupStreamCardInteractions();
    
    // Setup embed functionality
    setupEmbedFunctionality();
}

/**
 * Initialize Video.js player
 */
function initializeVideoPlayer() {
    const videoElement = document.getElementById('streamPlayer');
    if (!videoElement) return;
    
    // Video.js configuration
    const playerOptions = {
        fluid: true,
        responsive: true,
        playbackRates: [0.5, 1, 1.25, 1.5, 2],
        controls: true,
        autoplay: false,
        muted: false,
        preload: 'auto',
        techOrder: ['html5'],
        html5: {
            hls: {
                enableLowInitialPlaylist: true,
                smoothQualityChange: true,
                overrideNative: true
            }
        },
        plugins: {
            // Add any Video.js plugins here
        }
    };
    
    // Initialize player
    videoPlayer = videojs('streamPlayer', playerOptions);
    
    // Setup player event listeners
    setupPlayerEvents();
    
    console.log('Video player initialized');
}

/**
 * Setup Video.js player event listeners
 */
function setupPlayerEvents() {
    if (!videoPlayer) return;
    
    videoPlayer.ready(() => {
        console.log('Player is ready');
        
        // Auto-start playback if stream is live
        if (window.isLive) {
            setTimeout(() => {
                videoPlayer.play().catch(error => {
                    console.log('Autoplay prevented:', error);
                });
            }, 1000);
        }
    });
    
    videoPlayer.on('loadstart', () => {
        console.log('Started loading');
        showPlayerStatus('Loading stream...');
    });
    
    videoPlayer.on('canplay', () => {
        console.log('Can start playing');
        hidePlayerStatus();
    });
    
    videoPlayer.on('play', () => {
        console.log('Playback started');
        hidePlayerStatus();
    });
    
    videoPlayer.on('pause', () => {
        console.log('Playback paused');
    });
    
    videoPlayer.on('ended', () => {
        console.log('Playback ended');
        showPlayerStatus('Stream has ended');
    });
    
    videoPlayer.on('error', (error) => {
        console.error('Player error:', error);
        handlePlayerError(error);
    });
    
    videoPlayer.on('waiting', () => {
        console.log('Buffering...');
        showPlayerStatus('Buffering...');
    });
    
    videoPlayer.on('playing', () => {
        console.log('Playing after buffering');
        hidePlayerStatus();
    });
    
    // Quality change detection
    videoPlayer.on('loadedmetadata', () => {
        console.log('Metadata loaded');
        detectStreamQuality();
    });
}

/**
 * Setup Socket.IO event listeners
 */
function setupSocketEvents() {
    socket.on('connect', () => {
        console.log('Connected to server');
        isConnected = true;
        
        // Join stream room if we're on a stream page
        if (window.streamId) {
            joinStreamRoom(window.streamId);
        }
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        isConnected = false;
    });
    
    socket.on('viewer_update', (data) => {
        updateViewerCount(data.count);
    });
    
    socket.on('stream_status_update', (data) => {
        handleStreamStatusUpdate(data);
    });
    
    socket.on('user_joined', (data) => {
        console.log('User joined:', data.username);
    });
    
    socket.on('user_left', (data) => {
        console.log('User left:', data.username);
    });
}

/**
 * Join stream room for real-time updates
 */
function joinStreamRoom(streamId) {
    currentStreamId = streamId;
    const username = window.sessionUsername || 'Anonymous_' + Math.random().toString(36).substr(2, 9);
    
    socket.emit('join_stream', {
        stream_id: streamId,
        username: username
    });
    
    console.log('Joined stream room:', streamId);
}

/**
 * Leave stream room
 */
function leaveStreamRoom() {
    if (currentStreamId) {
        const username = window.sessionUsername || 'Anonymous';
        
        socket.emit('leave_stream', {
            stream_id: currentStreamId,
            username: username
        });
        
        console.log('Left stream room:', currentStreamId);
        currentStreamId = null;
    }
}

/**
 * Update viewer count display
 */
function updateViewerCount(count) {
    const viewerCountElements = document.querySelectorAll('#viewerCount, .viewer-count');
    viewerCountElements.forEach(element => {
        element.textContent = count;
    });
}

/**
 * Handle stream status updates
 */
function handleStreamStatusUpdate(data) {
    if (data.stream_id === currentStreamId) {
        if (data.status === 'offline' && videoPlayer) {
            // Stream went offline
            videoPlayer.pause();
            showPlayerStatus('Stream has ended');
            
            // Show notification
            showNotification('Stream has ended', 'info');
        } else if (data.status === 'live' && !window.isLive) {
            // Stream came online
            showNotification('Stream is now live!', 'success');
            
            // Reload page to get live player
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    }
}

/**
 * Setup stream card interactions for listing page
 */
function setupStreamCardInteractions() {
    const streamCards = document.querySelectorAll('.stream-card');
    
    streamCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on buttons
            if (e.target.closest('.btn')) {
                return;
            }
            
            const streamLink = card.querySelector('a[href*="/stream/"]');
            if (streamLink) {
                window.location.href = streamLink.href;
            }
        });
        
        // Add hover effects
        card.addEventListener('mouseenter', function() {
            card.style.transform = 'translateY(-5px)';
            card.style.transition = 'transform 0.3s ease';
        });
        
        card.addEventListener('mouseleave', function() {
            card.style.transform = 'translateY(0)';
        });
    });
}

/**
 * Setup embed functionality
 */
function setupEmbedFunctionality() {
    // This will be called from the template if needed
}

/**
 * Show embed code modal
 */
function showEmbedCode(streamId) {
    fetch(`/embed_code/${streamId}`)
        .then(response => response.json())
        .then(data => {
            if (data.iframe) {
                document.getElementById('embedCode').value = data.iframe;
                document.getElementById('embedUrl').value = data.direct_url;
                
                const embedModal = new bootstrap.Modal(document.getElementById('embedModal'));
                embedModal.show();
            } else {
                showNotification('Failed to generate embed code', 'error');
            }
        })
        .catch(error => {
            console.error('Error getting embed code:', error);
            showNotification('Failed to load embed code', 'error');
        });
}

/**
 * Copy embed code to clipboard
 */
function copyEmbedCode() {
    const embedCode = document.getElementById('embedCode').value;
    copyToClipboard(embedCode);
}

/**
 * Copy embed URL to clipboard
 */
function copyEmbedUrl() {
    const embedUrl = document.getElementById('embedUrl').value;
    copyToClipboard(embedUrl);
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
    } catch (error) {
        console.error('Failed to copy:', error);
        
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showNotification('Copied to clipboard!', 'success');
        } catch (fallbackError) {
            showNotification('Failed to copy to clipboard', 'error');
        }
        
        document.body.removeChild(textArea);
    }
}

/**
 * Show player status message
 */
function showPlayerStatus(message) {
    let statusElement = document.getElementById('playerStatus');
    
    if (!statusElement) {
        statusElement = document.createElement('div');
        statusElement.id = 'playerStatus';
        statusElement.className = 'position-absolute top-50 start-50 translate-middle text-center text-white';
        statusElement.style.cssText = `
            z-index: 1000;
            background: rgba(0, 0, 0, 0.8);
            padding: 1rem 2rem;
            border-radius: 0.5rem;
            font-size: 1.1rem;
        `;
        
        const videoContainer = document.querySelector('.video-js') || document.querySelector('#streamPlayer');
        if (videoContainer) {
            videoContainer.parentNode.style.position = 'relative';
            videoContainer.parentNode.appendChild(statusElement);
        }
    }
    
    statusElement.innerHTML = `
        <i class="fas fa-circle-notch fa-spin me-2"></i>
        ${message}
    `;
    statusElement.style.display = 'block';
}

/**
 * Hide player status message
 */
function hidePlayerStatus() {
    const statusElement = document.getElementById('playerStatus');
    if (statusElement) {
        statusElement.style.display = 'none';
    }
}

/**
 * Handle player errors
 */
function handlePlayerError(error) {
    console.error('Player error details:', error);
    
    let errorMessage = 'An error occurred while playing the stream';
    
    if (videoPlayer) {
        const playerError = videoPlayer.error();
        if (playerError) {
            switch (playerError.code) {
                case 1:
                    errorMessage = 'Stream aborted';
                    break;
                case 2:
                    errorMessage = 'Network error';
                    break;
                case 3:
                    errorMessage = 'Stream format not supported';
                    break;
                case 4:
                    errorMessage = 'Stream not found';
                    break;
                default:
                    errorMessage = 'Unknown playback error';
            }
        }
    }
    
    showPlayerStatus(`Error: ${errorMessage}`);
    showNotification(errorMessage, 'error');
    
    // Try to reload stream after a delay
    setTimeout(() => {
        if (videoPlayer && window.isLive) {
            videoPlayer.load();
        }
    }, 5000);
}

/**
 * Detect stream quality
 */
function detectStreamQuality() {
    if (!videoPlayer) return;
    
    const videoWidth = videoPlayer.videoWidth();
    const videoHeight = videoPlayer.videoHeight();
    
    let quality = 'Unknown';
    
    if (videoHeight >= 2160) {
        quality = '4K';
    } else if (videoHeight >= 1440) {
        quality = '1440p';
    } else if (videoHeight >= 1080) {
        quality = '1080p';
    } else if (videoHeight >= 720) {
        quality = '720p';
    } else if (videoHeight >= 480) {
        quality = '480p';
    } else if (videoHeight >= 360) {
        quality = '360p';
    } else if (videoHeight > 0) {
        quality = '240p';
    }
    
    console.log(`Stream quality detected: ${quality} (${videoWidth}x${videoHeight})`);
    
    // Update quality display if element exists
    const qualityElement = document.getElementById('streamQuality');
    if (qualityElement) {
        qualityElement.textContent = quality;
    }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        max-width: 500px;
    `;
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * Check if stream is still live periodically
 */
function startStreamHealthCheck() {
    if (!currentStreamId) return;
    
    setInterval(() => {
        fetch(`/api/stream/${currentStreamId}/status`)
            .then(response => response.json())
            .then(data => {
                if (!data.is_live && window.isLive) {
                    // Stream went offline
                    handleStreamStatusUpdate({
                        stream_id: currentStreamId,
                        status: 'offline'
                    });
                    window.isLive = false;
                }
            })
            .catch(error => {
                console.error('Error checking stream status:', error);
            });
    }, 30000); // Check every 30 seconds
}

/**
 * Handle page visibility change
 */
document.addEventListener('visibilitychange', function() {
    if (videoPlayer) {
        if (document.hidden) {
            // Page is hidden, pause video to save bandwidth
            if (!videoPlayer.paused()) {
                videoPlayer.pause();
                videoPlayer.wasPlayingBeforeHidden = true;
            }
        } else {
            // Page is visible again, resume if it was playing
            if (videoPlayer.wasPlayingBeforeHidden) {
                videoPlayer.play().catch(error => {
                    console.log('Could not resume playback:', error);
                });
                videoPlayer.wasPlayingBeforeHidden = false;
            }
        }
    }
});

/**
 * Handle page unload
 */
window.addEventListener('beforeunload', function() {
    leaveStreamRoom();
    
    if (videoPlayer) {
        videoPlayer.dispose();
    }
});

// Start health check if on stream page
if (window.streamId) {
    startStreamHealthCheck();
}

// Export functions for global access
window.showEmbedCode = showEmbedCode;
window.copyEmbedCode = copyEmbedCode;
window.copyEmbedUrl = copyEmbedUrl;
window.initializeVideoPlayer = initializeVideoPlayer;
