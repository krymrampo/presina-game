"""
Presina - Main Flask application.
"""
import logging
from urllib.parse import parse_qs
from flask import Flask, render_template, send_from_directory, request, jsonify
from werkzeug.wrappers import Response
from flask_socketio import SocketIO

from config import get_config
from sockets import register_lobby_events, register_game_events, register_chat_events

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# Block websocket transport for Engine.IO to avoid gunicorn gthread errors.
class _BlockWebSocketTransport:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/socket.io'):
            qs = parse_qs(environ.get('QUERY_STRING', ''))
            if qs.get('transport', [''])[0] == 'websocket':
                res = Response('WebSocket disabled', status=400)
                return res(environ, start_response)
        return self.wsgi_app(environ, start_response)

# Create Socket.IO instance
socketio = SocketIO(
    app, 
    cors_allowed_origins=app.config.get('CORS_ALLOWED_ORIGINS', '*'),
    async_mode='threading',
    allow_upgrades=False,
    transports=['polling']
)

app.wsgi_app = _BlockWebSocketTransport(app.wsgi_app)

# Register socket events
register_lobby_events(socketio)
register_game_events(socketio)
register_chat_events(socketio)


# ==================== Routes ====================

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/carte_napoletane/<path:filepath>')
def serve_cards(filepath):
    """Serve card images."""
    return send_from_directory('carte_napoletane', filepath)


@app.route('/static/<path:filepath>')
def serve_static(filepath):
    """Serve static files."""
    return send_from_directory('static', filepath)


@app.route('/admin/cleanup', methods=['POST'])
def admin_cleanup():
    """Admin endpoint to cleanup stale rooms."""
    # Simple auth check - in production use proper auth
    auth_key = request.headers.get('X-Admin-Key') or request.args.get('key')
    expected_key = app.config.get('SECRET_KEY')
    
    if not auth_key or auth_key != expected_key:
        return jsonify({'error': 'Unauthorized'}), 401
    
    from rooms.room_manager import room_manager
    deleted_count = room_manager.cleanup_stale_rooms()
    
    return jsonify({
        'success': True,
        'deleted_rooms': deleted_count,
        'remaining_rooms': len(room_manager.rooms)
    })


# ==================== Main ====================

if __name__ == '__main__':
    logger.info("Starting Presina server...")
    logger.info("Open http://localhost:5000 in your browser")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
