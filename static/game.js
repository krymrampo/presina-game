// Connessione Socket.IO
const socket = io();

// Stato del gioco
let gameState = {
    playerId: null,
    playerName: '',
    roomCode: '',
    currentScreen: 'home',
    pendingCardIndex: null
};

// Funzioni UI - Navigazione
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId + '-screen').classList.add('active');
    gameState.currentScreen = screenId;
}

function showCreateGame() {
    const playerName = document.getElementById('player-name').value.trim();
    if (!playerName) {
        showNotification('Inserisci il tuo nome!', true);
        return;
    }
    gameState.playerName = playerName;
    showScreen('create');
}

function showJoinGame() {
    const playerName = document.getElementById('player-name').value.trim();
    if (!playerName) {
        showNotification('Inserisci il tuo nome!', true);
        return;
    }
    gameState.playerName = playerName;
    showScreen('join');
}

function showRules() {
    showScreen('rules');
}

function backToHome() {
    showScreen('home');
}

// Funzioni di notifica
function showNotification(message, isError = false) {
    const notif = document.getElementById('notification');
    notif.textContent = message;
    notif.className = 'notification' + (isError ? ' error' : '');
    notif.style.display = 'block';
    
    setTimeout(() => {
        notif.style.display = 'none';
    }, 3000);
}

function addGameMessage(message, type = 'info') {
    const messagesDiv = document.getElementById('game-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'game-message ' + type;
    msgDiv.textContent = message;
    messagesDiv.appendChild(msgDiv);
    
    setTimeout(() => {
        msgDiv.remove();
    }, 5000);
}

// Funzioni Socket - Crea/Unisciti
function createGame() {
    const numPlayers = parseInt(document.getElementById('num-players').value);
    socket.emit('create_game', {
        playerName: gameState.playerName,
        numPlayers: numPlayers
    });
}

function joinGame() {
    const roomCode = document.getElementById('room-code').value.trim().toUpperCase();
    if (!roomCode || roomCode.length !== 6) {
        showNotification('Inserisci un codice valido (6 caratteri)', true);
        return;
    }
    
    socket.emit('join_game', {
        roomCode: roomCode,
        playerName: gameState.playerName
    });
}

function startGame() {
    socket.emit('start_game', {
        roomCode: gameState.roomCode
    });
}

// Funzioni di gioco
function makeBet(bet) {
    socket.emit('make_bet', {
        roomCode: gameState.roomCode,
        bet: bet
    });
    
    // Disabilita i pulsanti di puntata
    document.querySelectorAll('.bet-button').forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.5';
    });
}

function playCard(cardIndex) {
    const hand = document.querySelectorAll('#player-hand .card');
    const card = hand[cardIndex];
    
    if (card.classList.contains('disabled')) {
        return;
    }
    
    // Se è un jolly, mostra il modale
    if (card.dataset.isJoker === 'true') {
        gameState.pendingCardIndex = cardIndex;
        document.getElementById('joker-modal').style.display = 'flex';
    } else {
        socket.emit('play_card', {
            roomCode: gameState.roomCode,
            cardIndex: cardIndex
        });
        
        // Disabilita tutte le carte
        document.querySelectorAll('#player-hand .card').forEach(c => {
            c.classList.add('disabled');
        });
    }
}

function selectJokerMode(mode) {
    document.getElementById('joker-modal').style.display = 'none';
    
    socket.emit('play_card', {
        roomCode: gameState.roomCode,
        cardIndex: gameState.pendingCardIndex,
        jokerMode: mode
    });
    
    gameState.pendingCardIndex = null;
    
    // Disabilita tutte le carte
    document.querySelectorAll('#player-hand .card').forEach(c => {
        c.classList.add('disabled');
    });
}

// Event Listeners Socket
socket.on('game_created', (data) => {
    gameState.roomCode = data.roomCode;
    gameState.playerId = data.playerId;
    
    document.getElementById('lobby-room-code').textContent = data.roomCode;
    showScreen('lobby');
    showNotification('Stanza creata con successo!');
});

socket.on('game_joined', (data) => {
    gameState.roomCode = data.roomCode;
    gameState.playerId = data.playerId;
    
    document.getElementById('lobby-room-code').textContent = data.roomCode;
    showScreen('lobby');
    showNotification('Ti sei unito alla stanza!');
});

socket.on('game_state', (state) => {
    updateLobby(state);
});

socket.on('game_started', (data) => {
    showScreen('game');
    showNotification(data.message);
});

socket.on('round_started', (data) => {
    document.getElementById('current-round').textContent = data.round;
    document.getElementById('cards-this-round').textContent = data.cardsThisRound;
    document.getElementById('total-tricks').textContent = data.cardsThisRound;
    
    addGameMessage(`Turno ${data.round} iniziato - ${data.cardsThisRound} carte`, 'info');
});

socket.on('player_hand', (data) => {
    displayPlayerHand(data);
});

socket.on('request_bet', (data) => {
    displayBettingArea(data);
});

socket.on('player_bet', (data) => {
    addGameMessage(`${data.playerName} ha puntato ${data.bet}`, 'info');
});

socket.on('betting_complete', (data) => {
    document.getElementById('betting-area').style.display = 'none';
    addGameMessage(`Puntate completate: ${data.totalBets} su ${data.cardsThisRound}`, 'info');
});

socket.on('trick_started', (data) => {
    document.getElementById('trick-number').textContent = data.trickNumber;
    document.getElementById('trick-area').style.display = 'block';
    document.getElementById('cards-played').innerHTML = '';
    
    document.getElementById('phase-title').textContent = 'Fase di Gioco';
    document.getElementById('phase-description').textContent = `Mano ${data.trickNumber} di ${data.totalTricks}`;
});

socket.on('request_card', (data) => {
    // Abilita le carte nella mano
    document.querySelectorAll('#player-hand .card').forEach(c => {
        c.classList.remove('disabled');
    });
    
    addGameMessage(`${data.playerName}, gioca una carta!`, 'info');
});

socket.on('card_played', (data) => {
    addGameMessage(`${data.playerName} ha giocato ${data.card.rankName} di ${data.card.suitName}`, 'info');
    
    // Aggiungi la carta all'area trick
    const cardsPlayedDiv = document.getElementById('cards-played');
    const playedCardDiv = document.createElement('div');
    playedCardDiv.className = 'played-card';
    playedCardDiv.innerHTML = `
        <div class="player-name">${data.playerName}</div>
        ${createCardHTML(data.card, -1, false)}
    `;
    cardsPlayedDiv.appendChild(playedCardDiv);
});

socket.on('trick_won', (data) => {
    addGameMessage(`${data.winnerName} vince la mano con ${data.winningCard.rankName} di ${data.winningCard.suitName}!`, 'success');
    
    setTimeout(() => {
        document.getElementById('cards-played').innerHTML = '';
    }, 2000);
});

socket.on('round_ended', (data) => {
    document.getElementById('trick-area').style.display = 'none';
    
    let message = 'Risultati del turno:\n\n';
    data.results.forEach(r => {
        const status = r.correct ? '✅' : '❌';
        message += `${status} ${r.playerName}: ${r.bet}/${r.tricksWon} (${r.lives} ❤️)\n`;
    });
    
    addGameMessage(message, 'info');
});

socket.on('game_ended', (data) => {
    let message = '🎉 FINE PARTITA! 🎉\n\n';
    
    if (data.winners.length === 1) {
        message += `🏆 Vincitore: ${data.winners[0]} con ${data.maxLives} vite!\n\n`;
    } else {
        message += `🏆 Pareggio tra: ${data.winners.join(', ')} con ${data.maxLives} vite!\n\n`;
    }
    
    message += 'Classifica finale:\n';
    data.finalStandings.forEach((p, i) => {
        message += `${i + 1}. ${p.playerName} - ${p.lives} ❤️\n`;
    });
    
    addGameMessage(message, 'success');
    
    setTimeout(() => {
        if (confirm('Partita terminata! Vuoi tornare alla home?')) {
            location.reload();
        }
    }, 5000);
});

socket.on('error', (data) => {
    showNotification(data.message, true);
});

socket.on('player_disconnected', (data) => {
    showNotification(data.message, true);
});

// Funzioni di rendering
function updateLobby(state) {
    document.getElementById('player-count').textContent = state.players.length;
    document.getElementById('max-players').textContent = state.maxPlayers;
    
    const playersList = document.getElementById('players-list');
    playersList.innerHTML = '';
    
    state.players.forEach(player => {
        const li = document.createElement('li');
        li.textContent = `${player.name} ${player.socketId === gameState.playerId ? '(Tu)' : ''}`;
        playersList.appendChild(li);
    });
    
    if (state.players.length === state.maxPlayers) {
        document.getElementById('start-game-section').style.display = 'block';
        document.getElementById('waiting-message').style.display = 'none';
    }
    
    // Aggiorna anche lo stato dei giocatori in gioco
    if (state.gameStarted) {
        updatePlayersStatus(state);
    }
}

function updatePlayersStatus(state) {
    const statusDiv = document.getElementById('players-status');
    statusDiv.innerHTML = '';
    
    state.players.forEach(player => {
        const div = document.createElement('div');
        div.className = 'player-status';
        
        if (state.waitingForPlayer === player.name) {
            div.classList.add('current');
        }
        
        let html = `<strong>${player.name}</strong><br>`;
        html += `❤️ ${player.lives} vite<br>`;
        
        if (player.bet !== null && player.bet !== undefined) {
            html += `🎯 Puntata: ${player.bet}<br>`;
        }
        
        if (state.playingPhase && player.tricksWon !== undefined) {
            html += `🏆 Prese: ${player.tricksWon}`;
        }
        
        div.innerHTML = html;
        statusDiv.appendChild(div);
    });
}

function displayPlayerHand(data) {
    const handDiv = document.getElementById('player-hand');
    handDiv.innerHTML = '';
    
    const specialNote = document.getElementById('special-round-note');
    
    if (data.specialRound && data.hideOwnCard) {
        // Turno speciale da 1 carta
        specialNote.style.display = 'block';
        
        // Mostra carta nascosta
        handDiv.innerHTML = createCardHTML({isHidden: true}, 0, false);
        
        // Mostra le carte degli altri giocatori
        if (data.otherPlayersCards.length > 0) {
            const othersDiv = document.createElement('div');
            othersDiv.innerHTML = '<h4 style="margin-top: 20px;">Carte degli altri giocatori:</h4>';
            const othersCards = document.createElement('div');
            othersCards.className = 'cards-container';
            
            data.otherPlayersCards.forEach(other => {
                const cardWrapper = document.createElement('div');
                cardWrapper.style.textAlign = 'center';
                cardWrapper.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 5px;">${other.playerName}</div>
                    ${createCardHTML(other.card, -1, false)}
                `;
                othersCards.appendChild(cardWrapper);
            });
            
            othersDiv.appendChild(othersCards);
            handDiv.parentElement.appendChild(othersDiv);
        }
    } else {
        specialNote.style.display = 'none';
        
        // Mostra le carte normali
        data.hand.forEach((card, index) => {
            handDiv.innerHTML += createCardHTML(card, index, true);
        });
    }
}

function createCardHTML(card, index, clickable) {
    if (card.isHidden) {
        return `<div class="card hidden">?</div>`;
    }
    
    const suitClass = ['bastoni', 'spade', 'coppe', 'denari'][card.suit];
    const suitSymbol = ['🌲', '⚔️', '🏆', '💰'][card.suit];
    const onclick = clickable ? `onclick="playCard(${index})"` : '';
    const jokerClass = card.isJoker ? ' joker' : '';
    
    return `
        <div class="card ${suitClass}${jokerClass}" 
             ${onclick}
             data-index="${index}"
             data-is-joker="${card.isJoker}">
            <div class="card-suit">${suitSymbol}</div>
            <div class="card-rank">${card.rankName}</div>
            ${card.isJoker ? '<div style="font-size: 0.8em;">JOLLY</div>' : ''}
        </div>
    `;
}

function displayBettingArea(data) {
    document.getElementById('betting-area').style.display = 'block';
    document.getElementById('phase-title').textContent = 'Fase di Puntata';
    document.getElementById('phase-description').textContent = `${data.playerName}, fai la tua puntata!`;
    
    const instruction = document.getElementById('bet-instruction');
    instruction.innerHTML = `Quante mani pensi di prendere? (0-${data.maxBet})<br>`;
    
    if (data.isLast) {
        instruction.innerHTML += `<span style="color: red;">⚠️ Non puoi puntare ${data.forbidden}!</span>`;
    }
    
    const buttonsDiv = document.getElementById('bet-buttons');
    buttonsDiv.innerHTML = '';
    
    for (let i = 0; i <= data.maxBet; i++) {
        const button = document.createElement('button');
        button.className = 'bet-button';
        button.textContent = i;
        button.onclick = () => makeBet(i);
        
        if (data.isLast && i === data.forbidden) {
            button.classList.add('forbidden');
            button.disabled = true;
        }
        
        buttonsDiv.appendChild(button);
    }
}

// Inizializzazione
document.addEventListener('DOMContentLoaded', () => {
    showScreen('home');
});
