// Connessione Socket.IO
const socket = io();

// Stato del gioco
let gameState = {
    playerId: null,
    playerName: '',
    roomId: '',
    roomName: '',
    isAdmin: false,
    pendingCardIndex: null
};

// ============================================
// FUNZIONI UI - Navigazione
// ============================================

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId + '-screen').classList.add('active');
}

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

// ============================================
// FUNZIONI LOBBY
// ============================================

function enterLobby() {
    const playerName = document.getElementById('player-name').value.trim();
    if (!playerName) {
        showNotification('Inserisci il tuo nome!', true);
        return;
    }
    gameState.playerName = playerName;
    showScreen('lobby');
    
    // Richiedi lista stanze
    socket.emit('get_rooms');
}

function createRoom() {
    const roomName = document.getElementById('room-name').value.trim();
    if (!roomName) {
        showNotification('Inserisci un nome per la stanza!', true);
        return;
    }
    
    document.getElementById('create-room-modal').style.display = 'none';
    
    socket.emit('create_room', {
        playerName: gameState.playerName,
        roomName: roomName
    });
}

function joinRoom(roomId) {
    socket.emit('join_room', {
        roomId: roomId,
        playerName: gameState.playerName
    });
}

function leaveRoom() {
    socket.emit('leave_room', {
        roomId: gameState.roomId
    });
    
    gameState.roomId = '';
    gameState.roomName = '';
    gameState.isAdmin = false;
    
    showScreen('lobby');
    socket.emit('get_rooms');
}

function startGame() {
    console.log('Avvio partita per stanza:', gameState.roomId);
    socket.emit('start_game', {
        roomId: gameState.roomId
    });
}

function filterRooms() {
    const searchText = document.getElementById('search-room').value.toLowerCase();
    const roomCards = document.querySelectorAll('.room-card');
    
    roomCards.forEach(card => {
        const roomName = card.dataset.roomName.toLowerCase();
        if (roomName.includes(searchText)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}

function renderRoomsList(rooms) {
    const roomsList = document.getElementById('rooms-list');
    
    if (!rooms || rooms.length === 0) {
        roomsList.innerHTML = '<p class="no-rooms">Nessuna stanza disponibile. Creane una!</p>';
        return;
    }
    
    roomsList.innerHTML = '';
    
    rooms.forEach(room => {
        const roomCard = document.createElement('div');
        roomCard.className = 'room-card';
        roomCard.dataset.roomName = room.name;
        
        const statusClass = room.started ? 'in-game' : 'waiting';
        const statusText = room.started ? '🎮 In Gioco' : '⏳ In Attesa';
        
        roomCard.innerHTML = `
            <div class="room-info-card">
                <h3>${room.name}</h3>
                <p>👥 ${room.playerCount}/8 giocatori</p>
                <span class="room-status ${statusClass}">${statusText}</span>
            </div>
            <button class="btn btn-primary" ${room.started || room.playerCount >= 8 ? 'disabled' : ''} 
                    onclick="joinRoom('${room.id}')">
                ${room.started ? 'Partita in corso' : 'Unisciti'}
            </button>
        `;
        
        roomsList.appendChild(roomCard);
    });
}

// ============================================
// FUNZIONI GIOCO
// ============================================

function makeBet(bet) {
    socket.emit('make_bet', {
        roomId: gameState.roomId,
        bet: bet
    });
    
    document.querySelectorAll('.bet-button').forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.5';
    });
}

function playCard(cardIndex) {
    const hand = document.querySelectorAll('#player-hand .card:not(.played)');
    const card = hand[cardIndex];
    
    if (!card || card.classList.contains('disabled') || card.classList.contains('played')) {
        return;
    }
    
    if (card.dataset.isJoker === 'true') {
        gameState.pendingCardIndex = cardIndex;
        document.getElementById('joker-modal').style.display = 'flex';
    } else {
        socket.emit('play_card', {
            roomId: gameState.roomId,
            cardIndex: cardIndex
        });
        
        card.classList.add('played');
        card.style.display = 'none';
        
        document.querySelectorAll('#player-hand .card').forEach(c => {
            c.classList.add('disabled');
        });
    }
}

function selectJokerMode(mode) {
    document.getElementById('joker-modal').style.display = 'none';
    
    socket.emit('play_card', {
        roomId: gameState.roomId,
        cardIndex: gameState.pendingCardIndex,
        jokerMode: mode
    });
    
    const hand = document.querySelectorAll('#player-hand .card:not(.played)');
    if (hand[gameState.pendingCardIndex]) {
        hand[gameState.pendingCardIndex].classList.add('played');
        hand[gameState.pendingCardIndex].style.display = 'none';
    }
    
    gameState.pendingCardIndex = null;
    
    document.querySelectorAll('#player-hand .card').forEach(c => {
        c.classList.add('disabled');
    });
}

// ============================================
// SOCKET EVENT LISTENERS
// ============================================

// Lista stanze
socket.on('rooms_list', (rooms) => {
    renderRoomsList(rooms);
});

// Stanza creata
socket.on('room_created', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = true;
    
    document.getElementById('room-title').textContent = '🏠 ' + data.roomName;
    document.getElementById('admin-controls').style.display = 'block';
    document.getElementById('waiting-message').style.display = 'none';
    
    showScreen('room');
    showNotification('Stanza creata!');
});

// Unito alla stanza
socket.on('room_joined', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = false;
    
    document.getElementById('room-title').textContent = '🏠 ' + data.roomName;
    document.getElementById('admin-controls').style.display = 'none';
    document.getElementById('waiting-message').style.display = 'block';
    
    showScreen('room');
    showNotification('Ti sei unito alla stanza!');
});

// Stato stanza aggiornato
socket.on('room_state', (state) => {
    updateRoomState(state);
});

// Partita iniziata
socket.on('game_started', (data) => {
    showScreen('game');
    showNotification('La partita è iniziata!');
});

// Turno iniziato
socket.on('round_started', (data) => {
    document.getElementById('current-round').textContent = data.round;
    document.getElementById('cards-this-round').textContent = data.cardsThisRound;
    document.getElementById('total-tricks').textContent = data.cardsThisRound;
    
    addGameMessage(`Turno ${data.round} iniziato - ${data.cardsThisRound} carte`, 'info');
});

// Mano del giocatore
socket.on('player_hand', (data) => {
    displayPlayerHand(data);
});

// Richiesta puntata
socket.on('request_bet', (data) => {
    displayBettingArea(data);
});

// Puntata effettuata
socket.on('player_bet', (data) => {
    addGameMessage(`${data.playerName} ha puntato ${data.bet}`, 'info');
});

// Puntate complete
socket.on('betting_complete', (data) => {
    document.getElementById('betting-area').style.display = 'none';
    addGameMessage(`Puntate completate: ${data.totalBets} su ${data.cardsThisRound}`, 'info');
});

// Mano iniziata
socket.on('trick_started', (data) => {
    document.getElementById('trick-number').textContent = data.trickNumber;
    document.getElementById('trick-area').style.display = 'block';
    document.getElementById('cards-played').innerHTML = '';
    
    document.getElementById('phase-title').textContent = 'Fase di Gioco';
    document.getElementById('phase-description').textContent = `Mano ${data.trickNumber} di ${data.totalTricks}`;
});

// Richiesta carta
socket.on('request_card', (data) => {
    document.querySelectorAll('#player-hand .card:not(.played)').forEach(c => {
        c.classList.remove('disabled');
    });
    
    addGameMessage(`${data.playerName}, gioca una carta!`, 'info');
});

// Carta giocata
socket.on('card_played', (data) => {
    addGameMessage(`${data.playerName} ha giocato ${data.card.rankName} di ${data.card.suitName}`, 'info');
    
    const cardsPlayedDiv = document.getElementById('cards-played');
    const playedCardDiv = document.createElement('div');
    playedCardDiv.className = 'played-card';
    playedCardDiv.innerHTML = `
        <div class="player-name">${data.playerName}</div>
        ${createCardHTML(data.card, -1, false)}
    `;
    cardsPlayedDiv.appendChild(playedCardDiv);
});

// Mano vinta
socket.on('trick_won', (data) => {
    addGameMessage(`${data.winnerName} vince la mano con ${data.winningCard.rankName} di ${data.winningCard.suitName}!`, 'success');
    
    setTimeout(() => {
        document.getElementById('cards-played').innerHTML = '';
    }, 2000);
});

// Turno terminato
socket.on('round_ended', (data) => {
    document.getElementById('trick-area').style.display = 'none';
    
    let message = 'Risultati del turno:\n\n';
    data.results.forEach(r => {
        const status = r.correct ? '✅' : '❌';
        message += `${status} ${r.playerName}: ${r.bet}/${r.tricksWon} (${r.lives} ❤️)\n`;
    });
    
    addGameMessage(message, 'info');
});

// Partita terminata
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
        if (confirm('Partita terminata! Vuoi tornare alla lobby?')) {
            showScreen('lobby');
            socket.emit('get_rooms');
        }
    }, 3000);
});

// Errore
socket.on('error', (data) => {
    showNotification(data.message, true);
});

// Giocatore disconnesso
socket.on('player_disconnected', (data) => {
    showNotification(data.message, true);
});

// Stato gioco
socket.on('game_state', (state) => {
    updatePlayersStatus(state);
});

// ============================================
// FUNZIONI DI RENDERING
// ============================================

function updateRoomState(state) {
    const playersList = document.getElementById('players-list');
    playersList.innerHTML = '';
    
    state.players.forEach(player => {
        const li = document.createElement('li');
        const isMe = player.socketId === gameState.playerId;
        const adminBadge = player.isAdmin ? ' 👑' : '';
        li.textContent = `${player.name}${adminBadge}${isMe ? ' (Tu)' : ''}`;
        li.className = isMe ? 'current-player' : '';
        playersList.appendChild(li);
    });
    
    // Se la partita è iniziata, vai alla schermata gioco
    if (state.gameStarted) {
        showScreen('game');
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
        specialNote.style.display = 'block';
        handDiv.innerHTML = createCardHTML({isHidden: true}, 0, false);
        
        if (data.otherPlayersCards && data.otherPlayersCards.length > 0) {
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

// ============================================
// INIZIALIZZAZIONE
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Pulsanti Home
    document.getElementById('enter-lobby-btn').addEventListener('click', enterLobby);
    document.getElementById('show-rules-btn').addEventListener('click', () => showScreen('rules'));
    
    // Pulsanti Lobby
    document.getElementById('create-room-btn').addEventListener('click', () => {
        document.getElementById('create-room-modal').style.display = 'flex';
    });
    document.getElementById('back-home-btn').addEventListener('click', () => showScreen('home'));
    document.getElementById('search-room').addEventListener('input', filterRooms);
    
    // Modale Crea Stanza
    document.getElementById('confirm-create-btn').addEventListener('click', createRoom);
    document.getElementById('cancel-create-btn').addEventListener('click', () => {
        document.getElementById('create-room-modal').style.display = 'none';
    });
    
    // Pulsanti Stanza
    document.getElementById('start-game-btn').addEventListener('click', startGame);
    document.getElementById('leave-room-btn').addEventListener('click', leaveRoom);
    
    // Pulsanti Regole
    document.getElementById('back-from-rules-btn').addEventListener('click', () => showScreen('home'));
    
    // Pulsanti Jolly
    document.getElementById('joker-prende-btn').addEventListener('click', () => selectJokerMode('prende'));
    document.getElementById('joker-lascia-btn').addEventListener('click', () => selectJokerMode('lascia'));
    
    // Mostra schermata home
    showScreen('home');
});
