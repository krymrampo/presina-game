"""
Server Flask per il gioco Presina multiplayer online.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
from game_online import PresinaGameOnline

app = Flask(__name__)
app.config['SECRET_KEY'] = 'presina_secret_key_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Dizionario per memorizzare le stanze di gioco
games = {}

def generate_room_code():
    """Genera un codice stanza casuale."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@app.route('/')
def index():
    """Pagina principale."""
    return render_template('index.html')


@socketio.on('get_rooms')
def handle_get_rooms():
    """Restituisce la lista delle stanze pubbliche."""
    rooms_list = []
    for room_id, game in games.items():
        rooms_list.append({
            'id': room_id,
            'name': game.room_name,
            'playerCount': game.connected_count(),
            'started': game.has_started()
        })
    
    emit('rooms_list', rooms_list)


@socketio.on('create_room')
def handle_create_room(data):
    """Crea una nuova stanza pubblica."""
    player_name = data.get('playerName', 'Giocatore')
    room_name = data.get('roomName', 'Stanza senza nome')
    
    # Genera codice stanza unico
    room_code = generate_room_code()
    while room_code in games:
        room_code = generate_room_code()
    
    # Crea la partita (max 8 giocatori)
    game = PresinaGameOnline(room_code, 8, socketio, room_name)
    games[room_code] = game
    
    # Aggiungi il creatore come admin
    game.add_player(request.sid, player_name, is_admin=True)
    join_room(room_code)
    
    emit('room_created', {
        'roomId': room_code,
        'roomName': room_name,
        'playerName': player_name,
        'playerId': request.sid
    })
    
    # Notifica tutti nella stanza
    game.broadcast_room_state()
    
    # Notifica tutti gli altri della nuova stanza (per aggiornare la lobby)
    socketio.emit('rooms_list', get_rooms_list())


@socketio.on('join_room')
def handle_join_room(data):
    """Unisciti a una stanza esistente."""
    room_id = data.get('roomId', '')
    player_name = data.get('playerName', 'Giocatore')
    join_mode = data.get('joinMode', None)
    
    if room_id not in games:
        emit('error', {'message': 'Stanza non trovata!'})
        return
    
    game = games[room_id]
    
    if game.has_started():
        if join_mode == 'player':
            if game.is_full_for_new_players():
                emit('error', {'message': 'La stanza è piena (max 8 giocatori)!'})
                return
            game.add_pending_player(request.sid, player_name)
            join_room(room_id)
            min_lives = min((p.lives for p in game.players), default=1)
            emit('pending_joined', {
                'roomId': room_id,
                'roomName': game.room_name,
                'playerName': player_name,
                'playerId': request.sid,
                'minLives': min_lives
            })
            emit('game_state', game.get_game_state(), room=request.sid)
            return
        # Default spettatore
        game.add_spectator(request.sid, player_name)
        join_room(room_id)
        emit('spectator_joined', {
            'roomId': room_id,
            'roomName': game.room_name,
            'playerName': player_name,
            'playerId': request.sid
        })
        emit('game_state', game.get_game_state(), room=request.sid)
        return
    
    if game.connected_count() >= game.max_players:
        emit('error', {'message': 'La stanza è piena (max 8 giocatori)!'})
        return
    
    # Aggiungi il giocatore
    if not game.add_player(request.sid, player_name):
        emit('error', {'message': 'La stanza è piena (max 8 giocatori)!'})
        return
    join_room(room_id)
    
    emit('room_joined', {
        'roomId': room_id,
        'roomName': game.room_name,
        'playerName': player_name,
        'playerId': request.sid
    })
    
    # Notifica tutti nella stanza
    game.broadcast_room_state()
    
    # Aggiorna la lobby per tutti
    socketio.emit('rooms_list', get_rooms_list())


@socketio.on('leave_room')
def handle_leave_room(data):
    """Lascia una stanza."""
    room_id = data.get('roomId', '')
    
    if room_id not in games:
        return
    
    game = games[room_id]
    if game.has_player(request.sid):
        game.remove_player(request.sid)
    elif game.has_pending_player(request.sid):
        game.remove_pending_player(request.sid)
    elif game.has_spectator(request.sid):
        game.remove_spectator(request.sid)
    leave_room(room_id)
    
    # Se la stanza è vuota, eliminala
    if len(game.players) == 0 and len(game.pending_players) == 0:
        del games[room_id]
    else:
        if game.has_started():
            game.broadcast_game_state()
        else:
            game.broadcast_room_state()
    
    # Aggiorna la lobby per tutti
    socketio.emit('rooms_list', get_rooms_list())


@socketio.on('kick_player')
def handle_kick_player(data):
    """Rimuove un giocatore dalla stanza (solo admin, pre-partita)."""
    room_id = data.get('roomId', '')
    target_id = data.get('targetId', '')
    
    if room_id not in games:
        emit('error', {'message': 'Stanza non trovata!'})
        return
    
    game = games[room_id]
    
    if game.has_started():
        emit('error', {'message': 'Non puoi rimuovere giocatori a partita iniziata!'})
        return
    
    if not game.is_admin(request.sid):
        emit('error', {'message': 'Solo l\'admin può rimuovere giocatori!'})
        return
    
    if not target_id or target_id == request.sid:
        emit('error', {'message': 'Giocatore non valido!'})
        return
    
    if not game.has_player(target_id):
        emit('error', {'message': 'Giocatore non trovato!'})
        return
    
    game.remove_player(target_id)
    leave_room(room_id, sid=target_id)
    socketio.emit('kicked', {
        'message': 'Sei stato rimosso dalla stanza'
    }, room=target_id)
    
    if len(game.players) == 0:
        del games[room_id]
    else:
        game.broadcast_room_state()
    
    socketio.emit('rooms_list', get_rooms_list())


def get_rooms_list():
    """Helper per ottenere la lista delle stanze."""
    rooms_list = []
    for room_id, game in games.items():
        rooms_list.append({
            'id': room_id,
            'name': game.room_name,
            'playerCount': game.connected_count(),
            'started': game.has_started()
        })
    return rooms_list


@socketio.on('create_game')
def handle_create_game(data):
    """Crea una nuova partita (legacy, reindirizza a create_room)."""
    data['roomName'] = 'Stanza di ' + data.get('playerName', 'Giocatore')
    handle_create_room(data)


@socketio.on('join_game')
def handle_join_game(data):
    """Unisciti a una partita esistente (legacy, reindirizza a join_room)."""
    data['roomId'] = data.get('roomCode', '').upper()
    handle_join_room(data)


@socketio.on('start_game')
def handle_start_game(data):
    """Avvia la partita."""
    room_code = data.get('roomCode') or data.get('roomId')
    
    if room_code not in games:
        emit('error', {'message': 'Stanza non trovata!'})
        return
    
    game = games[room_code]
    
    # Verifica che chi avvia sia l'admin
    if not game.is_admin(request.sid):
        emit('error', {'message': 'Solo l\'admin può avviare la partita!'})
        return
    
    # Verifica minimo 2 giocatori
    connected_players = game.connected_count()
    if connected_players < 2:
        emit('error', {'message': 'Servono almeno 2 giocatori per iniziare!'})
        return
    
    if connected_players > game.max_players:
        emit('error', {'message': 'Massimo 8 giocatori!'})
        return
    
    # Avvia la partita
    game.start_game()


@socketio.on('make_bet')
def handle_make_bet(data):
    """Gestisce la puntata di un giocatore."""
    room_code = data.get('roomCode') or data.get('roomId')
    bet = data.get('bet')
    
    if room_code not in games:
        return
    
    game = games[room_code]
    game.player_bet(request.sid, bet)


@socketio.on('play_card')
def handle_play_card(data):
    """Gestisce la giocata di una carta."""
    room_code = data.get('roomCode') or data.get('roomId')
    card_index = data.get('cardIndex')
    joker_mode = data.get('jokerMode', None)
    
    if room_code not in games:
        return
    
    game = games[room_code]
    game.player_play_card(request.sid, card_index, joker_mode)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Gestisce i messaggi chat."""
    room_code = data.get('roomCode') or data.get('roomId')
    message = (data.get('message') or '').strip()

    if not room_code or room_code not in games or not message:
        return

    # Limita la lunghezza per evitare spam o payload eccessivi
    if len(message) > 200:
        message = message[:200]

    game = games[room_code]
    player = game.player_ids.get(request.sid)
    if player:
        player_name = player.name
    elif request.sid in game.pending_players:
        player_name = game.pending_players.get(request.sid, 'Giocatore')
    else:
        player_name = game.spectators.get(request.sid, data.get('playerName', 'Giocatore'))

    socketio.emit('chat_message', {
        'playerName': player_name,
        'message': message
    }, room=room_code)

@socketio.on('next_round')
def handle_next_round(data):
    """Segna il giocatore come pronto per il prossimo turno."""
    room_code = data.get('roomCode') or data.get('roomId')
    
    if room_code not in games:
        return
    
    game = games[room_code]
    if not game.has_started():
        return
    
    game.mark_ready_for_next_round(request.sid)


@socketio.on('rejoin_game')
def handle_rejoin_game(data):
    """Permette a un giocatore di rientrare dopo un refresh."""
    room_code = data.get('roomCode', '').upper()
    player_name = data.get('playerName', '')
    
    if room_code not in games:
        emit('rejoin_failed', {'message': 'La stanza non esiste più'})
        return
    
    game = games[room_code]
    
    # Prova a riconnettere il giocatore
    success = game.rejoin_player(request.sid, player_name)
    
    if success:
        join_room(room_code)
        
        # Controlla se questo giocatore è admin
        is_admin = game.is_admin(request.sid)
        
        emit('rejoin_success', {
            'roomCode': room_code,
            'roomName': game.room_name,
            'playerName': player_name,
            'playerId': request.sid,
            'gameStarted': game.has_started(),
            'isAdmin': is_admin
        })
        
        # Invia lo stato corretto in base alla fase
        if game.has_started():
            game.broadcast_game_state()
            game.send_player_hand(request.sid)
        else:
            game.broadcast_room_state()
    else:
        emit('rejoin_failed', {'message': 'Impossibile rientrare nella partita'})


@socketio.on('disconnect')
def handle_disconnect():
    """Gestisce la disconnessione di un giocatore."""
    # Trova la stanza del giocatore
    for room_code, game in list(games.items()):
        if game.has_player(request.sid):
            # Non rimuovere il giocatore, segna solo come disconnesso
            game.mark_player_disconnected(request.sid)
            leave_room(room_code)
            
            # Se tutti sono disconnessi, rimuovi la partita dopo un timeout
            if game.all_players_disconnected():
                del games[room_code]
            else:
                game.broadcast_game_state()
            break
        if game.has_pending_player(request.sid):
            game.remove_pending_player(request.sid)
            leave_room(room_code)
            break
        if game.has_spectator(request.sid):
            game.remove_spectator(request.sid)
            leave_room(room_code)
            break


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
