"""
Presina - Main Flask application.
"""
import logging
import secrets
from urllib.parse import parse_qs
from flask import Flask, render_template, send_from_directory, request, jsonify
from werkzeug.wrappers import Response
from flask_socketio import SocketIO

from config import get_config
from sockets import register_lobby_events, register_game_events, register_chat_events
from models.user import User, init_database

# Initialize database
init_database()

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


# ==================== Authentication Routes ====================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Register a new user"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip() or None
    display_name = data.get('display_name', '').strip() or None
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username e password richiesti'}), 400
    
    if len(username) < 3:
        return jsonify({'success': False, 'error': 'Username troppo corto (min 3 caratteri)'}), 400
    
    if len(password) < 4:
        return jsonify({'success': False, 'error': 'Password troppo corta (min 4 caratteri)'}), 400
    
    user, error = User.register(username, password, email, display_name)
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Login a user"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username e password richiesti'}), 400
    
    result, error = User.login(username, password)
    
    if error:
        return jsonify({'success': False, 'error': error}), 401
    
    return jsonify({
        'success': True,
        'user': result['user'].to_dict(include_stats=True),
        'token': result['token']
    })


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """Logout a user"""
    data = request.get_json() or {}
    token = data.get('token') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if token:
        user = User.get_by_token(token)
        if user:
            user.logout()
    
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def api_get_current_user():
    """Get current user info from token"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not token:
        return jsonify({'success': False, 'error': 'Token mancante'}), 401
    
    user = User.get_by_token(token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Sessione scaduta'}), 401
    
    return jsonify({
        'success': True,
        'user': user.to_dict(include_stats=True)
    })


@app.route('/api/auth/guest', methods=['POST'])
def api_guest_login():
    """Login as guest (create temporary user)"""
    import uuid
    
    guest_id = str(uuid.uuid4())[:8]
    username = f"guest_{guest_id}"
    password = secrets.token_hex(16)
    
    user, error = User.register(username, password, display_name=f"Ospite {guest_id}")
    
    if error:
        return jsonify({'success': False, 'error': error}), 500
    
    # Create session
    token = user.create_session(duration_days=1)  # Short session for guests
    
    return jsonify({
        'success': True,
        'user': user.to_dict(include_stats=True),
        'token': token,
        'is_guest': True
    })


# ==================== User Statistics Routes ====================

@app.route('/api/user/stats', methods=['GET'])
def api_get_user_stats():
    """Get current user statistics"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not token:
        return jsonify({'success': False, 'error': 'Token mancante'}), 401
    
    user = User.get_by_token(token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Sessione scaduta'}), 401
    
    return jsonify({
        'success': True,
        'stats': user.get_stats()
    })


@app.route('/api/user/games', methods=['GET'])
def api_get_user_games():
    """Get user's recent games"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not token:
        return jsonify({'success': False, 'error': 'Token mancante'}), 401
    
    user = User.get_by_token(token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Sessione scaduta'}), 401
    
    games = user.get_recent_games(limit=limit)
    
    return jsonify({
        'success': True,
        'games': games
    })


@app.route('/api/user/achievements', methods=['GET'])
def api_get_user_achievements():
    """Get user achievements"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not token:
        return jsonify({'success': False, 'error': 'Token mancante'}), 401
    
    user = User.get_by_token(token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Sessione scaduta'}), 401
    
    achievements = user.get_achievements()
    
    return jsonify({
        'success': True,
        'achievements': achievements
    })


@app.route('/api/leaderboard', methods=['GET'])
def api_get_leaderboard():
    """Get global leaderboard"""
    from models.user import get_db_connection
    
    category = request.args.get('category', 'wins')  # wins, games, streak
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if category == 'wins':
        order_by = 'games_won DESC, games_played ASC'
    elif category == 'games':
        order_by = 'games_played DESC'
    elif category == 'streak':
        order_by = 'best_streak DESC'
    elif category == 'win_rate':
        order_by = 'CAST(games_won AS FLOAT) / games_played DESC'
    else:
        order_by = 'games_won DESC'
    
    cursor.execute(f'''
        SELECT u.username, u.display_name, u.avatar, s.*
        FROM users u
        JOIN user_stats s ON u.id = s.user_id
        WHERE u.username NOT LIKE 'guest_%'
        AND s.games_played > 0
        ORDER BY {order_by}
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    leaderboard = []
    for idx, row in enumerate(rows, 1):
        stats = dict(row)
        stats['rank'] = idx
        if stats['games_played'] > 0:
            stats['win_rate'] = round((stats['games_won'] / stats['games_played']) * 100, 1)
        else:
            stats['win_rate'] = 0
        leaderboard.append(stats)
    
    return jsonify({
        'success': True,
        'leaderboard': leaderboard
    })


# ==================== Main ====================

if __name__ == '__main__':
    logger.info("Starting Presina server...")
    logger.info("Open http://localhost:5000 in your browser")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
