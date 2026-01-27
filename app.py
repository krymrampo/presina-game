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


@socketio.on('create_game')
def handle_create_game(data):
    """Crea una nuova partita."""
    player_name = data.get('playerName', 'Giocatore')
    num_players = data.get('numPlayers', 2)
    
    # Genera codice stanza unico
    room_code = generate_room_code()
    while room_code in games:
        room_code = generate_room_code()
    
    # Crea la partita
    game = PresinaGameOnline(room_code, num_players, socketio)
    games[room_code] = game
    
    # Aggiungi il creatore
    game.add_player(request.sid, player_name)
    join_room(room_code)
    
    emit('game_created', {
        'roomCode': room_code,
        'playerName': player_name,
        'playerId': request.sid
    })
    
    # Notifica tutti nella stanza
    game.broadcast_game_state()


@socketio.on('join_game')
def handle_join_game(data):
    """Unisciti a una partita esistente."""
    room_code = data.get('roomCode', '').upper()
    player_name = data.get('playerName', 'Giocatore')
    
    if room_code not in games:
        emit('error', {'message': 'Stanza non trovata!'})
        return
    
    game = games[room_code]
    
    if game.is_full():
        emit('error', {'message': 'La stanza è piena!'})
        return
    
    if game.has_started():
        emit('error', {'message': 'La partita è già iniziata!'})
        return
    
    # Aggiungi il giocatore
    game.add_player(request.sid, player_name)
    join_room(room_code)
    
    emit('game_joined', {
        'roomCode': room_code,
        'playerName': player_name,
        'playerId': request.sid
    })
    
    # Notifica tutti nella stanza
    game.broadcast_game_state()


@socketio.on('start_game')
def handle_start_game(data):
    """Avvia la partita."""
    room_code = data.get('roomCode')
    
    if room_code not in games:
        emit('error', {'message': 'Stanza non trovata!'})
        return
    
    game = games[room_code]
    
    if not game.is_full():
        emit('error', {'message': f'Servono {game.max_players} giocatori per iniziare!'})
        return
    
    # Avvia la partita
    game.start_game()


@socketio.on('make_bet')
def handle_make_bet(data):
    """Gestisce la puntata di un giocatore."""
    room_code = data.get('roomCode')
    bet = data.get('bet')
    
    if room_code not in games:
        return
    
    game = games[room_code]
    game.player_bet(request.sid, bet)


@socketio.on('play_card')
def handle_play_card(data):
    """Gestisce la giocata di una carta."""
    room_code = data.get('roomCode')
    card_index = data.get('cardIndex')
    joker_mode = data.get('jokerMode', None)
    
    if room_code not in games:
        return
    
    game = games[room_code]
    game.player_play_card(request.sid, card_index, joker_mode)


@socketio.on('disconnect')
def handle_disconnect():
    """Gestisce la disconnessione di un giocatore."""
    # Trova la stanza del giocatore
    for room_code, game in list(games.items()):
        if game.has_player(request.sid):
            game.remove_player(request.sid)
            leave_room(room_code)
            
            # Se non ci sono più giocatori, rimuovi la partita
            if game.is_empty():
                del games[room_code]
            else:
                game.broadcast_game_state()
            break


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
