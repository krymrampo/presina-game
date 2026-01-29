"""
Presina - Main Flask application.
"""
import logging
from flask import Flask, render_template, send_from_directory
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

# Create Socket.IO instance
socketio = SocketIO(
    app, 
    cors_allowed_origins=app.config.get('CORS_ALLOWED_ORIGINS', '*'),
    async_mode='eventlet'
)

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


# ==================== Main ====================

if __name__ == '__main__':
    logger.info("Starting Presina server...")
    logger.info("Open http://localhost:5000 in your browser")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
