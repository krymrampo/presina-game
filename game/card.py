"""
Card class for Presina game.
Uses Neapolitan cards: 40 cards, 4 suits, values 1-10.
"""

class Card:
    # Suits in order of strength (Bastoni < Spade < Coppe < Ori)
    SUITS = ['Bastoni', 'Spade', 'Coppe', 'Ori']
    
    # Value names for display
    VALUE_NAMES = {
        1: 'Asso',
        2: '2',
        3: '3',
        4: '4',
        5: '5',
        6: '6',
        7: '7',
        8: 'Fante',
        9: 'Cavallo',
        10: 'Re'
    }
    
    def __init__(self, suit: str, value: int):
        """
        Create a card.
        
        Args:
            suit: One of 'Bastoni', 'Spade', 'Coppe', 'Ori'
            value: 1-10 (1=Asso, 8=Fante, 9=Cavallo, 10=Re)
        """
        if suit not in self.SUITS:
            raise ValueError(f"Invalid suit: {suit}")
        if value < 1 or value > 10:
            raise ValueError(f"Invalid value: {value}")
        
        self.suit = suit
        self.value = value
        self._jolly_choice = None  # 'prende' or 'lascia' for Asso di Ori
    
    @property
    def is_jolly(self) -> bool:
        """Check if this is the Jolly (Asso di Ori/Denari)."""
        return self.suit == 'Ori' and self.value == 1
    
    @property
    def jolly_choice(self):
        """Get the jolly choice if set."""
        return self._jolly_choice
    
    @jolly_choice.setter
    def jolly_choice(self, choice: str):
        """Set jolly choice: 'prende' (strongest) or 'lascia' (weakest)."""
        if not self.is_jolly:
            raise ValueError("Can only set jolly_choice on Asso di Ori")
        if choice not in ('prende', 'lascia'):
            raise ValueError("Choice must be 'prende' or 'lascia'")
        self._jolly_choice = choice
    
    def get_strength(self) -> int:
        """
        Calculate card strength for comparison.
        
        Normal cards: suit_index * 10 + value (0-39)
        Jolly with 'prende': 50 (beats everything including Re di Ori=39)
        Jolly with 'lascia': -1 (loses to everything)
        """
        if self.is_jolly and self._jolly_choice:
            if self._jolly_choice == 'prende':
                return 50
            else:  # lascia
                return -1
        
        suit_index = self.SUITS.index(self.suit)
        return suit_index * 10 + self.value
    
    def image_path(self) -> str:
        """Get the path to the card image."""
        return f"carte_napoletane/{self.suit}/{self.suit}_{self.value}.jpg"
    
    @property
    def display_name(self) -> str:
        """Get human-readable card name."""
        return f"{self.VALUE_NAMES[self.value]} di {self.suit}"
    
    def to_dict(self) -> dict:
        """Serialize card for JSON transmission."""
        return {
            'suit': self.suit,
            'value': self.value,
            'display_name': self.display_name,
            'image_path': self.image_path(),
            'is_jolly': self.is_jolly,
            'jolly_choice': self._jolly_choice,
            'strength': self.get_strength() if self._jolly_choice or not self.is_jolly else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Card':
        """Deserialize card from dict."""
        card = cls(data['suit'], data['value'])
        if data.get('jolly_choice'):
            card.jolly_choice = data['jolly_choice']
        return card
    
    def __repr__(self):
        return f"Card({self.suit}, {self.value})"
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.value == other.value
    
    def __hash__(self):
        return hash((self.suit, self.value))
