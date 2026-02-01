"""
Presina - Main Flask application.
"""
import logging
from functools import wraps
from urllib.parse import parse_qs
from flask import Flask, render_template, send_from_directory, request, jsonify, g
from werkzeug.wrappers import Response
from flask_socketio import SocketIO

from config import get_config
from auth_utils import (
    create_guest_session,
    resolve_token,
    serialize_user,
    invalidate_token
)
from models.user import User, get_db_connection
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


@app.route('/uploads/avatars/<path:filepath>')
def serve_avatars(filepath):
    """Serve user uploaded avatars."""
    return send_from_directory('uploads/avatars', filepath)


# ==================== Auth Helpers ====================

def _extract_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1].strip()
    data = request.get_json(silent=True) or {}
    return data.get('token')


def _require_auth(allow_guest: bool = False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            user, is_guest = resolve_token(token)
            if not user or (is_guest and not allow_guest):
                return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
            g.current_user = user
            g.is_guest = is_guest
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ==================== Auth API ====================

@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    display_name = (data.get('display_name') or '').strip() or None

    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Username troppo corto (min 3 caratteri)'}), 400
    if len(password) < 4:
        return jsonify({'success': False, 'error': 'Password troppo corta (min 4 caratteri)'}), 400

    user, error = User.register(username, password, display_name=display_name)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    return jsonify({'success': True, 'user': user.to_dict()})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400

    result, error = User.login(username, password)
    if error:
        return jsonify({'success': False, 'error': error}), 401

    return jsonify({
        'success': True,
        'token': result['token'],
        'user': result['user'].to_dict()
    })


@app.route('/api/auth/guest', methods=['POST'])
def api_auth_guest():
    data = request.get_json(silent=True) or {}
    display_name = data.get('display_name')
    token, guest_user = create_guest_session(display_name=display_name)
    return jsonify({
        'success': True,
        'token': token,
        'user': guest_user
    })


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    token = _extract_token()
    user, is_guest = resolve_token(token)
    if not user:
        return jsonify({'success': False, 'error': 'Sessione non valida'}), 401
    return jsonify({'success': True, 'user': serialize_user(user, is_guest)})


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    token = _extract_token()
    invalidate_token(token)
    return jsonify({'success': True})


# ==================== User API ====================

@app.route('/api/user/stats', methods=['GET'])
@_require_auth(allow_guest=False)
def api_user_stats():
    user = g.current_user
    stats = user.get_stats()
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/user/games', methods=['GET'])
@_require_auth(allow_guest=False)
def api_user_games():
    user = g.current_user
    try:
        limit = int(request.args.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10
    limit = max(1, min(limit, 50))
    games = user.get_recent_games(limit=limit)
    return jsonify({'success': True, 'games': games})


@app.route('/api/user/avatar', methods=['POST'])
@_require_auth(allow_guest=False)
def api_user_avatar():
    user = g.current_user
    data = request.get_json(silent=True) or {}
    image = data.get('image')
    success, result = user.update_avatar(image)
    if not success:
        return jsonify({'success': False, 'error': result}), 400
    return jsonify({'success': True, 'avatar': result})


# ==================== Leaderboard ====================

@app.route('/api/leaderboard', methods=['GET'])
def api_leaderboard():
    category = (request.args.get('category') or 'wins').lower()
    try:
        limit = int(request.args.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10
    limit = max(1, min(limit, 50))

    order_map = {
        'wins': 's.games_won DESC, s.games_played DESC',
        'win_rate': 'win_rate DESC, s.games_played DESC',
        'streak': 's.best_streak DESC, s.games_played DESC'
    }
    order_by = order_map.get(category, order_map['wins'])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT 
            u.username,
            u.display_name,
            s.games_played,
            s.games_won,
            s.games_lost,
            s.best_streak,
            CASE 
                WHEN s.games_played > 0 THEN ROUND((s.games_won * 100.0) / s.games_played, 1)
                ELSE 0
            END AS win_rate
        FROM users u
        JOIN user_stats s ON s.user_id = u.id
        WHERE u.is_active = 1
        ORDER BY {order_by}
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    leaderboard = []
    for idx, row in enumerate(rows):
        leaderboard.append({
            'rank': idx + 1,
            'username': row['username'],
            'display_name': row['display_name'],
            'games_played': row['games_played'],
            'games_won': row['games_won'],
            'games_lost': row['games_lost'],
            'best_streak': row['best_streak'],
            'win_rate': row['win_rate']
        })

    return jsonify({'success': True, 'leaderboard': leaderboard})


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
