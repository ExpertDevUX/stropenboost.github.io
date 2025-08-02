from flask import render_template, request, jsonify, Response, session
from app import app, db
from models import Stream, EmbedSettings
import json

@app.route('/embed/<int:stream_id>')
def embed_stream(stream_id):
    """Embeddable stream player"""
    stream = Stream.query.get_or_404(stream_id)
    
    if not stream.allow_embedding:
        return "Embedding not allowed for this stream", 403
    
    # Get embed settings
    embed_settings = EmbedSettings.query.filter_by(stream_id=stream_id).first()
    if not embed_settings:
        # Create default settings
        embed_settings = EmbedSettings(stream_id=stream_id)
        db.session.add(embed_settings)
        db.session.commit()
    
    # Get parameters from URL
    width = request.args.get('width', embed_settings.width)
    height = request.args.get('height', embed_settings.height)
    autoplay = request.args.get('autoplay', 'false').lower() == 'true'
    show_chat = request.args.get('chat', 'true').lower() == 'true' and embed_settings.show_chat
    show_controls = request.args.get('controls', 'true').lower() == 'true' and embed_settings.show_controls
    theme = request.args.get('theme', embed_settings.theme)
    
    return render_template('embed_player.html', 
                         stream=stream,
                         width=width,
                         height=height,
                         autoplay=autoplay,
                         show_chat=show_chat,
                         show_controls=show_controls,
                         theme=theme)

@app.route('/embed_code/<int:stream_id>')
def get_embed_code(stream_id):
    """Generate embed code for a stream"""
    stream = Stream.query.get_or_404(stream_id)
    embed_settings = EmbedSettings.query.filter_by(stream_id=stream_id).first()
    
    if not embed_settings:
        embed_settings = EmbedSettings(stream_id=stream_id)
        db.session.add(embed_settings)
        db.session.commit()
    
    base_url = request.url_root.rstrip('/')
    embed_url = f"{base_url}/embed/{stream_id}"
    
    # Generate iframe code
    iframe_code = f'''<iframe 
    src="{embed_url}" 
    width="{embed_settings.width}" 
    height="{embed_settings.height}" 
    frameborder="0" 
    allowfullscreen
    allow="autoplay; fullscreen">
</iframe>'''
    
    # Generate responsive iframe code
    responsive_code = f'''<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden;">
    <iframe 
        src="{embed_url}" 
        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
        frameborder="0" 
        allowfullscreen
        allow="autoplay; fullscreen">
    </iframe>
</div>'''
    
    # Generate JavaScript embed code
    js_code = f'''<div id="strophenboost-player-{stream_id}"></div>
<script>
(function() {{
    var iframe = document.createElement('iframe');
    iframe.src = '{embed_url}';
    iframe.width = '{embed_settings.width}';
    iframe.height = '{embed_settings.height}';
    iframe.frameBorder = '0';
    iframe.allowFullscreen = true;
    iframe.allow = 'autoplay; fullscreen';
    
    var container = document.getElementById('strophenboost-player-{stream_id}');
    container.appendChild(iframe);
}})();
</script>'''
    
    return jsonify({
        'iframe': iframe_code,
        'responsive': responsive_code,
        'javascript': js_code,
        'direct_url': embed_url
    })

@app.route('/update_embed_settings/<int:stream_id>', methods=['POST'])
def update_embed_settings(stream_id):
    """Update embed settings for a stream"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    stream = Stream.query.get_or_404(stream_id)
    
    if stream.broadcaster_id != session['user_id']:
        return jsonify({'error': 'Permission denied'}), 403
    
    embed_settings = EmbedSettings.query.filter_by(stream_id=stream_id).first()
    if not embed_settings:
        embed_settings = EmbedSettings(stream_id=stream_id)
        db.session.add(embed_settings)
    
    # Update settings from form data
    embed_settings.width = int(request.form.get('width', embed_settings.width))
    embed_settings.height = int(request.form.get('height', embed_settings.height))
    embed_settings.autoplay = request.form.get('autoplay') == 'true'
    embed_settings.show_chat = request.form.get('show_chat') == 'true'
    embed_settings.show_controls = request.form.get('show_controls') == 'true'
    embed_settings.theme = request.form.get('theme', embed_settings.theme)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Embed settings updated successfully'})

@app.route('/api/stream/<int:stream_id>/status')
def stream_status_api(stream_id):
    """API endpoint for stream status (for embedded players)"""
    stream = Stream.query.get_or_404(stream_id)
    
    return jsonify({
        'id': stream.id,
        'title': stream.title,
        'is_live': stream.is_live,
        'viewer_count': stream.viewer_count,
        'hls_url': stream.hls_url if stream.is_live else None,
        'dash_url': stream.dash_url if stream.is_live else None,
        'chat_enabled': stream.chat_enabled,
        'started_at': stream.started_at.isoformat() if stream.started_at else None
    })

@app.route('/hls/<stream_key>/<path:filename>')
def serve_hls(stream_key, filename):
    """Serve HLS files"""
    # This would typically serve files from a CDN or file system
    # For now, we'll return a placeholder response
    return Response("HLS content not available", mimetype="application/vnd.apple.mpegurl")

@app.route('/dash/<stream_key>/<path:filename>')
def serve_dash(stream_key, filename):
    """Serve DASH files"""
    # This would typically serve files from a CDN or file system
    # For now, we'll return a placeholder response
    return Response("DASH content not available", mimetype="application/dash+xml")
