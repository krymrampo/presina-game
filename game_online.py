"""
Versione online del gioco Presina con supporto multiplayer.
"""

import random
import threading
from card import create_deck, Card
from player import Player


class PresinaGameOnline:
    """Gestisce la logica del gioco Presina per multiplayer online."""
    
    CARDS_PER_ROUND = [5, 4, 3, 2, 1]
    
    def __init__(self, room_code, max_players, socketio, room_name=None):
        """
        Inizializza una partita online di Presina.
        
        Args:
            room_code: Codice della stanza
            max_players: Numero massimo di giocatori
            socketio: Istanza di SocketIO per le comunicazioni
            room_name: Nome pubblico della stanza
        """
        self.room_code = room_code
        self.room_name = room_name or room_code
        self.max_players = max_players
        self.socketio = socketio
        self.players = []
        self.player_ids = {}  # Mappa socket_id -> Player
        self.current_round = 0
        self.current_trick = 0
        self.dealer_index = 0
        self.current_player_index = 0
        self.first_player_index = 0
        self.deck = []
        self.cards_played = []
        self.game_started = False
        self.betting_phase = False
        self.playing_phase = False
        self.waiting_for_player = None
        self.round_in_progress = False
        self.admin_socket_id = None  # Socket ID dell'admin
    
    def add_player(self, socket_id, name, is_admin=False):
        """Aggiunge un giocatore alla partita."""
        if not self.game_started:
            self.prune_disconnected()
        
        if self.connected_count() >= self.max_players:
            return False
        
        player = Player(name)
        player.socket_id = socket_id
        player.connected = True
        player.is_admin = is_admin
        self.players.append(player)
        self.player_ids[socket_id] = player
        
        if is_admin:
            self.admin_socket_id = socket_id
        
        return True

    def connected_players(self):
        """Ritorna la lista dei giocatori connessi."""
        return [p for p in self.players if getattr(p, 'connected', True)]

    def connected_count(self):
        """Ritorna il numero di giocatori connessi."""
        return len(self.connected_players())

    def prune_disconnected(self):
        """Rimuove i giocatori disconnessi prima dell'inizio partita."""
        if self.game_started:
            return
        
        removed_admin = False
        for player in list(self.players):
            if not getattr(player, 'connected', True):
                if getattr(player, 'is_admin', False):
                    removed_admin = True
                if player.socket_id in self.player_ids:
                    del self.player_ids[player.socket_id]
                self.players.remove(player)
        
        if removed_admin and self.players:
            if not any(getattr(p, 'is_admin', False) for p in self.players):
                self.players[0].is_admin = True
                self.admin_socket_id = self.players[0].socket_id
    
    def is_admin(self, socket_id):
        """Verifica se il socket_id è l'admin."""
        if socket_id in self.player_ids:
            return getattr(self.player_ids[socket_id], 'is_admin', False)
        return False
    
    def rejoin_player(self, socket_id, player_name):
        """Permette a un giocatore di rientrare nella partita."""
        # Cerca il giocatore per nome
        for player in self.players:
            if player.name == player_name:
                # Rimuovi vecchio socket_id se esiste
                old_socket_id = player.socket_id
                if old_socket_id in self.player_ids:
                    del self.player_ids[old_socket_id]
                
                # Aggiorna con nuovo socket_id
                player.socket_id = socket_id
                player.connected = True
                self.player_ids[socket_id] = player
                return True
        return False
    
    def mark_player_disconnected(self, socket_id):
        """Segna un giocatore come disconnesso senza rimuoverlo."""
        if socket_id in self.player_ids:
            player = self.player_ids[socket_id]
            player.connected = False
            
            # Notifica disconnessione temporanea
            self.socketio.emit('player_disconnected', {
                'playerName': player.name,
                'message': f'{player.name} si è disconnesso temporaneamente'
            }, room=self.room_code)
    
    def all_players_disconnected(self):
        """Verifica se tutti i giocatori sono disconnessi."""
        return all(not getattr(p, 'connected', True) for p in self.players)
    
    def remove_player(self, socket_id):
        """Rimuove un giocatore dalla partita."""
        if socket_id in self.player_ids:
            player = self.player_ids[socket_id]
            was_admin = getattr(player, 'is_admin', False)
            self.players.remove(player)
            del self.player_ids[socket_id]
            
            # Notifica disconnessione
            self.socketio.emit('player_disconnected', {
                'playerName': player.name,
                'message': f'{player.name} si è disconnesso'
            }, room=self.room_code)
            
            if was_admin:
                if self.players:
                    for p in self.players:
                        p.is_admin = False
                    self.players[0].is_admin = True
                    self.admin_socket_id = self.players[0].socket_id
                else:
                    self.admin_socket_id = None
    
    def has_player(self, socket_id):
        """Verifica se un giocatore è nella partita."""
        return socket_id in self.player_ids
    
    def is_full(self):
        """Verifica se la partita è piena."""
        return self.connected_count() >= self.max_players
    
    def is_empty(self):
        """Verifica se la partita è vuota."""
        return len(self.players) == 0
    
    def has_started(self):
        """Verifica se la partita è iniziata."""
        return self.game_started
    
    def broadcast_room_state(self):
        """Invia lo stato della stanza a tutti i giocatori (pre-partita)."""
        state = {
            'roomId': self.room_code,
            'roomName': self.room_name,
            'players': [{
                'name': p.name,
                'socketId': p.socket_id,
                'isAdmin': getattr(p, 'is_admin', False),
                'connected': getattr(p, 'connected', True)
            } for p in self.players],
            'gameStarted': self.game_started
        }
        self.socketio.emit('room_state', state, room=self.room_code)
    
    def broadcast_game_state(self):
        """Invia lo stato del gioco a tutti i giocatori."""
        state = self.get_game_state()
        self.socketio.emit('game_state', state, room=self.room_code)
    
    def get_game_state(self):
        """Ottiene lo stato corrente del gioco."""
        return {
            'roomCode': self.room_code,
            'maxPlayers': self.max_players,
            'players': [{
                'name': p.name,
                'lives': p.lives,
                'bet': p.bet if self.betting_phase or self.playing_phase else None,
                'tricksWon': p.tricks_won if self.playing_phase else 0,
                'socketId': p.socket_id,
                'isAdmin': getattr(p, 'is_admin', False)
            } for p in self.players],
            'gameStarted': self.game_started,
            'currentRound': self.current_round + 1 if self.game_started else 0,
            'totalRounds': 5,
            'cardsThisRound': self.CARDS_PER_ROUND[self.current_round] if self.game_started else 0,
            'bettingPhase': self.betting_phase,
            'playingPhase': self.playing_phase,
            'currentTrick': self.current_trick + 1 if self.playing_phase else 0,
            'waitingForPlayer': self.waiting_for_player,
            'cardsPlayed': [{
                'playerName': p.name,
                'card': self.card_to_dict(c)
            } for p, c in self.cards_played] if self.playing_phase else []
        }
    
    def send_player_hand(self, socket_id, show_own_card=True):
        """Invia la mano a un giocatore specifico."""
        if socket_id not in self.player_ids:
            return
        
        player = self.player_ids[socket_id]
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        
        # Nel turno da 1 carta, mostra le carte degli altri
        if cards_this_round == 1:
            other_players_cards = []
            for other_player in self.players:
                if other_player.socket_id != socket_id and other_player.hand:
                    other_players_cards.append({
                        'playerName': other_player.name,
                        'card': self.card_to_dict(other_player.hand[0])
                    })
            
            self.socketio.emit('player_hand', {
                'hand': [] if not show_own_card else [self.card_to_dict(c) for c in player.hand],
                'hideOwnCard': not show_own_card,
                'otherPlayersCards': other_players_cards,
                'specialRound': True
            }, room=socket_id)
        else:
            self.socketio.emit('player_hand', {
                'hand': [self.card_to_dict(c) for c in player.hand],
                'hideOwnCard': False,
                'otherPlayersCards': [],
                'specialRound': False
            }, room=socket_id)
    
    def card_to_dict(self, card):
        """Converte una carta in dizionario per JSON."""
        return {
            'suit': card.suit,
            'rank': card.rank,
            'suitName': Card.SUITS[card.suit],
            'rankName': Card.RANKS[card.rank],
            'isJoker': card.is_joker,
            'jokerMode': card.joker_mode,
            'value': card.get_value()
        }
    
    def start_game(self):
        """Avvia la partita."""
        if self.game_started:
            return
        
        self.prune_disconnected()
        connected = self.connected_count()
        if connected < 2 or connected > self.max_players:
            return
        
        self.game_started = True
        self.current_round = 0
        self.dealer_index = 0
        
        self.socketio.emit('game_started', {
            'message': 'La partita è iniziata!'
        }, room=self.room_code)
        
        # Inizia il primo turno
        self.start_round()
    
    def start_round(self):
        """Inizia un nuovo turno."""
        if self.current_round >= 5:
            self.end_game()
            return
        
        self.round_in_progress = True
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        
        # Reset giocatori
        for player in self.players:
            player.reset_for_round()
        
        # Distribuisci carte
        self.deal_cards(cards_this_round)
        
        # Invia le mani ai giocatori
        for player in self.players:
            self.send_player_hand(player.socket_id, show_own_card=(cards_this_round != 1))
        
        self.socketio.emit('round_started', {
            'round': self.current_round + 1,
            'cardsThisRound': cards_this_round
        }, room=self.room_code)
        
        # Inizia la fase di puntata
        self.start_betting_phase()
    
    def deal_cards(self, num_cards):
        """Distribuisce le carte ai giocatori."""
        self.deck = create_deck()
        random.shuffle(self.deck)
        
        for _ in range(num_cards):
            for player in self.players:
                if self.deck:
                    player.add_card(self.deck.pop())
    
    def start_betting_phase(self):
        """Inizia la fase di puntata."""
        self.betting_phase = True
        self.current_player_index = self.dealer_index
        self.waiting_for_player = self.players[self.current_player_index].name
        
        self.broadcast_game_state()
        self.request_bet()
    
    def request_bet(self):
        """Richiede la puntata al giocatore corrente."""
        player = self.players[self.current_player_index]
        is_last = (self.current_player_index == (self.dealer_index + len(self.players) - 1) % len(self.players))
        
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        total_bets = sum(p.bet for p in self.players if p.bet > 0 or p != player)
        forbidden = cards_this_round - total_bets if is_last else None
        
        self.socketio.emit('request_bet', {
            'playerName': player.name,
            'isLast': is_last,
            'forbidden': forbidden,
            'maxBet': cards_this_round,
            'totalBets': total_bets
        }, room=player.socket_id)
    
    def player_bet(self, socket_id, bet):
        """Gestisce la puntata di un giocatore."""
        if not self.betting_phase or socket_id not in self.player_ids:
            return
        
        player = self.player_ids[socket_id]
        if player != self.players[self.current_player_index]:
            return
        
        # Valida la puntata
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        is_last = (self.current_player_index == (self.dealer_index + len(self.players) - 1) % len(self.players))
        
        if bet < 0 or bet > cards_this_round:
            self.socketio.emit('error', {'message': 'Puntata non valida'}, room=socket_id)
            return
        
        if is_last:
            total_bets = sum(p.bet for p in self.players if p != player)
            forbidden = cards_this_round - total_bets
            if bet == forbidden:
                self.socketio.emit('error', {
                    'message': f'Non puoi puntare {forbidden}!'
                }, room=socket_id)
                return
        
        player.make_bet(bet)
        
        self.socketio.emit('player_bet', {
            'playerName': player.name,
            'bet': bet
        }, room=self.room_code)
        
        # Prossimo giocatore
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        
        # Controlla se tutti hanno puntato
        if self.current_player_index == self.dealer_index:
            self.end_betting_phase()
        else:
            self.waiting_for_player = self.players[self.current_player_index].name
            self.broadcast_game_state()
            self.request_bet()
    
    def end_betting_phase(self):
        """Termina la fase di puntata."""
        self.betting_phase = False
        
        total_bets = sum(p.bet for p in self.players)
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        
        self.socketio.emit('betting_complete', {
            'totalBets': total_bets,
            'cardsThisRound': cards_this_round
        }, room=self.room_code)
        
        # Inizia la fase di gioco
        self.start_playing_phase()
    
    def start_playing_phase(self):
        """Inizia la fase di gioco."""
        self.playing_phase = True
        self.current_trick = 0
        self.first_player_index = self.dealer_index
        self.start_trick()
    
    def start_trick(self):
        """Inizia una nuova mano."""
        self.cards_played = []
        self.current_player_index = self.first_player_index
        self.waiting_for_player = self.players[self.current_player_index].name
        
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        
        self.socketio.emit('trick_started', {
            'trickNumber': self.current_trick + 1,
            'totalTricks': cards_this_round,
            'firstPlayer': self.players[self.first_player_index].name
        }, room=self.room_code)
        
        self.broadcast_game_state()
        self.request_card()
    
    def request_card(self):
        """Richiede una carta al giocatore corrente."""
        player = self.players[self.current_player_index]
        
        self.socketio.emit('request_card', {
            'playerName': player.name
        }, room=player.socket_id)
    
    def player_play_card(self, socket_id, card_index, joker_mode=None):
        """Gestisce la giocata di una carta."""
        if not self.playing_phase or socket_id not in self.player_ids:
            return
        
        player = self.player_ids[socket_id]
        if player != self.players[self.current_player_index]:
            return
        
        if card_index < 0 or card_index >= len(player.hand):
            self.socketio.emit('error', {'message': 'Carta non valida'}, room=socket_id)
            return
        
        card = player.hand[card_index]
        
        # Gestione jolly
        if card.is_joker:
            if joker_mode not in ['prende', 'lascia']:
                self.socketio.emit('request_joker_mode', {
                    'message': 'Scegli se il jolly prende o lascia'
                }, room=socket_id)
                return
            card.set_joker_mode(joker_mode)
        
        player.remove_card(card)
        self.cards_played.append((player, card))
        
        self.socketio.emit('card_played', {
            'playerName': player.name,
            'card': self.card_to_dict(card)
        }, room=self.room_code)
        
        # Prossimo giocatore
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        
        # Controlla se tutti hanno giocato
        if len(self.cards_played) == len(self.players):
            self.end_trick()
        else:
            self.waiting_for_player = self.players[self.current_player_index].name
            self.broadcast_game_state()
            self.request_card()
    
    def end_trick(self):
        """Termina una mano."""
        # Determina il vincitore
        winner = max(self.cards_played, key=lambda x: x[1].get_value())
        winner_player = winner[0]
        winner_card = winner[1]
        
        winner_player.win_trick()
        
        self.socketio.emit('trick_won', {
            'winnerName': winner_player.name,
            'winningCard': self.card_to_dict(winner_card)
        }, room=self.room_code)
        
        # Imposta il vincitore come primo giocatore della prossima mano
        self.first_player_index = self.players.index(winner_player)
        
        # Prossima mano
        self.current_trick += 1
        cards_this_round = self.CARDS_PER_ROUND[self.current_round]
        
        if self.current_trick >= cards_this_round:
            self.end_round()
        else:
            # Aspetta un po' prima della prossima mano
            threading.Timer(2, self.start_trick).start()
    
    def end_round(self):
        """Termina un turno."""
        self.playing_phase = False
        self.round_in_progress = False
        
        # Verifica le puntate
        results = []
        for player in self.players:
            correct = player.check_bet()
            result = {
                'playerName': player.name,
                'bet': player.bet,
                'tricksWon': player.tricks_won,
                'correct': correct,
                'lives': player.lives
            }
            
            if not correct:
                player.lose_life()
                result['lives'] = player.lives
            
            results.append(result)
        
        self.socketio.emit('round_ended', {
            'results': results
        }, room=self.room_code)
        
        # Prossimo turno
        self.current_round += 1
        self.dealer_index = (self.dealer_index + 1) % len(self.players)
        
        if self.current_round < 5:
            threading.Timer(5, self.start_round).start()
        else:
            self.end_game()
    
    def end_game(self):
        """Termina la partita."""
        self.game_started = False
        
        # Determina il vincitore
        max_lives = max(p.lives for p in self.players)
        winners = [p for p in self.players if p.lives == max_lives]
        
        self.socketio.emit('game_ended', {
            'winners': [w.name for w in winners],
            'maxLives': max_lives,
            'finalStandings': [{
                'playerName': p.name,
                'lives': p.lives
            } for p in sorted(self.players, key=lambda x: x.lives, reverse=True)]
        }, room=self.room_code)
