"""
Player class for Presina game.
"""
from typing import List, Optional
from .card import Card


class Player:
    INITIAL_LIVES = 5
    
    def __init__(self, player_id: str, name: str, sid: str = None):
        """
        Create a player.
        
        Args:
            player_id: Unique identifier for the player
            name: Display name
            sid: Socket.IO session ID
        """
        self.player_id = player_id
        self.name = name
        self.sid = sid
        self.lives = self.INITIAL_LIVES
        self.hand: List[Card] = []
        self.bet: Optional[int] = None
        self.tricks_won = 0
        self.is_online = True
        self.offline_since = None  # Timestamp when marked offline
        self.is_spectator = False
        self.join_next_turn = False  # For players joining mid-game
        self.ready_for_next_turn = False
    
    def reset_for_turn(self):
        """Reset player state for a new turn."""
        self.hand = []
        self.bet = None
        self.tricks_won = 0
        self.ready_for_next_turn = False
    
    def receive_cards(self, cards: List[Card]):
        """Receive cards for the current turn."""
        self.hand = cards
    
    def play_card(self, card: Card) -> Card:
        """
        Play a card from hand.
        
        Args:
            card: The card to play
            
        Returns:
            The played card
            
        Raises:
            ValueError: If card not in hand
        """
        if card not in self.hand:
            raise ValueError(f"Card {card} not in hand")
        self.hand.remove(card)
        return card
    
    def has_card(self, suit: str, value: int) -> bool:
        """Check if player has a specific card."""
        return any(c.suit == suit and c.value == value for c in self.hand)
    
    def get_card(self, suit: str, value: int) -> Optional[Card]:
        """Get a specific card from hand."""
        for card in self.hand:
            if card.suit == suit and card.value == value:
                return card
        return None
    
    def make_bet(self, bet: int, max_cards: int):
        """
        Make a bet for the current turn.
        
        Args:
            bet: Number of tricks the player thinks they'll win
            max_cards: Maximum valid bet (number of cards in hand)
            
        Raises:
            ValueError: If bet is invalid
        """
        if bet < 0 or bet > max_cards:
            raise ValueError(f"Bet must be between 0 and {max_cards}")
        self.bet = bet
    
    def win_trick(self):
        """Record winning a trick."""
        self.tricks_won += 1
    
    def calculate_life_change(self) -> int:
        """
        Calculate life change at end of turn.
        
        Returns:
            0 if bet was correct, -1 if wrong
        """
        if self.bet == self.tricks_won:
            return 0
        return -1
    
    def apply_life_change(self):
        """Apply life change at end of turn."""
        change = self.calculate_life_change()
        self.lives += change
        return change
    
    @property
    def is_eliminated(self) -> bool:
        """Check if player is eliminated (0 lives)."""
        return self.lives <= 0
    
    def to_dict(self, include_hand: bool = False, others_hand_visible: bool = False) -> dict:
        """
        Serialize player for JSON transmission.
        
        Args:
            include_hand: Include full hand info (for the player themselves)
            others_hand_visible: Include hand info for special turn (1 card)
        """
        data = {
            'player_id': self.player_id,
            'name': self.name,
            'lives': self.lives,
            'bet': self.bet,
            'tricks_won': self.tricks_won,
            'is_online': self.is_online,
            'is_spectator': self.is_spectator,
            'join_next_turn': self.join_next_turn,
            'ready_for_next_turn': self.ready_for_next_turn,
            'cards_in_hand': len(self.hand)
        }
        
        if include_hand:
            data['hand'] = [card.to_dict() for card in self.hand]
        elif others_hand_visible and self.hand:
            # Special turn: show hand to others
            data['hand'] = [card.to_dict() for card in self.hand]
        
        return data
    
    def __repr__(self):
        return f"Player({self.player_id}, {self.name}, lives={self.lives})"
