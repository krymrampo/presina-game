"""
Entry point per il gioco Presina.
"""

from game import PresinaGame


def main():
    """Funzione principale per avviare il gioco."""
    print("="*60)
    print(" "*20 + "PRESINA")
    print("="*60)
    print("\nIl gioco della puntata perfetta!")
    print("\nRegole:")
    print("- 5 turni con 5, 4, 3, 2 e 1 carte")
    print("- Ogni giocatore inizia con 5 vite")
    print("- Punta quante mani prenderai nel turno")
    print("- Se indovini, mantieni le tue vite")
    print("- Se sbagli, perdi 1 vita")
    print("- L'ultimo a puntare non può far tornare i conti!")
    print("- Nel turno da 1 carta, vedi le carte altrui ma non la tua")
    print("- Asso di Denari è jolly: può 'prendere' o 'lasciare'")
    print("\n")
    
    # Chiedi il numero di giocatori
    while True:
        try:
            num_players = int(input("Quanti giocatori? (2-8): "))
            if 2 <= num_players <= 8:
                break
            else:
                print("Il numero di giocatori deve essere tra 2 e 8")
        except ValueError:
            print("Inserisci un numero valido")
    
    # Chiedi i nomi dei giocatori
    player_names = []
    for i in range(num_players):
        while True:
            name = input(f"Nome del giocatore {i+1}: ").strip()
            if name and name not in player_names:
                player_names.append(name)
                break
            elif name in player_names:
                print("Nome già usato, scegline un altro")
            else:
                print("Il nome non può essere vuoto")
    
    # Crea e avvia il gioco
    game = PresinaGame(player_names)
    game.play_game()
    
    # Chiedi se giocare ancora
    print("\n")
    while True:
        again = input("Vuoi giocare di nuovo? (s/n): ").lower()
        if again in ['s', 'si', 'sì', 'y', 'yes']:
            print("\n\n")
            main()
            break
        elif again in ['n', 'no']:
            print("\nGrazie per aver giocato a Presina! Arrivederci!")
            break
        else:
            print("Rispondi con 's' o 'n'")


if __name__ == "__main__":
    main()
