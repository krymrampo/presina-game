"""
PresinaGameOnline - Main game logic for online Presina.

Game rules:
- 2-8 players, each starts with 5 lives
- 5 turns with 5, 4, 3, 2, 1 cards respectively
- Special turn (1 card): players see others' cards but not their own
- Betting: last player cannot bet the number that makes sum = cards in play
- Jolly (Asso di Ori): can be 'prende' (strongest) or 'lascia' (weakest)
- End of turn: correct bet = no life lost, wrong bet = -1 life
"""
from typing import List, Dict, Optional, Tuple
from enum import Enum
import time

from .card import Card
from .player import Player
from .deck import Deck


class GamePhase(Enum):
    WAITING = "waiting"           # In lobby, waiting for players
    BETTING = "betting"           # Players making bets
    PLAYING = "playing"           # Playing cards
    WAITING_JOLLY = "waiting_jolly"  # Waiting for jolly choice
    TRICK_COMPLETE = "trick_complete" # Trick just resolved, showing cards for 3 sec
    TURN_RESULTS = "turn_results"    # Showing turn results
    GAME_OVER = "game_over"       # Game finished


class PresinaGameOnline:
    CARDS_PER_TURN = [5, 4, 3, 2, 1]
    MIN_PLAYERS = 2
    MAX_PLAYERS = 8
    
    # Time limits in seconds
    PLAYING_TIME_LIMIT = 20      # 20 seconds to play a card per trick
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: Dict[str, Player] = {}  # player_id -> Player
        self.player_order: List[str] = []     # Order of play
        self.deck = Deck()
        
        self.phase = GamePhase.WAITING
        self.current_turn = 0                 # 0-4
        self.current_trick = 0                # Current trick in the turn
        self.current_player_index = 0         # Index in player_order
        self.first_better_index = 0           # Who bets first this turn
        self.trick_starter_index = 0          # Who starts the current trick
        
        self.bets_made: List[str] = []        # player_ids in betting order
        self.cards_on_table: List[Tuple[str, Card]] = []  # (player_id, card)
        self.last_trick_cards: List[Tuple[str, Card]] = []  # Cards from last completed trick
        self.pending_jolly_player: Optional[str] = None   # Waiting for jolly choice
        self.trick_winner_id: Optional[str] = None        # Winner of last completed trick
        self.is_last_trick_of_turn: bool = False          # Was this the last trick of the turn?
        
        self.turn_results: List[dict] = []    # Results for current turn
        self.game_results: List[dict] = []    # Final standings
        
        self.messages: List[dict] = []        # Game event messages
        
        # Timer tracking
        self.phase_start_time: Optional[float] = None
        self.turn_time_limit: Optional[int] = None
    
    # ==================== Player Management ====================
    
    def add_player(self, player: Player) -> bool:
        """Add a player to the game."""
        if len(self.players) >= self.MAX_PLAYERS:
            return False
        
        if player.player_id in self.players:
            return False
        
        self.players[player.player_id] = player
        self.player_order.append(player.player_id)
        return True
    
    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the game (only in waiting phase)."""
        if self.phase != GamePhase.WAITING:
            return False
        
        if player_id in self.players:
            del self.players[player_id]
            self.player_order.remove(player_id)
            return True
        return False
    
    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID."""
        return self.players.get(player_id)
    
    def get_active_players(self) -> List[Player]:
        """Get all active (non-spectator, non-eliminated) players."""
        return [
            self.players[pid] for pid in self.player_order
            if pid in self.players 
            and not self.players[pid].is_spectator
            and not self.players[pid].is_eliminated
            and not self.players[pid].join_next_turn
        ]
    
    def get_online_active_players(self) -> List[Player]:
        """Get all online active players."""
        return [p for p in self.get_active_players() if p.is_online]
    
    # ==================== Game Flow ====================
    
    def can_start(self) -> bool:
        """Check if game can start."""
        active = self.get_active_players()
        return (
            self.phase == GamePhase.WAITING
            and len(active) >= self.MIN_PLAYERS
        )
    
    def start_game(self) -> bool:
        """Start the game."""
        if not self.can_start():
            return False
        
        self.current_turn = 0
        self.first_better_index = 0
        self._start_turn()
        return True
    
    def _start_turn(self):
        """Start a new turn."""
        # Reset players for new turn
        for player in self.players.values():
            player.reset_for_turn()
        
        # Handle players joining mid-game
        for player in self.players.values():
            if player.join_next_turn:
                player.join_next_turn = False
                player.is_spectator = False
                # Set lives to minimum of active players
                active_lives = [p.lives for p in self.get_active_players() if p != player]
                if active_lives:
                    player.lives = min(active_lives)
        
        # Deal cards
        self.deck.reset()
        cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
        
        for pid in self.player_order:
            player = self.players[pid]
            if not player.is_spectator and not player.is_eliminated:
                cards = self.deck.draw(cards_this_turn)
                player.receive_cards(cards)
        
        # Reset turn state
        self.current_trick = 0
        self.bets_made = []
        self.cards_on_table = []
        self.turn_results = []
        
        # Rotate first better
        active_ids = [p.player_id for p in self.get_active_players()]
        if active_ids:
            self.first_better_index = self.current_turn % len(active_ids)
            self.current_player_index = self.first_better_index
            self.trick_starter_index = self.first_better_index
        
        self.phase = GamePhase.BETTING
        self.phase_start_time = None  # No timer during betting
        self.turn_time_limit = None
        self._add_message('system', f"Turno {self.current_turn + 1}: {cards_this_turn} carte")

    def auto_advance_offline(self):
        """Auto-play for offline players to avoid blocking the game."""
        safety = 0
        while safety < 200:
            safety += 1

            if self.phase == GamePhase.BETTING:
                current = self.get_current_better()
                if not current or current.is_online:
                    break

                bet = self._choose_auto_bet()
                success, _ = self.make_bet(current.player_id, bet)
                if not success:
                    break
                continue

            if self.phase == GamePhase.WAITING_JOLLY:
                player_id = self.pending_jolly_player
                if not player_id:
                    self.phase = GamePhase.PLAYING
                    continue

                player = self.get_player(player_id)
                if player and not player.is_online:
                    success, _ = self._handle_jolly_choice(player_id, 'lascia')
                    if not success:
                        break
                    continue
                break

            if self.phase == GamePhase.PLAYING:
                current = self.get_current_player()
                if not current or current.is_online:
                    break

                card = self._choose_auto_card(current)
                if not card:
                    break

                if card.is_jolly:
                    success, _ = self.play_card(current.player_id, card.suit, card.value, 'lascia')
                else:
                    success, _ = self.play_card(current.player_id, card.suit, card.value)

                if not success:
                    break
                continue

            break

    def _choose_auto_bet(self) -> int:
        """Choose a safe automatic bet for offline players."""
        cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
        forbidden = self.get_forbidden_bet()
        for bet in range(cards_this_turn + 1):
            if forbidden is None or bet != forbidden:
                return bet
        return 0

    def _choose_auto_card(self, player: Player) -> Optional[Card]:
        """Choose a low-strength card for offline auto-play."""
        if not player.hand:
            return None

        def strength(card: Card) -> int:
            if card.is_jolly:
                return -1
            return card.get_strength()

        return min(player.hand, key=strength)
    
    # ==================== Betting Phase ====================
    
    def get_current_better(self) -> Optional[Player]:
        """Get the player whose turn it is to bet."""
        if self.phase != GamePhase.BETTING:
            return None
        
        active = self.get_active_players()
        if not active:
            return None
        
        # The next better is at index: first_better_index + number of bets already made
        if len(self.bets_made) >= len(active):
            return None  # All players have bet
        
        idx = (self.first_better_index + len(self.bets_made)) % len(active)
        return active[idx]
    
    def get_forbidden_bet(self) -> Optional[int]:
        """
        Get the forbidden bet for the last player.
        Returns None if not the last player.
        """
        active = self.get_active_players()
        if len(self.bets_made) != len(active) - 1:
            return None
        
        cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
        total_bets = sum(self.players[pid].bet for pid in self.bets_made)
        forbidden = cards_this_turn - total_bets
        
        if 0 <= forbidden <= cards_this_turn:
            return forbidden
        return None
    
    def make_bet(self, player_id: str, bet: int) -> Tuple[bool, str]:
        """
        Make a bet for a player.
        
        Returns:
            (success, message)
        """
        if self.phase != GamePhase.BETTING:
            return False, "Non è il momento delle puntate"
        
        player = self.get_player(player_id)
        if not player:
            return False, "Giocatore non trovato"
        
        current_better = self.get_current_better()
        if not current_better or current_better.player_id != player_id:
            return False, "Non è il tuo turno di puntare"
        
        cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
        
        if bet < 0 or bet > cards_this_turn:
            return False, f"La puntata deve essere tra 0 e {cards_this_turn}"
        
        # Check forbidden bet for last player
        forbidden = self.get_forbidden_bet()
        if forbidden is not None and bet == forbidden:
            return False, f"Non puoi puntare {forbidden} (somma uguale alle carte)"
        
        player.make_bet(bet, cards_this_turn)
        self.bets_made.append(player_id)
        self._add_message('bet', f"{player.name} punta {bet}")
        
        # Check if all bets are made
        if len(self.bets_made) == len(self.get_active_players()):
            self._start_playing()
        
        return True, "Puntata registrata"
    
    def _start_playing(self):
        """Transition from betting to playing phase."""
        self.phase = GamePhase.PLAYING
        self._start_phase_timer(self.PLAYING_TIME_LIMIT)  # 20s timer starts
        active = self.get_active_players()
        if active:
            self.trick_starter_index = self.first_better_index
            self.current_player_index = self.trick_starter_index
        self._add_message('system', "Fase di gioco iniziata")
    
    def _start_phase_timer(self, time_limit: int):
        """Start timer for current phase."""
        self.phase_start_time = time.time()
        self.turn_time_limit = time_limit
    
    def get_remaining_time(self) -> Optional[int]:
        """Get remaining time for current phase in seconds."""
        if self.phase_start_time is None or self.turn_time_limit is None:
            return None
        
        elapsed = time.time() - self.phase_start_time
        remaining = self.turn_time_limit - elapsed
        return max(0, int(remaining))
    
    def is_time_expired(self) -> bool:
        """Check if current phase time has expired."""
        if self.phase_start_time is None or self.turn_time_limit is None:
            return False
        
        elapsed = time.time() - self.phase_start_time
        return elapsed >= self.turn_time_limit
    
    def handle_timeout(self) -> Tuple[bool, str]:
        """
        Handle timeout for current phase.
        Only applies during PLAYING phase (20s per trick).
        Returns (action_taken, message)
        """
        if not self.is_time_expired():
            return False, "Time not expired"
        
        if self.phase == GamePhase.PLAYING:
            # Auto-play a random card for current player
            current = self.get_current_player()
            if current and current.hand:
                import random
                card = random.choice(current.hand)
                if card.is_jolly:
                    # Random choice for jolly too
                    choice = random.choice(['prende', 'lascia'])
                    success, msg = self.play_card(current.player_id, card.suit, card.value, choice)
                else:
                    success, msg = self.play_card(current.player_id, card.suit, card.value)
                if success:
                    return True, f"Tempo scaduto: {current.name} gioca automaticamente"
        
        return False, "No timeout action for current phase"
    
    # ==================== Playing Phase ====================
    
    def get_current_player(self) -> Optional[Player]:
        """Get the player whose turn it is to play a card."""
        if self.phase not in (GamePhase.PLAYING, GamePhase.WAITING_JOLLY):
            return None
        
        active = self.get_active_players()
        if not active:
            return None
        
        idx = (self.trick_starter_index + len(self.cards_on_table)) % len(active)
        return active[idx]
    
    def play_card(self, player_id: str, suit: str, value: int, jolly_choice: str = None) -> Tuple[bool, str]:
        """
        Play a card.
        
        Args:
            player_id: ID of the player
            suit: Card suit
            value: Card value
            jolly_choice: 'prende' or 'lascia' if playing the jolly
            
        Returns:
            (success, message)
        """
        if self.phase == GamePhase.WAITING_JOLLY:
            return self._handle_jolly_choice(player_id, jolly_choice)
        
        if self.phase != GamePhase.PLAYING:
            return False, "Non è il momento di giocare carte"
        
        player = self.get_player(player_id)
        if not player:
            return False, "Giocatore non trovato"
        
        current_player = self.get_current_player()
        if not current_player or current_player.player_id != player_id:
            return False, "Non è il tuo turno"
        
        card = player.get_card(suit, value)
        if not card:
            return False, "Non hai questa carta"
        
        # Handle jolly
        if card.is_jolly:
            if not jolly_choice:
                self.pending_jolly_player = player_id
                self.phase = GamePhase.WAITING_JOLLY
                # No timer for jolly choice - player must decide
                return True, "Scegli: prende o lascia?"
            card.jolly_choice = jolly_choice
        
        player.play_card(card)
        self.cards_on_table.append((player_id, card))
        self._add_message('play', f"{player.name} gioca {card.display_name}")
        
        # Check if trick is complete
        active = self.get_active_players()
        if len(self.cards_on_table) == len(active):
            self._resolve_trick()
        else:
            # Reset timer for next player (20 seconds)
            self._start_phase_timer(self.PLAYING_TIME_LIMIT)
        
        return True, "Carta giocata"
    
    def _handle_jolly_choice(self, player_id: str, choice: str) -> Tuple[bool, str]:
        """Handle jolly choice when in WAITING_JOLLY phase."""
        if player_id != self.pending_jolly_player:
            return False, "Non sei tu che devi scegliere"
        
        if choice not in ('prende', 'lascia'):
            return False, "Scegli 'prende' o 'lascia'"
        
        player = self.get_player(player_id)
        if not player:
            return False, "Giocatore non trovato"

        # Find the jolly in hand
        found = False
        for card in player.hand:
            if card.is_jolly:
                card.jolly_choice = choice
                player.play_card(card)
                self.cards_on_table.append((player_id, card))
                self._add_message('play', f"{player.name} gioca {card.display_name} ({choice})")
                found = True
                break

        if not found:
            return False, "Jolly non trovato"
        
        self.pending_jolly_player = None
        self.phase = GamePhase.PLAYING
        
        # Check if trick is complete
        active = self.get_active_players()
        if len(self.cards_on_table) == len(active):
            self._resolve_trick()
        else:
            # Reset timer for next player (20 seconds)
            self._start_phase_timer(self.PLAYING_TIME_LIMIT)
        
        return True, f"Jolly: {choice}"
    
    def _resolve_trick(self):
        """Resolve the current trick and determine winner."""
        if not self.cards_on_table:
            return
        
        # Find winning card
        winner_id, winner_card = self.cards_on_table[0]
        for pid, card in self.cards_on_table[1:]:
            if card.get_strength() > winner_card.get_strength():
                winner_id, winner_card = pid, card
        
        winner = self.get_player(winner_id)
        winner.win_trick()
        self._add_message('trick', f"{winner.name} vince la mano con {winner_card.display_name}")
        
        # Save winner and check if this is the last trick
        self.trick_winner_id = winner_id
        cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
        self.is_last_trick_of_turn = (self.current_trick + 1) >= cards_this_turn
        
        # Enter TRICK_COMPLETE phase - cards stay visible for 3 seconds
        self.phase = GamePhase.TRICK_COMPLETE
    
    def advance_from_trick_complete(self) -> Tuple[bool, str]:
        """Advance from TRICK_COMPLETE phase after 3 second delay."""
        if self.phase != GamePhase.TRICK_COMPLETE:
            return False, "Non è il momento"
        
        self.current_trick += 1
        
        # Set winner as next trick starter
        if self.trick_winner_id:
            active = self.get_active_players()
            for i, p in enumerate(active):
                if p.player_id == self.trick_winner_id:
                    self.trick_starter_index = i
                    break
        
        if self.is_last_trick_of_turn:
            # Last trick of turn - go to turn results
            self._end_turn()
            return True, "Fine del turno"
        else:
            # More tricks to play - clear table and continue
            self.cards_on_table = []
            self.phase = GamePhase.PLAYING
            return True, "Prossima mano"
    
    def _end_turn(self):
        """End the current turn and calculate results."""
        self.turn_results = []
        
        for player in self.get_active_players():
            change = player.apply_life_change()
            self.turn_results.append({
                'player_id': player.player_id,
                'name': player.name,
                'bet': player.bet,
                'tricks_won': player.tricks_won,
                'life_change': change,
                'lives': player.lives,
                'correct': change == 0
            })
            
            if change == 0:
                self._add_message('result', f"{player.name}: puntata corretta!")
            else:
                self._add_message('result', f"{player.name}: sbagliato, perde 1 vita")
        
        self.phase = GamePhase.TURN_RESULTS
        
        # Check for game over
        active = self.get_active_players()
        if self.current_turn >= 4 or len(active) <= 1:
            self._end_game()
    
    def ready_for_next_turn(self, player_id: str, is_admin: bool = False) -> Tuple[bool, str]:
        """Mark ready or advance to next turn (admin only advances)."""
        if self.phase != GamePhase.TURN_RESULTS:
            return False, "Non è il momento"
        
        player = self.get_player(player_id)
        if not player:
            return False, "Giocatore non trovato"
        
        # Only admin can advance to next turn
        if not is_admin:
            return False, "Solo l'admin può passare al prossimo turno"
        
        # Clear cards from table
        self.cards_on_table = []
        self.last_trick_cards = []
        
        # Admin advances the turn
        self.current_turn += 1
        if self.current_turn < 5:
            self._start_turn()
        else:
            self._end_game()
        
        return True, "Prossimo turno avviato"
    
    def _end_game(self):
        """End the game and calculate final standings."""
        self.phase = GamePhase.GAME_OVER
        
        # Sort players by lives (descending)
        all_players = list(self.players.values())
        all_players.sort(key=lambda p: p.lives, reverse=True)
        
        self.game_results = []
        for i, player in enumerate(all_players):
            self.game_results.append({
                'position': i + 1,
                'player_id': player.player_id,
                'name': player.name,
                'lives': player.lives
            })
        
        if self.game_results:
            winner = self.game_results[0]
            self._add_message('system', f"Partita finita! Vince {winner['name']} con {winner['lives']} vite!")
    
    # ==================== Special Turn (1 card) ====================
    
    def is_special_turn(self) -> bool:
        """Check if this is the special turn (1 card)."""
        return self.CARDS_PER_TURN[self.current_turn] == 1
    
    # ==================== Utility Methods ====================
    
    def _add_message(self, msg_type: str, content: str):
        """Add a game message."""
        self.messages.append({
            'type': msg_type,
            'content': content,
            'timestamp': time.time()
        })
        # Keep only last 100 messages
        if len(self.messages) > 100:
            self.messages = self.messages[-100:]
    
    def get_state_for_player(self, player_id: str) -> dict:
        """Get the game state from a specific player's perspective."""
        player = self.get_player(player_id)
        is_spectator = player is None or player.is_spectator if player else True
        
        active = self.get_active_players()
        is_special = self.is_special_turn()
        
        # Build players info
        players_info = []
        for pid in self.player_order:
            p = self.players[pid]
            # Show hand to the player themselves, or to others in special turn
            include_hand = (pid == player_id)
            others_hand_visible = (is_special and pid != player_id and self.phase in (GamePhase.BETTING, GamePhase.PLAYING))
            players_info.append(p.to_dict(include_hand=include_hand, others_hand_visible=others_hand_visible))
        
        # Current player info
        current_better = self.get_current_better()
        current_player = self.get_current_player()
        
        # Find winning card info for trick_complete phase
        trick_winner_info = None
        if self.phase == GamePhase.TRICK_COMPLETE and self.trick_winner_id:
            winner = self.get_player(self.trick_winner_id)
            if winner:
                # Find the winning card from cards_on_table
                winning_card = None
                for pid, card in self.cards_on_table:
                    if pid == self.trick_winner_id:
                        winning_card = card
                        break
                trick_winner_info = {
                    'player_id': self.trick_winner_id,
                    'player_name': winner.name,
                    'card': winning_card.to_dict() if winning_card else None
                }
        
        return {
            'room_id': self.room_id,
            'phase': self.phase.value,
            'current_turn': self.current_turn,
            'cards_this_turn': self.CARDS_PER_TURN[self.current_turn] if self.current_turn < 5 else 0,
            'current_trick': self.current_trick,
            'is_special_turn': is_special,
            'players': players_info,
            'player_order': self.player_order,
            'current_better_id': current_better.player_id if current_better else None,
            'current_player_id': current_player.player_id if current_player else None,
            'forbidden_bet': self.get_forbidden_bet(),
            'cards_on_table': [(pid, card.to_dict()) for pid, card in self.cards_on_table],
            'waiting_jolly': self.phase == GamePhase.WAITING_JOLLY,
            'pending_jolly_player': self.pending_jolly_player,
            'turn_results': self.turn_results,
            'game_results': self.game_results,
            'is_spectator': is_spectator,
            'messages': self.messages[-20:],  # Last 20 messages
            'time_remaining': self.get_remaining_time(),
            'time_limit': self.turn_time_limit,
            'trick_winner': trick_winner_info
        }
    
    def to_dict(self) -> dict:
        """Serialize full game state."""
        return {
            'room_id': self.room_id,
            'phase': self.phase.value,
            'current_turn': self.current_turn,
            'player_count': len(self.players),
            'active_count': len(self.get_active_players())
        }
