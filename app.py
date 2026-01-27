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
    
    # Genera codice stanza unico
    room_code = generate_room_code()
    while room_code in games:
        room_code = generate_room_code()
    
    # Crea la partita (max 8 giocatori, ma si può iniziare con qualsiasi numero >= 2)
    game = PresinaGameOnline(room_code, 8, socketio)
    games[room_code] = game
    
    # Aggiungi il creatore come admin
    game.add_player(request.sid, player_name, is_admin=True)
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
    
    if game.has_started():
        emit('error', {'message': 'La partita è già iniziata!'})
        return
    
    if len(game.players) >= 8:
        emit('error', {'message': 'La stanza è piena (max 8 giocatori)!'})
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
    
    # Verifica che chi avvia sia l'admin
    if not game.is_admin(request.sid):
        emit('error', {'message': 'Solo l\'admin può avviare la partita!'})
        return
    
    # Verifica minimo 2 giocatori
    if len(game.players) < 2:
        emit('error', {'message': 'Servono almeno 2 giocatori per iniziare!'})
        return
    
    if len(game.players) > 8:
        emit('error', {'message': 'Massimo 8 giocatori!'})
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
            'playerName': player_name,
            'playerId': request.sid,
            'gameStarted': game.has_started(),
            'isAdmin': is_admin
        })
        
        # Invia lo stato del gioco e la mano del giocatore
        game.broadcast_game_state()
        game.send_player_hand(request.sid)
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


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
