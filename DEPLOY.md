# Guida al Deploy su Render

## Preparazione

1. **Crea un account su Render**: Vai su [render.com](https://render.com) e crea un account gratuito.

2. **Carica il codice su GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Presina game"
   git branch -M main
   git remote add origin <URL_DEL_TUO_REPO>
   git push -u origin main
   ```

## Deploy su Render

### Opzione 1: Deploy Automatico (consigliato)

1. Vai su [render.com](https://render.com) e fai login
2. Clicca su "New +" e seleziona "Web Service"
3. Connetti il tuo repository GitHub
4. Seleziona il repository "Presina"
5. Configura il servizio:
   - **Name**: presina-game (o il nome che preferisci)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`
6. Clicca su "Create Web Service"

### Opzione 2: Deploy tramite render.yaml

1. Vai su [render.com](https://render.com) e fai login
2. Clicca su "New +" e seleziona "Blueprint"
3. Connetti il tuo repository GitHub
4. Render rileverà automaticamente il file `render.yaml` e creerà il servizio

## Dopo il Deploy

1. Render ti fornirà un URL del tipo: `https://presina-game.onrender.com`
2. Condividi questo URL con i tuoi amici per giocare!
3. La prima richiesta potrebbe essere lenta (il servizio gratuito va in sleep dopo 15 minuti di inattività)

## Test Locale Prima del Deploy

Per testare in locale prima di fare il deploy:

```bash
# Installa le dipendenze
pip install -r requirements.txt

# Avvia il server
python app.py

# Apri il browser su http://localhost:5000
```

## Variabili d'Ambiente (opzionali)

Se vuoi personalizzare:

1. Vai su Render Dashboard → Il tuo servizio → Environment
2. Aggiungi variabili d'ambiente:
   - `SECRET_KEY`: Una chiave segreta per Flask (generata automaticamente se non impostata)
   - `PORT`: Porta del server (gestita automaticamente da Render)

## Troubleshooting

### Il sito non si carica
- Controlla i logs su Render Dashboard → Il tuo servizio → Logs
- Verifica che tutte le dipendenze siano in `requirements.txt`

### Errori WebSocket
- Assicurati che la connessione Socket.IO usi il protocollo corretto
- Render supporta automaticamente WebSocket

### Il gioco è lento
- Il piano gratuito di Render ha limitazioni
- Considera di upgradare al piano a pagamento per prestazioni migliori

## Aggiornamenti

Per aggiornare il gioco dopo modifiche:

```bash
git add .
git commit -m "Descrizione delle modifiche"
git push
```

Render farà il deploy automaticamente delle modifiche!

## Note

- Il piano gratuito di Render mette il servizio in sleep dopo 15 minuti di inattività
- La prima richiesta dopo lo sleep richiederà 30-60 secondi per riavviarsi
- Per evitare lo sleep, considera un piano a pagamento o usa un servizio di "keep alive"
