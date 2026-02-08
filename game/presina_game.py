"""
PresinaGameOnline - Main game logic for online Presina.

Game rules:
- 2-8 players, each starts with 5 lives
- 5 turns with 5, 4, 3, 2, 1 cards respectively
- Special turn (1 card): players see others' cards but not their own
- Betting: last player cannot bet the number that makes sum = cards in play (except 1-card round)
- Jolly (Asso di Ori): can be 'prende' (strongest) or 'lascia' (weakest)
- End of turn: correct bet = no life lost, wrong bet = -1 life
- Special round repeat: if everyone is correct in the 1-card round, it repeats until someone is wrong
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
    TURN_TIMEOUT_SECONDS = 30
    
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
        self.last_turn_all_correct: bool = False  # Track if last turn had no mistakes
        
        self.messages: List[dict] = []        # Game event messages
        self._last_offline_check: float = 0   # Last time we checked for offline players

        # Turn timer (betting/playing/jolly)
        self.turn_timer_deadline: Optional[float] = None
        self.turn_timer_player_id: Optional[str] = None
        self.turn_timer_type: Optional[str] = None  # 'betting' | 'playing' | 'jolly'
    
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

    def force_remove_player(self, player_id: str) -> bool:
        """Force remove a player even if the game has started."""
        if player_id not in self.players:
            return False

        # Remove references first
        self.bets_made = [pid for pid in self.bets_made if pid != player_id]
        self.cards_on_table = [(pid, card) for pid, card in self.cards_on_table if pid != player_id]
        self.last_trick_cards = [(pid, card) for pid, card in self.last_trick_cards if pid != player_id]

        if self.pending_jolly_player == player_id:
            self.pending_jolly_player = None
            if self.phase == GamePhase.WAITING_JOLLY:
                self.phase = GamePhase.PLAYING

        if self.trick_winner_id == player_id:
            self.trick_winner_id = None

        # Remove player from game
        del self.players[player_id]
        if player_id in self.player_order:
            self.player_order.remove(player_id)

        # Recompute indices to keep them in range
        active = self.get_active_players()
        if active:
            self.first_better_index = self.first_better_index % len(active)
            self.trick_starter_index = self.trick_starter_index % len(active)
            self.current_player_index = self.trick_starter_index
        else:
            self.first_better_index = 0
            self.trick_starter_index = 0
            self.current_player_index = 0

        # If betting/playing, check if we can advance
        if self.phase == GamePhase.BETTING:
            if active and len(self.bets_made) >= len(active):
                self._start_playing()
        elif self.phase in (GamePhase.PLAYING, GamePhase.WAITING_JOLLY):
            if active and len(self.cards_on_table) >= len(active):
                self._resolve_trick()

        self._sync_turn_timer()
        return True
    
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
        # Reset last turn correctness flag
        self.last_turn_all_correct = False

        # Remove bot players from previous turn
        bot_ids = [pid for pid, p in self.players.items() if p.is_bot]
        for pid in bot_ids:
            bot_name = self.players[pid].name
            self.force_remove_player(pid)
            self._add_message('system', f"🤖 {bot_name} è stato rimosso dalla partita")

        # Check if enough real players remain after bot removal
        active = self.get_active_players()
        if len(active) < self.MIN_PLAYERS:
            if len(active) == 1:
                self._add_message('system', f"{active[0].name} è l'ultimo giocatore rimasto!")
            self._end_game()
            return

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
        self._add_message('system', f"Turno {self.current_turn + 1}: {cards_this_turn} carte")
        self._sync_turn_timer()

    def auto_advance_offline(self):
        """Auto-play disabled - game waits for players indefinitely."""
        pass

    def _clear_turn_timer(self):
        self.turn_timer_deadline = None
        self.turn_timer_player_id = None
        self.turn_timer_type = None

    def _set_turn_timer(self, player_id: Optional[str], timer_type: str):
        if not player_id:
            self._clear_turn_timer()
            return
        self.turn_timer_player_id = player_id
        self.turn_timer_type = timer_type
        self.turn_timer_deadline = time.time() + self.TURN_TIMEOUT_SECONDS

    def _sync_turn_timer(self):
        """Ensure timer is aligned with current game state without resetting unnecessarily."""
        if self.phase == GamePhase.BETTING:
            current = self.get_current_better()
            current_id = current.player_id if current else None
            timer_type = 'betting'
        elif self.phase == GamePhase.PLAYING:
            current = self.get_current_player()
            current_id = current.player_id if current else None
            timer_type = 'playing'
        elif self.phase == GamePhase.WAITING_JOLLY:
            current_id = self.pending_jolly_player
            timer_type = 'jolly'
        else:
            self._clear_turn_timer()
            return

        if current_id is None:
            self._clear_turn_timer()
            return

        if self.turn_timer_player_id != current_id or self.turn_timer_type != timer_type:
            self._set_turn_timer(current_id, timer_type)

    def check_and_handle_turn_timeout(self) -> bool:
        """Auto-advance a turn if the active player exceeds the time limit."""
        if self.phase not in (GamePhase.BETTING, GamePhase.PLAYING, GamePhase.WAITING_JOLLY):
            self._clear_turn_timer()
            return False

        if not self.turn_timer_deadline or not self.turn_timer_player_id or not self.turn_timer_type:
            self._sync_turn_timer()
            return False

        if time.time() < self.turn_timer_deadline:
            return False

        # Timer expired: verify still same active player
        if self.phase == GamePhase.BETTING:
            current = self.get_current_better()
            current_id = current.player_id if current else None
        elif self.phase == GamePhase.PLAYING:
            current = self.get_current_player()
            current_id = current.player_id if current else None
        else:
            current_id = self.pending_jolly_player

        if not current_id:
            self._clear_turn_timer()
            return False

        if current_id != self.turn_timer_player_id:
            self._sync_turn_timer()
            return False

        self._auto_timeout_player(current_id)
        self._sync_turn_timer()
        return True
    
    def check_and_handle_offline_player(self, force_check: bool = False):
        """
        Check if the current player is offline and handle it.
        If player is offline for too long during their turn, auto-skip or auto-play.
        
        Note: Players who are just 'away' (tab switched/minimized) are NOT auto-skipped.
        Only truly disconnected players (socket closed) are auto-skipped.
        
        Args:
            force_check: If True, check immediately even if we checked recently
        """
        OFFLINE_TIMEOUT_SECONDS = 60  # 1 minute timeout for turn
        CHECK_INTERVAL = 5  # Check every 5 seconds max
        
        now = time.time()
        
        # Rate limit checks unless forced
        if not force_check and now - self._last_offline_check < CHECK_INTERVAL:
            return
        self._last_offline_check = now
        
        if self.phase == GamePhase.WAITING or self.phase == GamePhase.GAME_OVER:
            return
        
        if self.phase == GamePhase.BETTING:
            current = self.get_current_better()
        elif self.phase in (GamePhase.PLAYING, GamePhase.WAITING_JOLLY):
            current = self.get_current_player()
        else:
            return
        
        if not current:
            return
        
        # IMPORTANT: Only auto-skip if player is truly offline (socket disconnected)
        # Do NOT auto-skip if player is just 'away' (tab switched/minimized)
        if not current.is_online and not current.is_away and current.offline_since:
            offline_duration = now - current.offline_since
            if offline_duration >= OFFLINE_TIMEOUT_SECONDS:
                self._auto_skip_player(current.player_id)
    
    def _auto_skip_player(self, player_id: str):
        """
        Automatically skip a player's turn when they're offline too long.
        For betting: bet 0
        For playing: play first available card
        """
        player = self.get_player(player_id)
        if not player:
            return
        
        self._add_message('system', f"{player.name} è offline - turno automatico")
        
        if self.phase == GamePhase.BETTING:
            # Auto-bet 0 (safest bet)
            cards_this_turn = self.CARDS_PER_TURN[self.current_turn]
            # Check if 0 is allowed (not forbidden)
            forbidden = self.get_forbidden_bet()
            if forbidden == 0:
                # Bet 1 instead if 0 is forbidden
                self.make_bet(player_id, 1)
            else:
                self.make_bet(player_id, 0)
                
        elif self.phase == GamePhase.PLAYING:
            # Auto-play first available card
            if player.hand:
                card = player.hand[0]  # Play first card
                # Check if it's jolly
                if card.is_jolly:
                    # Default to 'prende'
                    self.play_card(player_id, card.suit, card.value, 'prende')
                else:
                    self.play_card(player_id, card.suit, card.value)
                    
        elif self.phase == GamePhase.WAITING_JOLLY and self.pending_jolly_player == player_id:
            # Auto-choose 'prende' for jolly
            self.play_card(player_id, None, None, 'prende')

    def _auto_timeout_player(self, player_id: str):
        """
        Automatically act when a player exceeds the turn timer.
        For betting: bet 0 (or 1 if 0 forbidden)
        For playing: play first available card (jolly -> 'prende')
        For jolly: auto-choose 'prende'
        """
        player = self.get_player(player_id)
        if not player:
            return

        self._add_message('system', f"{player.name} ha finito il tempo - turno automatico")

        if self.phase == GamePhase.BETTING:
            forbidden = self.get_forbidden_bet()
            auto_bet = 1 if forbidden == 0 else 0
            self.make_bet(player_id, auto_bet)
        elif self.phase == GamePhase.PLAYING:
            if player.hand:
                card = player.hand[0]
                if card.is_jolly:
                    self.play_card(player_id, card.suit, card.value, 'prende')
                else:
                    self.play_card(player_id, card.suit, card.value)
        elif self.phase == GamePhase.WAITING_JOLLY and self.pending_jolly_player == player_id:
            self.play_card(player_id, None, None, 'prende')

    def mark_as_bot(self, player_id: str) -> bool:
        """Mark a player as bot-controlled (after abandon). Bot finishes current turn."""
        player = self.get_player(player_id)
        if not player:
            return False
        player.is_bot = True
        player.is_online = False
        player.offline_since = None  # Don't trigger offline timeout
        player.sid = None
        self._add_message('system', f"🤖 {player.name} ha abbandonato – un bot giocherà al suo posto per questo turno")
        return True

    def _handle_bot_auto_play(self, _depth: int = 0):
        """Immediately auto-play for any bot whose turn it is."""
        if _depth > 20:  # Safety: max 20 chained bot actions
            return
        if self.phase not in (GamePhase.BETTING, GamePhase.PLAYING, GamePhase.WAITING_JOLLY):
            return

        # Determine current player
        if self.phase == GamePhase.BETTING:
            current = self.get_current_better()
        elif self.phase == GamePhase.WAITING_JOLLY:
            current = self.get_player(self.pending_jolly_player) if self.pending_jolly_player else None
        else:
            current = self.get_current_player()

        if not current or not current.is_bot:
            return

        # Bot plays immediately (no delay)
        self._add_message('system', f"🤖 {current.name} (Bot) gioca automaticamente")

        if self.phase == GamePhase.BETTING:
            forbidden = self.get_forbidden_bet()
            auto_bet = 1 if forbidden == 0 else 0
            self.make_bet(current.player_id, auto_bet)
        elif self.phase == GamePhase.PLAYING:
            if current.hand:
                card = current.hand[0]
                if card.is_jolly:
                    self.play_card(current.player_id, card.suit, card.value, 'prende')
                else:
                    self.play_card(current.player_id, card.suit, card.value)
        elif self.phase == GamePhase.WAITING_JOLLY and self.pending_jolly_player == current.player_id:
            self.play_card(current.player_id, None, None, 'prende')

        # After playing, the game may have advanced to another bot's turn
        # Recurse to handle chains of bots (e.g. multiple bots betting in sequence)
        self._handle_bot_auto_play(_depth + 1)

    def get_real_active_players(self) -> List[Player]:
        """Get active players that are NOT bots (real humans still in the game)."""
        return [p for p in self.get_active_players() if not p.is_bot]
    
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
        # Special (1 card) turn: sum can equal cards
        if self.is_special_turn():
            return None

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
        else:
            next_better = self.get_current_better()
            if next_better:
                self._set_turn_timer(next_better.player_id, 'betting')
        
        return True, "Puntata registrata"
    
    def _start_playing(self):
        """Transition from betting to playing phase."""
        self.phase = GamePhase.PLAYING
        active = self.get_active_players()
        if active:
            self.trick_starter_index = self.first_better_index
            self.current_player_index = self.trick_starter_index
        self._add_message('system', "Fase di gioco iniziata")
        current = self.get_current_player()
        if current:
            self._set_turn_timer(current.player_id, 'playing')
        else:
            self._clear_turn_timer()
    
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
                # Timer for jolly choice
                self._set_turn_timer(player_id, 'jolly')
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
            next_player = self.get_current_player()
            if next_player:
                self._set_turn_timer(next_player.player_id, 'playing')
        
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
            next_player = self.get_current_player()
            if next_player:
                self._set_turn_timer(next_player.player_id, 'playing')
        
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
        self._clear_turn_timer()
    
    def advance_from_trick_complete(self) -> Tuple[bool, str]:
        """Advance from TRICK_COMPLETE phase after 3 second delay."""
        if self.phase != GamePhase.TRICK_COMPLETE:
            return False, "Non è il momento"
        
        # Set winner as next trick starter
        if self.trick_winner_id:
            active = self.get_active_players()
            for i, p in enumerate(active):
                if p.player_id == self.trick_winner_id:
                    self.trick_starter_index = i
                    break
        
        if self.is_last_trick_of_turn:
            # Last trick of turn - go to turn results
            # Don't increment current_trick since the turn is ending
            self._end_turn()
            return True, "Fine del turno"
        else:
            # More tricks to play - increment trick counter and continue
            self.current_trick += 1
            self.cards_on_table = []
            self.phase = GamePhase.PLAYING
            current = self.get_current_player()
            if current:
                self._set_turn_timer(current.player_id, 'playing')
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
            
            # Track per-game totals for stats
            player.total_tricks_won += player.tricks_won
            if change == 0:
                player.total_bets_correct += 1
            else:
                player.total_bets_wrong += 1
                player.total_lives_lost += abs(change)
            
            if change == 0:
                self._add_message('result', f"{player.name}: puntata corretta!")
            else:
                self._add_message('result', f"{player.name}: sbagliato, perde 1 vita")

        # Track if everyone was correct this turn
        self.last_turn_all_correct = all(r.get('correct') for r in self.turn_results)

        self.phase = GamePhase.TURN_RESULTS
        self._clear_turn_timer()

        # Check for game over
        active = self.get_active_players()
        if len(active) <= 1:
            self._end_game()
        elif self.current_turn >= 4:
            # On last turn, only end if someone made a mistake
            if not self.last_turn_all_correct:
                self._end_game()
            else:
                self._add_message('system', "Nessuno sbaglia: il turno da 1 carta si ripete")
    
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
        if self.current_turn >= 4 and self.last_turn_all_correct:
            # Repeat the special (1 card) turn until someone makes a mistake
            self._start_turn()
        else:
            self.current_turn += 1
            if self.current_turn < 5:
                self._start_turn()
            else:
                self._end_game()

        return True, "Prossimo turno avviato"
    
    def _end_game(self):
        """End the game and calculate final standings."""
        self.phase = GamePhase.GAME_OVER
        self._clear_turn_timer()
        
        # Sort non-spectator players by lives (descending)
        all_players = [
            p for p in self.players.values()
            if not p.is_spectator and not p.join_next_turn
        ]
        all_players.sort(key=lambda p: p.lives, reverse=True)
        
        self.game_results = []
        for i, player in enumerate(all_players):
            self.game_results.append({
                'position': i + 1,
                'player_id': player.player_id,
                'name': f"🤖 {player.name}" if player.is_bot else player.name,
                'lives': player.lives
            })
        
        if self.game_results:
            winner = self.game_results[0]
            self._add_message('system', f"Partita finita! Vince {winner['name']} con {winner['lives']} vite!")
    
    def reset_game(self):
        """Reset game state so the same room can start a new game."""
        if self.phase != GamePhase.GAME_OVER:
            return False
        
        # Reset game-level state
        self.phase = GamePhase.WAITING
        self.current_turn = 0
        self.current_trick = 0
        self.current_player_index = 0
        self.first_better_index = 0
        self.trick_starter_index = 0
        self.bets_made = []
        self.cards_on_table = []
        self.last_trick_cards = []
        self.pending_jolly_player = None
        self.trick_winner_id = None
        self.is_last_trick_of_turn = False
        self.turn_results = []
        self.game_results = []
        self.last_turn_all_correct = False
        self.messages = []
        self._clear_turn_timer()

        # Remove bot players (they were abandoned and should not persist)
        bot_ids = [pid for pid, p in self.players.items() if p.is_bot]
        for pid in bot_ids:
            del self.players[pid]
            if pid in self.player_order:
                self.player_order.remove(pid)
        
        # Reset each player that is still present
        for player in self.players.values():
            player.lives = Player.INITIAL_LIVES
            player.hand = []
            player.bet = None
            player.tricks_won = 0
            player.total_tricks_won = 0
            player.total_bets_correct = 0
            player.total_bets_wrong = 0
            player.total_lives_lost = 0
            player.is_spectator = False
            player.join_next_turn = False
            player.ready_for_next_turn = False
        
        self._add_message('system', 'Nuova partita! In attesa di giocatori...')
        return True
    
    # ==================== Special Turn (1 card) ====================
    
    def is_special_turn(self) -> bool:
        """Check if this is the special turn (1 card)."""
        if self.current_turn < 0 or self.current_turn >= len(self.CARDS_PER_TURN):
            return False
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
    
    def tick(self):
        """Run periodic checks (offline players, turn timeouts, bot auto-play). Call once before broadcasting, NOT per-player."""
        self.check_and_handle_offline_player()
        self.check_and_handle_turn_timeout()
        self._handle_bot_auto_play()

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
            # Special turn: players see others' cards but not their own
            hide_own_hand = is_special and self.phase in (GamePhase.BETTING, GamePhase.PLAYING, GamePhase.WAITING_JOLLY)
            # Always include my own hand so the client can render hidden, clickable cards
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
        
        now = time.time()
        seconds_left = None
        if self.turn_timer_deadline:
            seconds_left = max(0, int(self.turn_timer_deadline - now))

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
            'trick_winner': trick_winner_info,
            'turn_timer': {
                'active': self.turn_timer_deadline is not None and self.turn_timer_player_id is not None,
                'player_id': self.turn_timer_player_id,
                'type': self.turn_timer_type,
                'deadline': self.turn_timer_deadline,
                'seconds_left': seconds_left
            }
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
