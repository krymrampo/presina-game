"""
Game Socket.IO events.
"""
import time
import logging
from flask import request
from flask_socketio import emit, join_room

from models.user import User
from rooms.room_manager import room_manager
from game.presina_game import GamePhase
from sockets.utils import verify_player_socket

logger = logging.getLogger(__name__)

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
        
        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return

            room.game.tick()
            
            if room.admin_id != player_id:
                emit('error', {'message': 'Solo l\'admin può avviare la partita'})
                return
            
            if not room.game.can_start():
                emit('error', {'message': 'Servono almeno 2 giocatori'})
                return
            
            room.game.start_game()
        
        _broadcast_game_state(socketio, room)
        
        socketio.emit('rooms_list', {
            'rooms': [r.to_dict() for r in room_manager.get_public_rooms()]
        })
    
    @socketio.on('play_again')
    def handle_play_again(data):
        """
        Reset the game in the same room (admin only, after game over).
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            emit('error', {'message': 'ID giocatore mancante'})
            return
        
        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return
            
            if room.admin_id != player_id:
                emit('error', {'message': 'Solo l\'admin può riavviare la partita'})
                return
            
            if not room.game.reset_game():
                emit('error', {'message': 'La partita non è ancora terminata'})
                return
            
            # Allow stats to be recorded again for the next game
            room.stats_recorded = False
            room.update_activity()
        
        # Broadcast updated state – players will see the waiting room
        _broadcast_game_state(socketio, room)
        
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
        
        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        try:
            bet_value = int(bet)
            if bet_value < 0:
                emit('error', {'message': 'La puntata non può essere negativa'})
                return
        except (ValueError, TypeError):
            emit('error', {'message': 'Puntata non valida'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return

            room.game.tick()
            success, message = room.game.make_bet(player_id, bet_value)
        
        if not success:
            emit('error', {'message': message})
            return

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
        
        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        try:
            card_value = int(value)
        except (ValueError, TypeError):
            emit('error', {'message': 'Valore carta non valido'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return

            room.game.tick()
            success, message = room.game.play_card(player_id, suit, card_value, jolly_choice)
            waiting_jolly = (room.game.phase == GamePhase.WAITING_JOLLY
                             and room.game.pending_jolly_player == player_id)
        
        if not success:
            emit('error', {'message': message})
            return

        if waiting_jolly:
            emit('jolly_choice_required', {'message': 'Scegli: prende o lascia?'})
            # Also broadcast so other players see WAITING_JOLLY status
            _broadcast_game_state(socketio, room)
        else:
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

        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return
            
            success, message = room.game.play_card(player_id, None, None, choice)
        
        if not success:
            emit('error', {'message': message})
            return

        _broadcast_game_state(socketio, room)
    
    @socketio.on('advance_trick')
    def handle_advance_trick(data):
        """
        Advance from TRICK_COMPLETE phase after 3 second display.
        Data: { player_id }
        Lock ensures only the first call actually advances.
        """
        player_id = data.get('player_id')
        
        if not player_id:
            return
        
        if not verify_player_socket(player_id, request.sid):
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                return
            
            player = room.game.get_player(player_id)
            if not player:
                return
            
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

        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                emit('error', {'message': 'Non sei in nessuna stanza'})
                return
            
            player = room.game.get_player(player_id)
            if player and player.sid != request.sid:
                player.sid = request.sid
                player.is_online = True
                player.offline_since = None
                # Re-join the socket.io room so chat broadcasts work
                join_room(room.room_id)
            
            room.game.tick()
            state = room.game.get_state_for_player(player_id)
            state['admin_id'] = room.admin_id

        emit('game_state', {'game_state': state})
    
    @socketio.on('ping')
    def handle_ping(data):
        """
        Heartbeat/ping from client to keep connection alive.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        if player_id:
            with room_manager.lock:
                room = room_manager.get_player_room(player_id)
                if room:
                    player = room.game.get_player(player_id)
                    if player:
                        player.is_online = True
                        player.offline_since = None
                        player.last_activity = time.time()
                        if player.sid != request.sid:
                            player.sid = request.sid
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
        
        if not verify_player_socket(player_id, request.sid):
            return
        
        with room_manager.lock:
            room = room_manager.get_player_room(player_id)
            if not room:
                return
            
            player = room.game.get_player(player_id)
            if not player:
                return
            
            if is_visible:
                player.is_away = False
                player.away_since = None
                player.is_online = True
                player.offline_since = None
                player.last_activity = time.time()
            else:
                player.is_away = True
                player.away_since = time.time()
        
        _broadcast_game_state(socketio, room)


def _broadcast_game_state(socketio, room, include_offline=False):
    """Broadcast game state to all players in a room.
    
    Calls tick() once before building per-player states.
    """
    if not room:
        return

    with room_manager.lock:
        room.game.tick()

        if room.game.phase == GamePhase.GAME_OVER:
            _record_game_stats(room)

        # Build all states while holding lock
        states_to_send = []
        for pid, player in room.game.players.items():
            if player.sid and (player.is_online or include_offline):
                try:
                    state = room.game.get_state_for_player(pid)
                    state['admin_id'] = room.admin_id
                    states_to_send.append((player.sid, state))
                except Exception as e:
                    logger.error(f"Error building state for {pid}: {e}")

    # Emit outside lock (I/O)
    for sid, state in states_to_send:
        try:
            socketio.emit('game_state', {'game_state': state}, room=sid)
        except Exception as e:
            logger.error(f"Error emitting to {sid}: {e}")


def _broadcast_to_room(socketio, room, event, data, include_offline=False):
    """Broadcast an event to all players in a room."""
    targets = []
    with room_manager.lock:
        for pid, player in room.game.players.items():
            if player.sid and (player.is_online or include_offline):
                targets.append(player.sid)
    for sid in targets:
        try:
            socketio.emit(event, data, room=sid)
        except Exception:
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
        if not p.is_spectator and not p.join_next_turn and not p.is_bot
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
