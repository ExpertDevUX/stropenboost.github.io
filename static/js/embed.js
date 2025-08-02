/**
 * StrophenBoost Embed JavaScript
 * Handles embed settings, code generation, and preview functionality
 */

// Global variables
let currentStreamId = null;
let embedSettings = {
    width: 800,
    height: 450,
    autoplay: false,
    show_chat: true,
    show_controls: true,
    theme: 'dark'
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeEmbedPage();
});

/**
 * Initialize embed page functionality
 */
function initializeEmbedPage() {
    // Get stream ID from URL or data attribute
    currentStreamId = getStreamIdFromPage();
    
    // Setup form event listeners
    setupEmbedForm();
    
    // Load current settings
    loadEmbedSettings();
    
    // Generate initial embed codes
    generateEmbedCodes();
    
    // Setup preview
    setupEmbedPreview();
    
    console.log('Embed page initialized for stream:', currentStreamId);
}

/**
 * Get stream ID from the current page
 */
function getStreamIdFromPage() {
    // Try to get from URL path
    const pathMatch = window.location.pathname.match(/\/embed\/(\d+)/);
    if (pathMatch) {
        return parseInt(pathMatch[1]);
    }
    
    // Try to get from data attribute
    const embedForm = document.getElementById('embedSettingsForm');
    if (embedForm && embedForm.dataset.streamId) {
        return parseInt(embedForm.dataset.streamId);
    }
    
    // Try to get from global variable
    if (window.streamId) {
        return window.streamId;
    }
    
    return null;
}

/**
 * Setup embed form event listeners
 */
function setupEmbedForm() {
    const form = document.getElementById('embedSettingsForm');
    if (!form) return;
    
    // Listen for form changes
    form.addEventListener('change', handleSettingsChange);
    form.addEventListener('input', handleSettingsChange);
    form.addEventListener('submit', handleSettingsSubmit);
    
    // Setup individual field listeners
    const widthInput = document.getElementById('embedWidth');
    const heightInput = document.getElementById('embedHeight');
    
    if (widthInput && heightInput) {
        widthInput.addEventListener('input', debounce(updateDimensions, 500));
        heightInput.addEventListener('input', debounce(updateDimensions, 500));
    }
}

/**
 * Handle settings form changes
 */
function handleSettingsChange(event) {
    const formData = new FormData(event.target.form);
    
    // Update embed settings object
    embedSettings = {
        width: parseInt(formData.get('width')) || 800,
        height: parseInt(formData.get('height')) || 450,
        autoplay: formData.has('autoplay'),
        show_chat: formData.has('show_chat'),
        show_controls: formData.has('show_controls'),
        theme: formData.get('theme') || 'dark'
    };
    
    // Regenerate embed codes
    generateEmbedCodes();
    
    // Update preview
    updateEmbedPreview();
}

/**
 * Handle settings form submission
 */
async function handleSettingsSubmit(event) {
    event.preventDefault();
    
    if (!currentStreamId) {
        showNotification('No stream ID found', 'error');
        return;
    }
    
    const formData = new FormData(event.target);
    const submitButton = event.target.querySelector('button[type="submit"]');
    
    // Show loading state
    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
    
    try {
        const response = await fetch(`/update_embed_settings/${currentStreamId}`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Settings saved successfully!', 'success');
        } else {
            showNotification(data.error || 'Failed to save settings', 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showNotification('Network error occurred', 'error');
    } finally {
        // Reset button state
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-save me-1"></i>Update Settings';
    }
}

/**
 * Load current embed settings
 */
async function loadEmbedSettings() {
    if (!currentStreamId) return;
    
    try {
        const response = await fetch(`/api/stream/${currentStreamId}/embed_settings`);
        if (response.ok) {
            const settings = await response.json();
            
            // Update form fields
            if (settings) {
                document.getElementById('embedWidth').value = settings.width || 800;
                document.getElementById('embedHeight').value = settings.height || 450;
                document.getElementById('autoplay').checked = settings.autoplay || false;
                document.getElementById('showChat').checked = settings.show_chat !== false;
                document.getElementById('showControls').checked = settings.show_controls !== false;
                document.getElementById('theme').value = settings.theme || 'dark';
                
                // Update embedSettings object
                embedSettings = {
                    width: settings.width || 800,
                    height: settings.height || 450,
                    autoplay: settings.autoplay || false,
                    show_chat: settings.show_chat !== false,
                    show_controls: settings.show_controls !== false,
                    theme: settings.theme || 'dark'
                };
            }
        }
    } catch (error) {
        console.error('Error loading embed settings:', error);
    }
}

/**
 * Generate embed codes
 */
function generateEmbedCodes() {
    if (!currentStreamId) return;
    
    const baseUrl = window.location.origin;
    const embedUrl = `${baseUrl}/embed/${currentStreamId}`;
    
    // Build query parameters
    const params = new URLSearchParams();
    if (embedSettings.width !== 800) params.set('width', embedSettings.width);
    if (embedSettings.height !== 450) params.set('height', embedSettings.height);
    if (embedSettings.autoplay) params.set('autoplay', 'true');
    if (!embedSettings.show_chat) params.set('chat', 'false');
    if (!embedSettings.show_controls) params.set('controls', 'false');
    if (embedSettings.theme !== 'dark') params.set('theme', embedSettings.theme);
    
    const fullEmbedUrl = params.toString() ? `${embedUrl}?${params.toString()}` : embedUrl;
    
    // Generate iframe code
    const iframeCode = `<iframe 
    src="${fullEmbedUrl}" 
    width="${embedSettings.width}" 
    height="${embedSettings.height}" 
    frameborder="0" 
    allowfullscreen
    allow="autoplay; fullscreen">
</iframe>`;
    
    // Generate responsive iframe code
    const aspectRatio = (embedSettings.height / embedSettings.width * 100).toFixed(2);
    const responsiveCode = `<div style="position: relative; padding-bottom: ${aspectRatio}%; height: 0; overflow: hidden;">
    <iframe 
        src="${fullEmbedUrl}" 
        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
        frameborder="0" 
        allowfullscreen
        allow="autoplay; fullscreen">
    </iframe>
</div>`;
    
    // Generate JavaScript embed code
    const jsCode = `<div id="strophenboost-player-${currentStreamId}"></div>
<script>
(function() {
    var iframe = document.createElement('iframe');
    iframe.src = '${fullEmbedUrl}';
    iframe.width = '${embedSettings.width}';
    iframe.height = '${embedSettings.height}';
    iframe.frameBorder = '0';
    iframe.allowFullscreen = true;
    iframe.allow = 'autoplay; fullscreen';
    
    var container = document.getElementById('strophenboost-player-${currentStreamId}');
    if (container) {
        container.appendChild(iframe);
    }
})();
</script>`;
    
    // Update textarea elements
    const iframeElement = document.getElementById('iframeCode');
    const responsiveElement = document.getElementById('responsiveCode');
    const jsElement = document.getElementById('jsCode');
    
    if (iframeElement) iframeElement.value = iframeCode;
    if (responsiveElement) responsiveElement.value = responsiveCode;
    if (jsElement) jsElement.value = jsCode;
}

/**
 * Setup embed preview
 */
function setupEmbedPreview() {
    updateEmbedPreview();
}

/**
 * Update embed preview
 */
function updateEmbedPreview() {
    const previewContainer = document.getElementById('embedPreview');
    if (!previewContainer || !currentStreamId) return;
    
    const baseUrl = window.location.origin;
    const embedUrl = `${baseUrl}/embed/${currentStreamId}`;
    
    // Build query parameters
    const params = new URLSearchParams();
    if (embedSettings.width !== 800) params.set('width', embedSettings.width);
    if (embedSettings.height !== 450) params.set('height', embedSettings.height);
    if (embedSettings.autoplay) params.set('autoplay', 'true');
    if (!embedSettings.show_chat) params.set('chat', 'false');
    if (!embedSettings.show_controls) params.set('controls', 'false');
    if (embedSettings.theme !== 'dark') params.set('theme', embedSettings.theme);
    
    const fullEmbedUrl = params.toString() ? `${embedUrl}?${params.toString()}` : embedUrl;
    
    // Create preview iframe with scaled size
    const previewWidth = Math.min(embedSettings.width, 600);
    const previewHeight = (previewWidth / embedSettings.width) * embedSettings.height;
    
    previewContainer.innerHTML = `
        <div class="text-center mb-3">
            <small class="text-muted">Preview (scaled to fit)</small>
        </div>
        <div class="d-flex justify-content-center">
            <iframe 
                src="${fullEmbedUrl}" 
                width="${previewWidth}" 
                height="${previewHeight}" 
                frameborder="0" 
                allowfullscreen
                allow="autoplay; fullscreen">
            </iframe>
        </div>
        <div class="text-center mt-2">
            <small class="text-muted">Actual size: ${embedSettings.width}x${embedSettings.height}px</small>
        </div>
    `;
}

/**
 * Update dimensions and maintain aspect ratio
 */
function updateDimensions() {
    const widthInput = document.getElementById('embedWidth');
    const heightInput = document.getElementById('embedHeight');
    
    if (!widthInput || !heightInput) return;
    
    const width = parseInt(widthInput.value) || 800;
    const height = parseInt(heightInput.value) || 450;
    
    // Update settings
    embedSettings.width = width;
    embedSettings.height = height;
    
    // Regenerate codes and preview
    generateEmbedCodes();
    updateEmbedPreview();
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const text = element.value;
    
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
        
        // Visual feedback
        element.select();
        setTimeout(() => {
            element.blur();
        }, 500);
    } catch (error) {
        console.error('Failed to copy:', error);
        
        // Fallback for older browsers
        element.select();
        try {
            document.execCommand('copy');
            showNotification('Copied to clipboard!', 'success');
        } catch (fallbackError) {
            showNotification('Failed to copy to clipboard', 'error');
        }
    }
}

/**
 * Reset to default settings
 */
function resetToDefaults() {
    if (!confirm('Reset to default settings? This will undo any unsaved changes.')) {
        return;
    }
    
    // Reset to default values
    embedSettings = {
        width: 800,
        height: 450,
        autoplay: false,
        show_chat: true,
        show_controls: true,
        theme: 'dark'
    };
    
    // Update form fields
    document.getElementById('embedWidth').value = 800;
    document.getElementById('embedHeight').value = 450;
    document.getElementById('autoplay').checked = false;
    document.getElementById('showChat').checked = true;
    document.getElementById('showControls').checked = true;
    document.getElementById('theme').value = 'dark';
    
    // Regenerate codes and preview
    generateEmbedCodes();
    updateEmbedPreview();
    
    showNotification('Settings reset to defaults', 'info');
}

/**
 * Preset size buttons
 */
function setPresetSize(width, height) {
    document.getElementById('embedWidth').value = width;
    document.getElementById('embedHeight').value = height;
    
    embedSettings.width = width;
    embedSettings.height = height;
    
    generateEmbedCodes();
    updateEmbedPreview();
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
 * Debounce function to limit rapid calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Test embed in new window
 */
function testEmbed() {
    if (!currentStreamId) {
        showNotification('No stream ID found', 'error');
        return;
    }
    
    const baseUrl = window.location.origin;
    const embedUrl = `${baseUrl}/embed/${currentStreamId}`;
    
    // Build query parameters
    const params = new URLSearchParams();
    if (embedSettings.width !== 800) params.set('width', embedSettings.width);
    if (embedSettings.height !== 450) params.set('height', embedSettings.height);
    if (embedSettings.autoplay) params.set('autoplay', 'true');
    if (!embedSettings.show_chat) params.set('chat', 'false');
    if (!embedSettings.show_controls) params.set('controls', 'false');
    if (embedSettings.theme !== 'dark') params.set('theme', embedSettings.theme);
    
    const fullEmbedUrl = params.toString() ? `${embedUrl}?${params.toString()}` : embedUrl;
    
    // Open in new window
    const testWindow = window.open(
        fullEmbedUrl,
        'embed_test',
        `width=${embedSettings.width + 50},height=${embedSettings.height + 50},scrollbars=no,resizable=yes`
    );
    
    if (!testWindow) {
        showNotification('Please allow popups to test the embed', 'warning');
    }
}

// Export functions for global access
window.copyToClipboard = copyToClipboard;
window.resetToDefaults = resetToDefaults;
window.setPresetSize = setPresetSize;
window.testEmbed = testEmbed;
