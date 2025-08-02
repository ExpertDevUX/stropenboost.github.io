// Dashboard functionality for StrophenBoost

document.addEventListener('DOMContentLoaded', function() {
    // Handle create stream form submission
    const createStreamForm = document.getElementById('createStreamForm');
    if (createStreamForm) {
        createStreamForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Creating...';
            submitBtn.disabled = true;
            
            fetch('/create_stream', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Close modal and dynamically add stream instead of reloading
                    const modal = bootstrap.Modal.getInstance(document.getElementById('createStreamModal'));
                    if (modal) modal.hide();
                    
                    // Add stream to the UI without reload
                    addStreamToUI(data);
                    
                    // Reset form
                    this.reset();
                } else {
                    alert('Error creating stream: ' + (data.error || 'Unknown error'));
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Create stream error:', error);
                alert('Failed to create stream. Please try again.');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }
    
    // Handle create RTMP key form submission
    const createRTMPKeyForm = document.getElementById('createRTMPKeyForm');
    if (createRTMPKeyForm) {
        createRTMPKeyForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Creating...';
            submitBtn.disabled = true;
            
            fetch('/create_rtmp_key', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Close modal and dynamically add key instead of reloading
                    const modal = bootstrap.Modal.getInstance(document.getElementById('createRTMPKeyModal'));
                    if (modal) modal.hide();
                    
                    // Add RTMP key to the UI without reload
                    addRTMPKeyToUI(data);
                    
                    // Reset form
                    this.reset();
                } else {
                    alert('Error creating RTMP key: ' + (data.error || 'Unknown error'));
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('Create RTMP key error:', error);
                alert('Failed to create RTMP key. Please try again.');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }
});

// Copy to clipboard function
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        // Show success feedback
        const btn = event.target.closest('button');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check text-success"></i>';
        setTimeout(() => {
            btn.innerHTML = originalHTML;
        }, 1000);
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        alert('Failed to copy to clipboard');
    });
}

// Delete RTMP key function
function deleteRTMPKey(keyId) {
    if (confirm('Are you sure you want to delete this RTMP key?')) {
        fetch('/delete_rtmp_key/' + keyId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error deleting RTMP key: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Delete RTMP key error:', error);
            alert('Failed to delete RTMP key. Please try again.');
        });
    }
}

// Start/stop stream functions
function startStream(streamId) {
    if (confirm('Are you sure you want to start this stream?')) {
        fetch('/start_stream/' + streamId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error starting stream: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Start stream error:', error);
            alert('Failed to start stream. Please try again.');
        });
    }
}

function stopStream(streamId) {
    if (confirm('Are you sure you want to stop this stream?')) {
        fetch('/stop_stream/' + streamId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error stopping stream: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Stop stream error:', error);
            alert('Failed to stop stream. Please try again.');
        });
    }
}

// Show embed code modal
function showEmbedCode(streamId) {
    // Generate embed codes
    const baseUrl = window.location.origin;
    const embedUrl = `${baseUrl}/embed/${streamId}`;
    
    const iframe = `<iframe src="${embedUrl}" width="640" height="360" frameborder="0" allowfullscreen></iframe>`;
    const responsive = `<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden;">
    <iframe src="${embedUrl}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" frameborder="0" allowfullscreen></iframe>
</div>`;
    const javascript = `<div id="strophenboost-player-${streamId}"></div>
<script>
    (function() {
        var iframe = document.createElement('iframe');
        iframe.src = '${embedUrl}';
        iframe.width = '640';
        iframe.height = '360';
        iframe.frameBorder = '0';
        iframe.allowFullscreen = true;
        document.getElementById('strophenboost-player-${streamId}').appendChild(iframe);
    })();
</script>`;

    // Set embed codes in modal
    document.getElementById('embedIframe').value = iframe;
    document.getElementById('embedResponsive').value = responsive;
    document.getElementById('embedJavaScript').value = javascript;
    
    // Show modal
    new bootstrap.Modal(document.getElementById('embedCodeModal')).show();
}

// Show analytics modal
function showAnalytics(streamId) {
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('analyticsModal'));
    modal.show();
    
    // Load analytics data
    fetch('/stream_analytics/' + streamId)
        .then(response => response.json())
        .then(data => {
            document.getElementById('analyticsContent').innerHTML = `
                <div class="row">
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h3 class="text-primary">${data.total_views || 0}</h3>
                                <p class="text-muted">Total Views</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h3 class="text-success">${data.current_viewers || 0}</h3>
                                <p class="text-muted">Current Viewers</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h3 class="text-info">${data.peak_viewers || 0}</h3>
                                <p class="text-muted">Peak Viewers</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card text-center">
                            <div class="card-body">
                                <h3 class="text-warning">${data.total_duration || 0}m</h3>
                                <p class="text-muted">Stream Duration</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        })
        .catch(error => {
            console.error('Analytics error:', error);
            document.getElementById('analyticsContent').innerHTML = `
                <div class="alert alert-danger">
                    Failed to load analytics data.
                </div>
            `;
        });
}

// Dynamic UI update functions for instant loading without page reload
function addStreamToUI(streamData) {
    const streamsTable = document.querySelector('#streamsTable tbody');
    if (streamsTable) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <strong>${streamData.title || 'New Stream'}</strong>
                ${streamData.description ? `<br><small class="text-muted">${streamData.description.substring(0, 50)}...</small>` : ''}
            </td>
            <td><span class="badge bg-secondary">Offline</span></td>
            <td><i class="fas fa-eye me-1"></i>0</td>
            <td><small class="text-muted">Just now</small></td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-success" onclick="startStream(${streamData.stream_id})">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="showEmbedCode(${streamData.stream_id})">
                        <i class="fas fa-code"></i>
                    </button>
                    <button class="btn btn-sm btn-info" onclick="showAnalytics(${streamData.stream_id})">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteStream(${streamData.stream_id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        streamsTable.prepend(row);
    }
    
    const noStreamsMsg = document.querySelector('.no-streams-message');
    if (noStreamsMsg) noStreamsMsg.remove();
    
    showToast('Success', 'Stream created instantly!', 'success');
}

function addRTMPKeyToUI(keyData) {
    const keysTable = document.querySelector('#rtmpKeysTable tbody');
    if (keysTable) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <strong>${keyData.key_name || 'New Key'}</strong>
                <br><small class="text-muted font-monospace">${keyData.rtmp_key}</small>
            </td>
            <td><span class="badge bg-success">Active</span></td>
            <td><small class="text-muted">Just now</small></td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="copyToClipboard('${keyData.rtmp_key}')">
                    <i class="fas fa-copy me-1"></i>Copy
                </button>
            </td>
        `;
        keysTable.prepend(row);
    }
    
    showToast('Success', 'RTMP key created instantly!', 'success');
}

function showToast(title, message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'primary'} border-0`;
    toast.id = toastId;
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body"><strong>${title}</strong><br>${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    new bootstrap.Toast(toast).show();
    
    setTimeout(() => toast.remove(), 4000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1055';
    document.body.appendChild(container);
    return container;
}

// Delete stream function
function deleteStream(streamId) {
    if (confirm('Are you sure you want to delete this stream? This action cannot be undone.')) {
        fetch('/delete_stream/' + streamId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the stream row from table
                const row = event.target.closest('tr');
                if (row) {
                    row.remove();
                }
                showToast('Success', 'Stream deleted successfully!', 'success');
            } else {
                alert('Error deleting stream: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Delete stream error:', error);
            alert('Failed to delete stream. Please try again.');
        });
    }
}