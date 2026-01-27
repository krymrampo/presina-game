# Presina - Gioco di Carte

Implementazione del gioco di carte Presina in Python.

## Regole del Gioco

### Obiettivo
Sopravvivere con il maggior numero di vite possibile attraverso 5 turni di gioco.

### Setup
- **Giocatori**: 2-8 giocatori
- **Mazzo**: Carte da briscola (40 carte)
- **Vite iniziali**: Ogni giocatore inizia con 5 vite

### Ordine delle Carte
Le carte sono ordinate dal valore più basso al più alto:
- **Semi**: Bastoni < Spade < Coppe < Denari
- **Valori**: Asso < 2 < 3 < 4 < 5 < 6 < 7 < Fante < Cavallo < Re
- **Carta più bassa**: Asso di Bastoni
- **Carta più alta**: Re di Denari
- **Jolly**: Asso di Denari (vedi sotto)

### Turni
Il gioco si svolge in 5 turni con un numero decrescente di carte:
1. **Turno 1**: 5 carte
2. **Turno 2**: 4 carte
3. **Turno 3**: 3 carte
4. **Turno 4**: 2 carte
5. **Turno 5**: 1 carta (regola speciale: tutti vedono le carte altrui ma non la propria)

### Fase di Puntata
- All'inizio di ogni turno, ogni giocatore punta quante mani (trick) riuscirà a vincere
- L'ordine di puntata ruota ad ogni turno
- **Regola importante**: L'ultimo giocatore a puntare NON può dire un numero che, sommato a tutti gli altri, sia uguale al numero totale di carte del turno

### Fase di Gioco
- Il primo giocatore a puntare gioca la prima carta della prima mano
- Gli altri giocatori seguono in ordine
- Chi gioca la carta più alta vince la mano
- Chi vince una mano inizia la mano successiva

### Asso di Denari (Jolly)
Quando un giocatore gioca l'Asso di Denari, deve dichiarare:
- **"Prende"**: La carta vale più del Re di Denari (diventa la più forte)
- **"Lascia"**: La carta vale meno dell'Asso di Bastoni (diventa la più debole)

### Fine Turno
- Se un giocatore indovina esattamente quante mani ha preso: mantiene le sue vite
- Se un giocatore sbaglia: perde 1 vita (indipendentemente da quanto ha sbagliato)

### Vincitore
Dopo 5 turni, vince il giocatore (o i giocatori) con più vite rimaste.

## Come Giocare

### Requisiti
- Python 3.6 o superiore

### Avvio del Gioco
```bash
python main.py
```

### Durante il Gioco
1. Inserisci il numero di giocatori e i loro nomi
2. Guarda le carte distribuite
3. Fai la tua puntata quando è il tuo turno
4. Gioca le tue carte quando è il tuo turno
5. Se giochi l'Asso di Denari, scegli se "prende" o "lascia"

## Struttura del Codice

- `card.py`: Gestione delle carte e del mazzo
- `player.py`: Gestione dei giocatori
- `game.py`: Logica principale del gioco
- `main.py`: Entry point e interfaccia utente

## Esempio di Partita

```
=============================================================
                      PRESINA
=============================================================

Il gioco della puntata perfetta!

Quanti giocatori? (2-8): 3
Nome del giocatore 1: Alice
Nome del giocatore 2: Bob
Nome del giocatore 3: Charlie

============================================================
TURNO 1/5 - 5 CARTE
============================================================

--- CARTE DISTRIBUITE ---
Alice: Asso di Bastoni, 3 di Spade, Fante di Coppe, 6 di Denari, Re di Denari
Bob: 2 di Bastoni, 5 di Spade, Cavallo di Coppe, 4 di Denari, 7 di Denari
Charlie: Asso di Spade, 6 di Spade, 3 di Coppe, Asso di Denari, Fante di Denari

--- FASE DI PUNTATA ---
Alice, è il tuo turno di puntare.
Quante mani pensi di prendere? (0-5): 2
...
```

## Note Tecniche

Il gioco è implementato con:
- Programmazione orientata agli oggetti
- Interfaccia testuale (CLI)
- Gestione completa delle regole incluse le eccezioni speciali
