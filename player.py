"""
Modulo per la gestione dei giocatori nel gioco Presina.
"""

class Player:
    """Rappresenta un giocatore nel gioco Presina."""
    
    def __init__(self, name):
        """
        Inizializza un giocatore.
        
        Args:
            name: Nome del giocatore
        """
        self.name = name
        self.lives = 5
        self.hand = []
        self.bet = 0
        self.tricks_won = 0
        self.has_bet = False
    
    def reset_for_round(self):
        """Resetta le statistiche per un nuovo turno."""
        self.hand = []
        self.bet = 0
        self.tricks_won = 0
        self.has_bet = False
    
    def add_card(self, card):
        """Aggiunge una carta alla mano del giocatore."""
        self.hand.append(card)
    
    def remove_card(self, card):
        """Rimuove una carta dalla mano del giocatore."""
        if card in self.hand:
            self.hand.remove(card)
            return True
        return False
    
    def make_bet(self, bet):
        """Imposta la puntata del giocatore."""
        self.bet = bet
        self.has_bet = True
    
    def win_trick(self):
        """Incrementa il numero di mani vinte."""
        self.tricks_won += 1
    
    def check_bet(self):
        """
        Verifica se il giocatore ha indovinato la puntata.
        
        Returns:
            bool: True se ha indovinato, False altrimenti
        """
        return self.bet == self.tricks_won
    
    def lose_life(self):
        """Fa perdere una vita al giocatore."""
        if self.lives > 0:
            self.lives -= 1
    
    def is_alive(self):
        """Verifica se il giocatore è ancora in gioco."""
        return self.lives > 0
    
    def __str__(self):
        return f"{self.name} (Vite: {self.lives})"
    
    def __repr__(self):
        return self.__str__()
