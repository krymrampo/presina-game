"""
Game Socket.IO events.
"""
import time
import logging
from flask import request
from flask_socketio import emit

from models.user import User
from rooms.room_manager import room_manager
from game.presina_game import GamePhase

def _verify_player_socket(player_id: str, sid: str) -> bool:
    """
    Verify that the player_id is associated with the given socket SID.
    This prevents players from impersonating others.
    """
    registered_player = room_manager.get_player_by_sid(sid)
    return registered_player == player_id

def register_game_events(socketio):
    """Register all game-related socket events."""
    
    @socketio.on('start_game')
    def handle_start_game(data):
        """
        Start the game (admin only).
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return
        
        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return

        if room.game.check_and_handle_turn_timeout():
            _broadcast_game_state(socketio, room)
        
        if room.admin_id != player_id:
            emit('error', {'message': 'Solo l\'admin può avviare la partita'})
            return
        
        if not room.game.can_start():
            emit('error', {'message': 'Servono almeno 2 giocatori'})
            return
        
        room.game.start_game()
        
        # Send game state to all players
        for pid, player in room.game.players.items():
            if player.sid:
                state = room.game.get_state_for_player(pid)
                state['admin_id'] = room.admin_id
                socketio.emit('game_started', {
                    'game_state': state
                }, room=player.sid)
        
        # Broadcast updated room list
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('make_bet')
    def handle_make_bet(data):
        """
        Make a bet.
        Data: { player_id, bet }
        """
        player_id = data.get('player_id')
        bet = data.get('bet')
        
        if player_id is None or bet is None:
            emit('error', {'message': 'Dati mancanti'})
            return
        
        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return

        if room.game.check_and_handle_turn_timeout():
            _broadcast_game_state(socketio, room)
        
        try:
            bet_value = int(bet)
            if bet_value < 0:
                emit('error', {'message': 'La puntata non può essere negativa'})
                return
        except (ValueError, TypeError):
            emit('error', {'message': 'Puntata non valida'})
            return
        
        success, message = room.game.make_bet(player_id, bet_value)
        
        if not success:
            emit('error', {'message': message})
            return

        # Send updated game state to all players
        _broadcast_game_state(socketio, room)
    
    @socketio.on('play_card')
    def handle_play_card(data):
        """
        Play a card.
        Data: { player_id, suit, value, jolly_choice? }
        """
        player_id = data.get('player_id')
        suit = data.get('suit')
        value = data.get('value')
        jolly_choice = data.get('jolly_choice')
        
        if not player_id or not suit or value is None:
            emit('error', {'message': 'Dati mancanti'})
            return
        
        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return

        if room.game.check_and_handle_turn_timeout():
            _broadcast_game_state(socketio, room)
        
        try:
            card_value = int(value)
        except (ValueError, TypeError):
            emit('error', {'message': 'Valore carta non valido'})
            return
        
        success, message = room.game.play_card(player_id, suit, card_value, jolly_choice)
        
        if not success:
            emit('error', {'message': message})
            return

        # Check if waiting for jolly choice
        if room.game.phase == GamePhase.WAITING_JOLLY and room.game.pending_jolly_player == player_id:
            emit('jolly_choice_required', {
                'message': 'Scegli: prende o lascia?'
            })
        else:
            # Send updated game state to all players
            _broadcast_game_state(socketio, room)
    
    @socketio.on('choose_jolly')
    def handle_choose_jolly(data):
        """
        Choose jolly action.
        Data: { player_id, choice: 'prende' | 'lascia' }
        """
        player_id = data.get('player_id')
        choice = data.get('choice')
        
        if not player_id or not choice:
            emit('error', {'message': 'Dati mancanti'})
            return

        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return
        
        success, message = room.game.play_card(player_id, None, None, choice)
        
        if not success:
            emit('error', {'message': message})
            return

        # Send updated game state to all players
        _broadcast_game_state(socketio, room)
    
    @socketio.on('advance_trick')
    def handle_advance_trick(data):
        """
        Advance from TRICK_COMPLETE phase after 3 second display.
        Data: { player_id }
        Only authenticated players in the room can trigger this.
        """
        player_id = data.get('player_id')
        
        if not player_id:
            return
        
        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        # Verify player is actually in this room
        player = room.game.get_player(player_id)
        if not player:
            return
        
        # Only process if in TRICK_COMPLETE phase
        if room.game.phase != GamePhase.TRICK_COMPLETE:
            return
        
        success, message = room.game.advance_from_trick_complete()
        
        if success:
            _broadcast_game_state(socketio, room)
    
    @socketio.on('ready_next_turn')
    def handle_ready_next_turn(data):
        """
        Admin advances to next turn.
        Data: { player_id }
        Only the room admin can advance to the next turn (server-side check).
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return
        
        # Server-side admin check - ignore what client says
        is_admin = room.admin_id == player_id
        if not is_admin:
            emit('error', {'message': 'Solo l\'admin può avviare il prossimo turno'})
            return
        
        success, message = room.game.ready_for_next_turn(player_id, is_admin)
        
        if not success:
            emit('error', {'message': message})
            return

        # Send updated game state to all players
        _broadcast_game_state(socketio, room)
        
        # If game is over, update room list
        if room.game.phase == GamePhase.GAME_OVER:
            socketio.emit('rooms_list', {
                'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
            })
    
    @socketio.on('get_game_state')
    def handle_get_game_state(data):
        """
        Get current game state.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return

        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            emit('error', {'message': 'Non sei in nessuna stanza'})
            return
        
        # Update player's sid if it changed (reconnection)
        player = room.game.get_player(player_id)
        if player and player.sid != request.sid:
            player.sid = request.sid
            player.is_online = True
            player.offline_since = None
        
        state = room.game.get_state_for_player(player_id)
        state['admin_id'] = room.admin_id
        emit('game_state', {
            'game_state': state
        })
    
    @socketio.on('ping')
    def handle_ping(data):
        """
        Heartbeat/ping from client to keep connection alive.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        if player_id:
            room = room_manager.get_player_room(player_id)
            if room:
                player = room.game.get_player(player_id)
                if player:
                    player.is_online = True
                    player.offline_since = None
                    player.last_activity = time.time()
                    if player.sid != request.sid:
                        player.sid = request.sid
                    # Also update room manager's sid mapping
                    room_manager.register_socket(request.sid, player_id)
        emit('pong', {'timestamp': time.time()})
    
    @socketio.on('visibility_change')
    def handle_visibility_change(data):
        """
        Handle page visibility change from client.
        Data: { player_id, is_visible: bool }
        """
        player_id = data.get('player_id')
        is_visible = data.get('is_visible', True)
        
        if not player_id:
            return
        
        # Verify player identity
        if not _verify_player_socket(player_id, request.sid):
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        player = room.game.get_player(player_id)
        if not player:
            return
        
        if is_visible:
            # User came back to the page
            player.is_away = False
            player.away_since = None
            player.is_online = True
            player.offline_since = None
            player.last_activity = time.time()
        else:
            # User switched tab or minimized
            player.is_away = True
            player.away_since = time.time()
            # Note: is_online remains True - they're still connected!
        
        # Broadcast updated state so other players see the away status
        _broadcast_game_state(socketio, room)


def _broadcast_game_state(socketio, room, include_offline=False):
    """Broadcast game state to all players in a room.
    
    Args:
        socketio: SocketIO instance
        room: Room object
        include_offline: If True, also try to send to offline players (in case they reconnected)
    """
    if room and room.game.phase == GamePhase.GAME_OVER:
        _record_game_stats(room)

    for pid, player in room.game.players.items():
        # Send to online players with valid sid
        if player.sid and player.is_online:
            try:
                state = room.game.get_state_for_player(pid)
                state['admin_id'] = room.admin_id
                socketio.emit('game_state', {
                    'game_state': state
                }, room=player.sid)
            except Exception as e:
                # Log error but don't stop broadcasting to others
                import logging
                logging.getLogger(__name__).error(f"Error broadcasting to {pid}: {e}")
        elif include_offline and player.sid:
            # Try to send to offline players too (they might have reconnected)
            try:
                state = room.game.get_state_for_player(pid)
                state['admin_id'] = room.admin_id
                socketio.emit('game_state', {
                    'game_state': state
                }, room=player.sid)
            except:
                pass  # Ignore errors for offline players


def _broadcast_to_room(socketio, room, event, data, include_offline=False):
    """Broadcast an event to all players in a room."""
    for pid, player in room.game.players.items():
        if player.sid and (player.is_online or include_offline):
            try:
                socketio.emit(event, data, room=player.sid)
            except:
                pass


def _record_game_stats(room):
    """Persist game stats for authenticated users (once per room)."""
    if not room or room.stats_recorded:
        return
    if room.game.phase != GamePhase.GAME_OVER:
        return

    room.stats_recorded = True
    logger = logging.getLogger(__name__)

    results_map = {r.get('player_id'): r for r in (room.game.game_results or [])}
    eligible_players = [
        p for p in room.game.players.values()
        if not p.is_spectator and not p.join_next_turn
    ]
    players_count = len(eligible_players)

    for player in eligible_players:
        if not player.user_id or player.is_guest:
            continue
        user = User.get_by_id(player.user_id)
        if not user:
            continue

        result = results_map.get(player.player_id, {})
        final_position = result.get('position', 0)
        final_lives = result.get('lives', player.lives)
        game_result = {
            'room_name': room.name,
            'players_count': players_count,
            'final_position': final_position,
            'final_lives': final_lives,
            'lives_lost': player.total_lives_lost,
            'bets_correct': player.total_bets_correct,
            'bets_wrong': player.total_bets_wrong,
            'tricks_won': player.total_tricks_won,
            'won': final_position == 1
        }

        try:
            user.update_stats_after_game(game_result)
        except Exception as e:
            logger.error(f"Failed to record stats for user {player.user_id}: {e}")
