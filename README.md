# Presina - Gioco di Carte Online

Un gioco di carte napoletano multiplayer online, costruito con Flask + Socket.IO.

## 🎮 Caratteristiche

- **2-8 giocatori** in tempo reale
- **5 turni** con 5, 4, 3, 2, 1 carte
- **Turno speciale**: nel turno con 1 carta, vedi le carte degli altri ma non la tua
- **Jolly** (Asso di Ori): scegli se "prende" (più forte) o "lascia" (più debole)
- **Chat** in stanza
- **Riconnessione automatica** dopo disconnect
- **Spettatori** che possono entrare durante la partita

## 🚀 Avvio Rapido

### Requisiti

- Python 3.9+
- pip

### Installazione

```bash
# Installa dipendenze
pip install -r requirements.txt

# Avvia il server
python app.py
```

Apri http://localhost:5000 nel browser.

### Sviluppo

```bash
# Esegui i test
pytest tests/ -v

# Con coverage
pytest tests/ --cov=game --cov=rooms --cov-report=html
```

## 📁 Struttura Progetto

```
presina/
├── app.py                  # Entry point Flask + Socket.IO
├── config.py               # Configurazioni
├── requirements.txt        # Dipendenze Python
├── Procfile               # Deploy (Heroku/Render)
├── render.yaml            # Config Render
│
├── game/                  # Logica di gioco
│   ├── card.py            # Classe Card
│   ├── player.py          # Classe Player
│   ├── deck.py            # Mazzo di carte
│   └── presina_game.py    # Logica partita
│
├── rooms/                 # Gestione stanze
│   └── room_manager.py    # RoomManager
│
├── sockets/               # Eventi Socket.IO
│   ├── lobby_events.py    # Eventi lobby
│   ├── game_events.py     # Eventi gioco
│   └── chat_events.py     # Eventi chat
│
├── templates/
│   └── index.html         # SPA frontend
│
├── static/
│   ├── css/style.css      # Stili
│   └── js/                # JavaScript
│       ├── main.js        # App principale
│       ├── socket_client.js
│       ├── game_ui.js
│       └── chat.js
│
├── carte_napoletane/      # Immagini carte
│   ├── Bastoni/
│   ├── Spade/
│   ├── Coppe/
│   └── Ori/
│
└── tests/                 # Unit tests
    ├── test_card.py
    ├── test_game_logic.py
    └── test_rooms.py
```

## 🎯 Regole del Gioco

### Obiettivo
Indovinare quante mani vincerai in ogni turno. Chi indovina non perde vite, chi sbaglia perde 1 vita.

### Setup
- 2-8 giocatori, ognuno parte con 5 vite
- Si giocano 5 turni con 5, 4, 3, 2, 1 carte
- Mazzo: 40 carte napoletane (Bastoni, Spade, Coppe, Ori)

### Forza delle Carte
- **Semi**: Bastoni < Spade < Coppe < Ori
- **Valori**: Asso < 2 < ... < 7 < Fante < Cavallo < Re

### Puntata
- L'ultimo giocatore a puntare NON può scegliere il numero che renderebbe la somma totale uguale alle carte in gioco

### Il Jolly (Asso di Ori)
- **Prende**: diventa la carta più forte (sopra il Re di Ori)
- **Lascia**: diventa la carta più debole (sotto l'Asso di Bastoni)

### Vittoria
Dopo 5 turni, vince chi ha più vite!

## 🌐 Deploy

### Render

1. Collega il repository GitHub a Render
2. Il file `render.yaml` configura tutto automaticamente

### Heroku

```bash
heroku create presina-game
git push heroku main
```

### Variabili d'Ambiente

- `SECRET_KEY`: Chiave segreta Flask (generata automaticamente in produzione)
- `FLASK_ENV`: `production` o `development`
- `CORS_ORIGINS`: Origini CORS permesse (default: `*`)

## 📝 Licenza

MIT License
