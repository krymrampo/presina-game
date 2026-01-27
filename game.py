"""
Modulo principale per la logica del gioco Presina.
"""

import random
from card import create_deck, Card
from player import Player


class PresinaGame:
    """Gestisce la logica del gioco Presina."""
    
    CARDS_PER_ROUND = [5, 4, 3, 2, 1]
    
    def __init__(self, player_names):
        """
        Inizializza una partita di Presina.
        
        Args:
            player_names: Lista di nomi dei giocatori (2-8)
        """
        if len(player_names) < 2 or len(player_names) > 8:
            raise ValueError("Il numero di giocatori deve essere tra 2 e 8")
        
        self.players = [Player(name) for name in player_names]
        self.current_round = 0
        self.dealer_index = 0  # Indice del primo giocatore a puntare/giocare
        self.deck = []
    
    def play_game(self):
        """Esegue una partita completa di Presina."""
        print("\n" + "="*60)
        print("BENVENUTI AL GIOCO PRESINA!")
        print("="*60)
        print(f"\nGiocatori: {', '.join([p.name for p in self.players])}")
        print("Ogni giocatore inizia con 5 vite.")
        print("\n")
        
        for round_num in range(5):
            self.current_round = round_num
            cards_this_round = self.CARDS_PER_ROUND[round_num]
            
            print("\n" + "="*60)
            print(f"TURNO {round_num + 1}/5 - {cards_this_round} CARTE")
            print("="*60)
            
            self.play_round(cards_this_round)
            self.show_standings()
            
            # Ruota il dealer per il prossimo turno
            self.dealer_index = (self.dealer_index + 1) % len(self.players)
            
            if round_num < 4:
                input("\nPremi INVIO per continuare al prossimo turno...")
        
        self.declare_winner()
    
    def play_round(self, num_cards):
        """
        Gioca un turno completo.
        
        Args:
            num_cards: Numero di carte da distribuire
        """
        # Reset dei giocatori per il turno
        for player in self.players:
            player.reset_for_round()
        
        # Distribuisci le carte
        self.deal_cards(num_cards)
        
        # Mostra le carte (regola speciale per 1 carta)
        if num_cards == 1:
            self.show_cards_special_round()
        else:
            self.show_all_hands()
        
        # Fase di puntata
        self.betting_phase(num_cards)
        
        # Gioca tutte le mani
        first_player_index = self.dealer_index
        for trick_num in range(num_cards):
            print(f"\n--- Mano {trick_num + 1}/{num_cards} ---")
            winner_index = self.play_trick(first_player_index, num_cards)
            first_player_index = winner_index
        
        # Verifica le puntate e assegna penalità
        self.check_bets()
    
    def deal_cards(self, num_cards):
        """
        Distribuisce le carte ai giocatori.
        
        Args:
            num_cards: Numero di carte da distribuire a ciascun giocatore
        """
        self.deck = create_deck()
        random.shuffle(self.deck)
        
        for _ in range(num_cards):
            for player in self.players:
                if self.deck:
                    player.add_card(self.deck.pop())
    
    def show_all_hands(self):
        """Mostra le carte di tutti i giocatori."""
        print("\n--- CARTE DISTRIBUITE ---")
        for player in self.players:
            sorted_hand = sorted(player.hand, key=lambda c: c.get_value())
            print(f"{player.name}: {', '.join([str(c) for c in sorted_hand])}")
    
    def show_cards_special_round(self):
        """Mostra le carte nel turno da 1 carta (ogni giocatore vede le altre ma non la sua)."""
        print("\n--- TURNO SPECIALE: 1 CARTA ---")
        print("Ogni giocatore vede le carte degli altri ma non la propria!\n")
        
        for i, player in enumerate(self.players):
            print(f"\n{player.name}, ecco le carte degli altri giocatori:")
            for j, other_player in enumerate(self.players):
                if i != j:
                    print(f"  {other_player.name}: {other_player.hand[0]}")
            print(f"  La TUA carta: ???")
    
    def betting_phase(self, num_cards):
        """
        Gestisce la fase di puntata.
        
        Args:
            num_cards: Numero di carte nel turno
        """
        print("\n--- FASE DI PUNTATA ---")
        total_bets = 0
        
        for i in range(len(self.players)):
            player_index = (self.dealer_index + i) % len(self.players)
            player = self.players[player_index]
            
            is_last = (i == len(self.players) - 1)
            
            if is_last:
                forbidden = num_cards - total_bets
                print(f"\n{player.name}, è il tuo turno di puntare.")
                print(f"Puntate finora: {total_bets} su {num_cards} carte totali")
                print(f"NON puoi puntare {forbidden} (regola ultimo giocatore)")
            else:
                print(f"\n{player.name}, è il tuo turno di puntare.")
            
            while True:
                try:
                    bet = int(input(f"Quante mani pensi di prendere? (0-{num_cards}): "))
                    if bet < 0 or bet > num_cards:
                        print(f"Devi puntare un numero tra 0 e {num_cards}")
                        continue
                    if is_last and bet == forbidden:
                        print(f"Non puoi puntare {forbidden}! Scegli un altro numero.")
                        continue
                    break
                except ValueError:
                    print("Inserisci un numero valido")
            
            player.make_bet(bet)
            total_bets += bet
            print(f"{player.name} punta {bet} mano/i")
        
        print(f"\nTotale puntate: {total_bets}, Carte in gioco: {num_cards}")
    
    def play_trick(self, first_player_index, num_cards):
        """
        Gioca una singola mano.
        
        Args:
            first_player_index: Indice del giocatore che inizia
            num_cards: Numero di carte nel turno (per gestire il turno speciale da 1 carta)
        
        Returns:
            int: Indice del giocatore che ha vinto la mano
        """
        cards_played = []
        
        for i in range(len(self.players)):
            player_index = (first_player_index + i) % len(self.players)
            player = self.players[player_index]
            
            print(f"\n{player.name}, è il tuo turno.")
            
            # Nel turno da 1 carta, mostra solo le carte giocate finora
            if num_cards == 1:
                if cards_played:
                    print("Carte già giocate:")
                    for p, c in cards_played:
                        print(f"  {p.name}: {c}")
                print(f"La tua carta: ???")
                input("Premi INVIO per giocare la tua carta...")
                card_to_play = player.hand[0]
            else:
                # Turno normale: mostra le carte
                print(f"Le tue carte: {', '.join([f'[{idx}] {c}' for idx, c in enumerate(player.hand)])}")
                if cards_played:
                    print("Carte già giocate:")
                    for p, c in cards_played:
                        print(f"  {p.name}: {c}")
                
                while True:
                    try:
                        choice = int(input(f"Quale carta vuoi giocare? (0-{len(player.hand)-1}): "))
                        if 0 <= choice < len(player.hand):
                            card_to_play = player.hand[choice]
                            break
                        else:
                            print(f"Scegli un numero tra 0 e {len(player.hand)-1}")
                    except ValueError:
                        print("Inserisci un numero valido")
            
            # Gestione jolly (Asso di Denari)
            if card_to_play.is_joker:
                print(f"\n{player.name} ha giocato l'Asso di Denari (JOLLY)!")
                while True:
                    mode = input("Vuoi che 'prende' (più forte) o 'lascia' (più debole)? ").lower()
                    if mode in ['prende', 'lascia']:
                        card_to_play.set_joker_mode(mode)
                        break
                    else:
                        print("Scrivi 'prende' o 'lascia'")
            
            player.remove_card(card_to_play)
            cards_played.append((player, card_to_play))
            print(f"{player.name} gioca: {card_to_play}")
        
        # Determina il vincitore
        winner = max(cards_played, key=lambda x: x[1].get_value())
        winner_player = winner[0]
        winner_card = winner[1]
        
        winner_player.win_trick()
        
        print(f"\n*** {winner_player.name} vince la mano con {winner_card}! ***")
        
        return self.players.index(winner_player)
    
    def check_bets(self):
        """Verifica le puntate e assegna penalità."""
        print("\n--- RISULTATI DEL TURNO ---")
        
        for player in self.players:
            correct = player.check_bet()
            print(f"{player.name}: Puntato {player.bet}, Preso {player.tricks_won}", end="")
            
            if correct:
                print(" ✓ INDOVINATO!")
            else:
                print(" ✗ SBAGLIATO - Perdi 1 vita")
                player.lose_life()
    
    def show_standings(self):
        """Mostra la classifica attuale."""
        print("\n--- CLASSIFICA ---")
        sorted_players = sorted(self.players, key=lambda p: p.lives, reverse=True)
        for i, player in enumerate(sorted_players, 1):
            print(f"{i}. {player}")
    
    def declare_winner(self):
        """Dichiara il vincitore finale."""
        print("\n" + "="*60)
        print("FINE PARTITA!")
        print("="*60)
        
        self.show_standings()
        
        max_lives = max(p.lives for p in self.players)
        winners = [p for p in self.players if p.lives == max_lives]
        
        print("\n" + "="*60)
        if len(winners) == 1:
            print(f"🏆 VINCITORE: {winners[0].name} con {max_lives} vite! 🏆")
        else:
            print(f"🏆 PAREGGIO tra: {', '.join([w.name for w in winners])} con {max_lives} vite! 🏆")
        print("="*60 + "\n")
