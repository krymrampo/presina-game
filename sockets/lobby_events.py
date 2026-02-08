"""
Lobby Socket.IO events.
"""
import logging
import uuid
from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from auth_utils import resolve_token, build_auth_payload
from game.player import Player
from game.presina_game import GamePhase
from rooms.room_manager import room_manager
from sockets.utils import verify_player_socket, ensure_player_socket

logger = logging.getLogger(__name__)

# Validation constants
MAX_NAME_LENGTH = 30
MAX_ROOM_NAME_LENGTH = 50


def _validate_name(name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """Validate and sanitize a name. Returns sanitized name or raises ValueError."""
    if not name or not isinstance(name, str):
        raise ValueError('Nome non valido')
    
    # Strip and limit length
    name = name.strip()[:max_length]
    
    if not name:
        raise ValueError('Il nome non può essere vuoto')
    
    return name

def _emit_room_state(socketio, room, event: str, extra: dict = None, exclude_player_id: str = None, include_offline: bool = True):
    """Emit per-player room state to avoid leaking private info.
    
    Args:
        socketio: SocketIO instance
        room: Room object
        event: Event name
        extra: Extra data to include
        exclude_player_id: Player ID to exclude
        include_offline: Also emit to offline players (for sync purposes)
    """
    if not room:
        return
    for pid, player in room.game.players.items():
        if exclude_player_id and pid == exclude_player_id:
            continue
        # Always try to emit if player has a sid, regardless of online status
        # This ensures reconnected players get updates
        if player.sid:
            try:
                state = room.game.get_state_for_player(pid)
                state['admin_id'] = room.admin_id
                payload = {'game_state': state}
                if extra:
                    payload.update(extra)
                socketio.emit(event, payload, room=player.sid)
            except Exception:
                # Ignore emit errors (player may have disconnected)
                pass

def register_lobby_events(socketio):
    """Register all lobby-related socket events."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle new connection."""
        logger.info(f"Client connected: {request.sid}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle disconnection."""
        logger.info(f"Client disconnected: {request.sid}")
        
        # Get player_id BEFORE unregistering (otherwise it's deleted)
        player_id = room_manager.get_player_by_sid(request.sid)
        
        # Now unregister the socket
        room_manager.unregister_socket(request.sid)
        
        # Notify room if player was in one
        room = room_manager.get_player_room(player_id) if player_id else None
        room_id_for_broadcast = room.room_id if room else None
        if player_id and room_id_for_broadcast:
            import threading
            def delayed_broadcast():
                import time
                time.sleep(2)  # Wait 2 seconds for quick reconnect
                with room_manager.lock:
                    # Re-fetch room - it may have been deleted in the meantime
                    still_room = room_manager.get_room(room_id_for_broadcast)
                    if not still_room:
                        return
                    player = still_room.game.get_player(player_id)
                    if player and not player.is_online:
                        _emit_room_state(socketio, still_room, 'game_state')
            
            threading.Thread(target=delayed_broadcast, daemon=True).start()
        
        # Broadcast updated room list (may clean up offline ghosts)
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('register_player')
    def handle_register(data):
        """
        Register a player.
        Data: { player_id, name, auth_token? }
        
        For authenticated users, if an existing player session is found
        in a room (same user_id), the session is taken over: the client
        receives the old player_id so it can rejoin seamlessly from
        a different device.
        """
        player_id = data.get('player_id')
        name = data.get('name', 'Anonimo')
        auth_token = data.get('auth_token')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return
        
        # Resolve authentication first
        auth = None
        user_id = None
        if auth_token:
            user, is_guest = resolve_token(auth_token)
            if user:
                auth = build_auth_payload(user, is_guest)
                user_id = auth.get('user_id')  # None for guests
        
        # For authenticated (non-guest) users, check for existing session in a room
        if user_id:
            with room_manager.lock:
                result = room_manager.takeover_player_session(user_id, request.sid)
            if result:
                old_player_id, room, old_sid = result
                room_manager.set_player_auth(old_player_id, auth)
                
                # Notify old device that session was transferred
                if old_sid:
                    socketio.emit('session_taken_over', {
                        'message': 'La tua sessione è stata trasferita su un altro dispositivo'
                    }, to=old_sid)
                
                player = room.game.get_player(old_player_id)
                emit('registered', {
                    'player_id': old_player_id,
                    'name': player.name if player else name,
                    'existing_room': room.to_dict()
                })
                return
        
        # Normal registration – no existing session found
        with room_manager.lock:
            room_manager.register_socket(request.sid, player_id)
        if auth:
            room_manager.set_player_auth(player_id, auth)
        else:
            room_manager.set_player_auth(player_id, None)
        emit('registered', {'player_id': player_id, 'name': name})
    
    @socketio.on('list_rooms')
    def handle_list_rooms():
        """Get list of public rooms."""
        rooms = room_manager.get_public_rooms()
        emit('rooms_list', {'rooms': [r.to_dict() for r in rooms]})
    
    @socketio.on('search_rooms')
    def handle_search_rooms(data):
        """
        Search rooms by name.
        Data: { query }
        """
        query = data.get('query', '')
        rooms = room_manager.search_rooms(query)
        emit('rooms_list', {'rooms': [r.to_dict() for r in rooms]})
    
    @socketio.on('create_room')
    def handle_create_room(data):
        """
        Create a new room.
        Data: { player_id, player_name, room_name, is_public?, access_code? }
        """
        player_id = data.get('player_id')
        player_name = data.get('player_name', 'Anonimo')
        room_name = data.get('room_name', 'Nuova stanza')
        is_public = data.get('is_public', True)
        access_code = data.get('access_code') if not is_public else None
        auth_token = data.get('auth_token')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        if not ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        # Prefer authenticated display name if available
        auth = room_manager.get_player_auth(player_id)
        if not auth and auth_token:
            user, is_guest = resolve_token(auth_token)
            if user:
                auth = build_auth_payload(user, is_guest)
                room_manager.set_player_auth(player_id, auth)
        if auth:
            auth_name = auth.get('display_name') or auth.get('username')
            if auth_name:
                player_name = auth_name

        # Validate names
        try:
            player_name = _validate_name(player_name, MAX_NAME_LENGTH)
            room_name = _validate_name(room_name, MAX_ROOM_NAME_LENGTH)
        except ValueError as e:
            emit('error', {'message': str(e)})
            return
        
        # Check if already in a room
        existing_room = room_manager.get_player_room(player_id)
        if existing_room:
            emit('error', {'message': 'Sei già in una stanza'})
            return
        
        # Create player and room
        user_id = auth.get('user_id') if auth and not auth.get('is_guest') else None
        is_guest = auth.get('is_guest', False) if auth else False
        player = Player(player_id, player_name, request.sid, user_id=user_id, is_guest=is_guest)
        room = room_manager.create_room(room_name, player, is_public=is_public, access_code=access_code)
        
        # Join socket room
        join_room(room.room_id)
        
        state = room.game.get_state_for_player(player_id)
        state['admin_id'] = room.admin_id
        # Include access code in response for private rooms (admin needs to share it)
        room_dict = room.to_dict_with_code() if not is_public else room.to_dict()
        emit('room_created', {
            'room': room_dict,
            'game_state': state
        })
        
        # Broadcast updated room list
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('join_room')
    def handle_join_room(data):
        """
        Join an existing room.
        Data: { player_id, player_name, room_id, access_code? }
        """
        player_id = data.get('player_id')
        player_name = data.get('player_name', 'Anonimo')
        room_id = data.get('room_id')
        access_code = data.get('access_code')
        auth_token = data.get('auth_token')
        
        if not player_id or not room_id:
            emit('error', {'message': 'Dati mancanti'})
            return

        if not ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        # Prefer authenticated display name if available
        auth = room_manager.get_player_auth(player_id)
        if not auth and auth_token:
            user, is_guest = resolve_token(auth_token)
            if user:
                auth = build_auth_payload(user, is_guest)
                room_manager.set_player_auth(player_id, auth)
        if auth:
            auth_name = auth.get('display_name') or auth.get('username')
            if auth_name:
                player_name = auth_name

        # Validate player name
        try:
            player_name = _validate_name(player_name, MAX_NAME_LENGTH)
        except ValueError as e:
            emit('error', {'message': str(e)})
            return
        
        # Create player
        user_id = auth.get('user_id') if auth and not auth.get('is_guest') else None
        is_guest = auth.get('is_guest', False) if auth else False
        player = Player(player_id, player_name, request.sid, user_id=user_id, is_guest=is_guest)
        
        success, message = room_manager.join_room(room_id, player, access_code=access_code)
        
        if not success:
            emit('error', {'message': message})
            return
        
        room = room_manager.get_room(room_id)
        
        # Join socket room
        join_room(room_id)
        room_manager.register_socket(request.sid, player_id)
        
        state = room.game.get_state_for_player(player_id)
        state['admin_id'] = room.admin_id
        emit('room_joined', {
            'room': room.to_dict(),
            'game_state': state,
            'message': message
        })
        
        # Notify other players
        _emit_room_state(
            socketio,
            room,
            'player_joined',
            extra={'player_id': player_id, 'player_name': player_name},
            exclude_player_id=player_id
        )
        
        # Broadcast updated room list
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        """
        Leave current room.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        if not ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        room_id = room.room_id if room else None
        
        success, message = room_manager.leave_room(player_id)
        
        if room_id:
            leave_room(room_id)
            
            # Notify other players
            room = room_manager.get_room(room_id)
            if room:
                _emit_room_state(
                    socketio,
                    room,
                    'player_left',
                    extra={'player_id': player_id},
                    exclude_player_id=player_id
                )
        
        emit('left_room', {'message': message})
        
        # Broadcast updated room list
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })

    @socketio.on('abandon_room')
    def handle_abandon_room(data):
        """
        Abandon a room explicitly (clear mapping to allow joining another room).
        Data: { player_id }
        """
        player_id = data.get('player_id')

        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        if not ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return

        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            room_id = room.room_id if room else None

            success, message, room = room_manager.abandon_room(player_id)

        if not success:
            emit('error', {'message': message})
            return

        if room_id:
            leave_room(room_id)

        if room:
            # Use _broadcast_game_state from game_events which calls tick()
            # to trigger bot auto-play if it's the bot's turn
            from sockets.game_events import _broadcast_game_state
            _broadcast_game_state(socketio, room)

        emit('left_room', {'message': message})

        # Broadcast updated room list
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('kick_player')
    def handle_kick_player(data):
        """
        Kick a player (admin only).
        Data: { admin_id, player_id }
        """
        admin_id = data.get('admin_id')
        player_id = data.get('player_id')
        
        if not admin_id or not player_id:
            emit('error', {'message': 'Dati mancanti'})
            return

        if not ensure_player_socket(admin_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(admin_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return
        
        player = room.game.get_player(player_id)
        player_sid = player.sid if player else None
        
        success, message = room_manager.kick_player(admin_id, player_id)
        
        if not success:
            emit('error', {'message': message})
            return
        
        # Notify kicked player
        if player_sid:
            socketio.emit('kicked', {'message': 'Sei stato rimosso dalla stanza'}, room=player_sid)
        
        # Notify room
        _emit_room_state(
            socketio,
            room,
            'player_kicked',
            extra={'player_id': player_id},
            exclude_player_id=player_id
        )
    
    @socketio.on('rejoin_game')
    def handle_rejoin(data):
        """
        Rejoin a game after disconnect.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        if not ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        success, message, room = room_manager.rejoin_room(player_id, request.sid)
        
        if not success:
            emit('rejoin_failed', {'message': message})
            return
        
        room_manager.register_socket(request.sid, player_id)
        join_room(room.room_id)
        
        state = room.game.get_state_for_player(player_id)
        state['admin_id'] = room.admin_id
        emit('rejoin_success', {
            'room': room.to_dict(),
            'game_state': state
        })
        
        # Notify other players
        emit('player_reconnected', {
            'player_id': player_id
        }, room=room.room_id, include_self=False)
        
        # Broadcast updated per-player state so online status is refreshed
        _emit_room_state(socketio, room, 'game_state')
