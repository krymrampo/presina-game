"""
Lobby Socket.IO events.
"""
import logging
import uuid
from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from game.player import Player
from game.presina_game import GamePhase
from rooms.room_manager import room_manager

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


def _verify_player_socket(player_id: str, sid: str) -> bool:
    """
    Verify that the player_id is associated with the given socket SID.
    This prevents players from impersonating others.
    """
    registered_player = room_manager.get_player_by_sid(sid)
    return registered_player == player_id

def _ensure_player_socket(player_id: str, sid: str) -> bool:
    """
    Ensure this socket is associated with the player_id.
    If the socket isn't registered yet, register it.
    """
    registered_player = room_manager.get_player_by_sid(sid)
    if registered_player is None:
        room_manager.register_socket(sid, player_id)
        return True
    return registered_player == player_id

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
        if player_id and room:
            # Small delay to allow for quick reconnections
            import threading
            def delayed_broadcast():
                import time
                time.sleep(2)  # Wait 2 seconds for quick reconnect
                # Check if player is still offline
                player = room.game.get_player(player_id)
                if player and not player.is_online:
                    _emit_room_state(socketio, room, 'game_state')
            
            threading.Thread(target=delayed_broadcast, daemon=True).start()
        
        # Broadcast updated room list (may clean up offline ghosts)
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('register_player')
    def handle_register(data):
        """
        Register a player.
        Data: { player_id, name }
        """
        player_id = data.get('player_id')
        name = data.get('name', 'Anonimo')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return
        
        room_manager.register_socket(request.sid, player_id)
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
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        if not _ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
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
        player = Player(player_id, player_name, request.sid)
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
        
        if not player_id or not room_id:
            emit('error', {'message': 'Dati mancanti'})
            return

        if not _ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        # Validate player name
        try:
            player_name = _validate_name(player_name, MAX_NAME_LENGTH)
        except ValueError as e:
            emit('error', {'message': str(e)})
            return
        
        # Create player
        player = Player(player_id, player_name, request.sid)
        
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

        if not _ensure_player_socket(player_id, request.sid):
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

        if not _ensure_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return

        room = room_manager.get_player_room(player_id)
        room_id = room.room_id if room else None

        success, message, room = room_manager.abandon_room(player_id)

        if not success:
            emit('error', {'message': message})
            return

        if room_id:
            leave_room(room_id)

        if room:
            _emit_room_state(socketio, room, 'game_state', exclude_player_id=player_id)

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

        if not _ensure_player_socket(admin_id, request.sid):
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

        if not _ensure_player_socket(player_id, request.sid):
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


