"""
Deck class for Presina game.
40 Neapolitan cards.
"""
import random
from typing import List
from .card import Card


class Deck:
    def __init__(self):
        """Create a new shuffled deck of 40 Neapolitan cards."""
        self.cards: List[Card] = []
        self.reset()
    
    def reset(self):
        """Reset and shuffle the deck."""
        self.cards = []
        for suit in Card.SUITS:
            for value in range(1, 11):
                self.cards.append(Card(suit, value))
        self.shuffle()
    
    def shuffle(self):
        """Shuffle the deck."""
        random.shuffle(self.cards)
    
    def draw(self, count: int = 1) -> List[Card]:
        """
        Draw cards from the deck.
        
        Args:
            count: Number of cards to draw
            
        Returns:
            List of drawn cards
            
        Raises:
            ValueError: If not enough cards in deck
        """
        if count > len(self.cards):
            raise ValueError(f"Not enough cards in deck. Requested: {count}, Available: {len(self.cards)}")
        
        drawn = self.cards[:count]
        self.cards = self.cards[count:]
        return drawn
    
    def __len__(self):
        return len(self.cards)
    
    def __repr__(self):
        return f"Deck({len(self.cards)} cards)"
