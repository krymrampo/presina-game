"""
Modulo per la gestione delle carte da briscola nel gioco Presina.
"""

class Card:
    """Rappresenta una carta da briscola."""
    
    SUITS = ['Bastoni', 'Spade', 'Coppe', 'Denari']
    RANKS = ['Asso', '2', '3', '4', '5', '6', '7', 'Fante', 'Cavallo', 'Re']
    
    def __init__(self, suit, rank):
        """
        Inizializza una carta.
        
        Args:
            suit: Il seme della carta (0=Bastoni, 1=Spade, 2=Coppe, 3=Denari)
            rank: Il valore della carta (0=Asso, 1=2, ..., 9=Re)
        """
        self.suit = suit
        self.rank = rank
        self.is_joker = (suit == 3 and rank == 0)  # Asso di Denari
        self.joker_mode = None  # 'prende' o 'lascia' (solo per jolly)
    
    def get_value(self):
        """
        Calcola il valore assoluto della carta per confronti.
        
        Returns:
            int: Valore della carta (0 = Asso Bastoni, 39 = Re Denari)
        """
        if self.is_joker:
            if self.joker_mode == 'prende':
                return 40  # Più del Re di Denari
            elif self.joker_mode == 'lascia':
                return -1  # Meno dell'Asso di Bastoni
            else:
                # Non ancora dichiarato
                return self.suit * 10 + self.rank
        
        return self.suit * 10 + self.rank
    
    def set_joker_mode(self, mode):
        """
        Imposta la modalità del jolly.
        
        Args:
            mode: 'prende' o 'lascia'
        """
        if self.is_joker:
            self.joker_mode = mode
    
    def __str__(self):
        """Rappresentazione in stringa della carta."""
        name = f"{self.RANKS[self.rank]} di {self.SUITS[self.suit]}"
        if self.is_joker and self.joker_mode:
            name += f" (Jolly: {self.joker_mode})"
        return name
    
    def __repr__(self):
        return self.__str__()
    
    def __lt__(self, other):
        """Confronto per ordinamento."""
        return self.get_value() < other.get_value()
    
    def __eq__(self, other):
        """Uguaglianza tra carte."""
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank


def create_deck():
    """
    Crea un mazzo completo di carte da briscola.
    
    Returns:
        list: Lista di 40 carte
    """
    deck = []
    for suit in range(4):
        for rank in range(10):
            deck.append(Card(suit, rank))
    return deck
