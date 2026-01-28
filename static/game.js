// Connessione Socket.IO
const socket = io();

// Stato del gioco
let gameState = {
    playerId: null,
    playerName: '',
    roomId: '',
    roomName: '',
    isAdmin: false,
    pendingCardIndex: null,
    selectedCardElement: null,
    isMyTurn: false,
    canPlay: false,
    awaitingPlay: false,
    waitingForPlayer: null,
    playingPhase: false,
    currentTrick: 0,
    turnNotified: false,
    awaitingNextRound: false,
    nextRoundReady: false,
    chatCollapsed: false,
    isSpectator: false,
    pendingJoin: false,
    pendingMinLives: null,
    browsingLobby: false,
    gameStarted: false
};

const SESSION_KEY = 'presina_session';
let joinStartedRoomId = null;

function saveSession() {
    if (!gameState.roomId || !gameState.playerName) {
        return;
    }
    const payload = {
        roomId: gameState.roomId,
        roomName: gameState.roomName,
        playerName: gameState.playerName
    };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
}

function clearSession() {
    sessionStorage.removeItem(SESSION_KEY);
}

function loadSession() {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) {
        return null;
    }
    try {
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function attemptRejoin() {
    const session = loadSession();
    if (!session || !session.roomId || !session.playerName) {
        return;
    }
    gameState.playerName = session.playerName;
    socket.emit('rejoin_game', {
        roomCode: session.roomId,
        playerName: session.playerName
    });
}

// ============================================
// FUNZIONI UI - Navigazione
// ============================================

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId + '-screen').classList.add('active');
}

function updateLobbyControls() {
    const banner = document.getElementById('active-room-banner');
    const returnBtn = document.getElementById('return-to-room-btn');
    const createBtn = document.getElementById('create-room-btn');
    const hasRoom = !!gameState.roomId;

    if (banner) {
        if (hasRoom) {
            banner.textContent = 'Sei già in una stanza. Per crearne o entrare in un\'altra devi prima chiuderla.';
            banner.style.display = 'block';
        } else {
            banner.style.display = 'none';
        }
    }
    if (returnBtn) {
        returnBtn.style.display = hasRoom ? 'block' : 'none';
    }
    if (createBtn) {
        createBtn.disabled = hasRoom;
    }
}

function showLobbyList() {
    gameState.browsingLobby = true;
    showScreen('lobby');
    socket.emit('get_rooms');
    updateLobbyControls();
}

function returnToMyRoom() {
    if (!gameState.roomId) {
        return;
    }
    gameState.browsingLobby = false;
    showScreen(gameState.gameStarted ? 'game' : 'room');
    updateLobbyControls();
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

function addChatMessage(data) {
    const messagesDiv = document.getElementById('chat-messages');
    if (!messagesDiv || !data || !data.message) {
        return;
    }
    const msgDiv = document.createElement('div');
    const isSelf = data.playerName === gameState.playerName;
    msgDiv.className = 'chat-message' + (isSelf ? ' self' : '');

    const nameEl = document.createElement('strong');
    nameEl.textContent = `${data.playerName || 'Giocatore'}: `;
    const textEl = document.createElement('span');
    textEl.textContent = data.message;

    msgDiv.appendChild(nameEl);
    msgDiv.appendChild(textEl);
    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    if (!input) {
        return;
    }
    const message = input.value.trim();
    if (!message || !gameState.roomId) {
        return;
    }
    socket.emit('chat_message', {
        roomId: gameState.roomId,
        message: message
    });
    input.value = '';
    input.focus();
}

function setChatCollapsed(collapsed) {
    const panel = document.getElementById('chat-panel');
    const btn = document.getElementById('chat-toggle-btn');
    if (!panel || !btn) {
        return;
    }
    panel.classList.toggle('collapsed', collapsed);
    gameState.chatCollapsed = collapsed;
    btn.textContent = collapsed ? 'Apri' : 'Riduci';
    btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
}

function toggleChatPanel() {
    const panel = document.getElementById('chat-panel');
    if (!panel) {
        return;
    }
    const collapsed = !panel.classList.contains('collapsed');
    setChatCollapsed(collapsed);
}

function renderFinalScreen(data) {
    const summaryEl = document.getElementById('final-summary');
    const standingsEl = document.getElementById('final-standings');
    if (!summaryEl || !standingsEl) {
        return;
    }
    standingsEl.innerHTML = '';
    if (data && Array.isArray(data.winners) && data.winners.length > 0) {
        if (data.winners.length === 1) {
            summaryEl.textContent = `Vincitore: ${data.winners[0]} con ${data.maxLives} vite`;
        } else {
            summaryEl.textContent = `Pareggio tra: ${data.winners.join(', ')} con ${data.maxLives} vite`;
        }
    } else {
        summaryEl.textContent = 'Partita terminata';
    }

    if (data && Array.isArray(data.finalStandings)) {
        data.finalStandings.forEach((p) => {
            const li = document.createElement('li');
            li.textContent = `${p.playerName} - ${p.lives} ❤️`;
            standingsEl.appendChild(li);
        });
    }
}

function notifyMyTurn() {
    if (gameState.turnNotified) {
        return;
    }
    gameState.turnNotified = true;
    showNotification('È il tuo turno!');
}

function ensureTrickGroup(trickNumber) {
    if (!trickNumber) {
        return null;
    }
    const cardsPlayedDiv = document.getElementById('cards-played');
    if (!cardsPlayedDiv) {
        return null;
    }
    let group = cardsPlayedDiv.querySelector(`.trick-group[data-trick="${trickNumber}"]`);
    if (group) {
        return group;
    }
    group = document.createElement('div');
    group.className = 'trick-group';
    group.dataset.trick = String(trickNumber);

    const divider = document.createElement('div');
    divider.className = 'trick-divider';
    divider.dataset.trick = String(trickNumber);
    divider.textContent = `Mano ${trickNumber}`;

    const cardsContainer = document.createElement('div');
    cardsContainer.className = 'trick-cards';

    group.appendChild(divider);
    group.appendChild(cardsContainer);
    cardsPlayedDiv.prepend(group);
    return group;
}

function hideCardConfirmation() {
    const confirmation = document.getElementById('card-confirmation');
    const label = document.getElementById('selected-card-label');
    confirmation.style.display = 'none';
    label.textContent = '';
}

function clearCardSelection(preservePending = false) {
    if (gameState.selectedCardElement) {
        gameState.selectedCardElement.classList.remove('selected');
    }
    gameState.selectedCardElement = null;
    if (!preservePending) {
        gameState.pendingCardIndex = null;
    }
    hideCardConfirmation();
}

function refreshCardInteractivity() {
    const canInteract = gameState.isMyTurn && !gameState.awaitingPlay;
    gameState.canPlay = canInteract;

    document.querySelectorAll('#player-hand .card:not(.played)').forEach(card => {
        if (canInteract) {
            card.classList.remove('disabled');
        } else {
            card.classList.add('disabled');
        }
    });

    if (!canInteract) {
        if (gameState.awaitingPlay) {
            if (gameState.selectedCardElement) {
                gameState.selectedCardElement.classList.remove('selected');
            }
            hideCardConfirmation();
        } else {
            clearCardSelection();
        }
    }
}

function updateSpectatorUI() {
    const banner = document.getElementById('spectator-banner');
    const handArea = document.getElementById('hand-area');
    const bettingArea = document.getElementById('betting-area');

    if (gameState.isSpectator || gameState.pendingJoin) {
        if (banner) {
            if (gameState.pendingJoin) {
                const hasLives = gameState.pendingMinLives !== null && gameState.pendingMinLives !== undefined;
                const livesText = hasLives ? ` (vite: ${gameState.pendingMinLives})` : '';
                banner.textContent = `Sei in attesa di entrare dal prossimo turno${livesText}.`;
            } else {
                banner.textContent = 'Sei spettatore: puoi seguire la partita e usare la chat.';
            }
            banner.style.display = 'block';
        }
        if (handArea) {
            handArea.style.display = 'none';
        }
        if (bettingArea) {
            bettingArea.style.display = 'none';
        }
    } else {
        if (banner) {
            banner.style.display = 'none';
        }
        if (handArea) {
            handArea.style.display = '';
        }
    }
}

function showNextRoundOverlay(isLastRound = false) {
    const overlay = document.getElementById('next-round-overlay');
    if (!overlay) {
        return;
    }
    const title = document.getElementById('next-round-title');
    const note = document.getElementById('next-round-note');
    const status = document.getElementById('next-round-status');
    const btn = document.getElementById('next-round-btn');

    overlay.style.display = 'flex';
    if (title) {
        title.textContent = isLastRound ? 'Fine partita' : 'Turno terminato';
    }
    if (note) {
        note.textContent = isLastRound
            ? 'Premi per vedere la classifica finale.'
            : 'Premi quando sei pronto a continuare.';
    }
    if (status) {
        status.textContent = '';
    }
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Prossimo turno';
    }
}

function hideNextRoundOverlay() {
    const overlay = document.getElementById('next-round-overlay');
    if (!overlay) {
        return;
    }
    overlay.style.display = 'none';
}

function updateNextRoundOverlay(state) {
    if (gameState.isSpectator || gameState.pendingJoin || gameState.browsingLobby) {
        hideNextRoundOverlay();
        return;
    }
    const awaiting = !!(state && state.awaitingNextRound);
    gameState.awaitingNextRound = awaiting;
    if (!awaiting) {
        gameState.nextRoundReady = false;
        hideNextRoundOverlay();
        return;
    }

    const readyList = Array.isArray(state.readyForNextRound) ? state.readyForNextRound : [];
    const connectedPlayers = Array.isArray(state.players)
        ? state.players.filter(p => p.connected !== false)
        : [];
    const total = connectedPlayers.length;
    const readyCount = connectedPlayers.filter(p => readyList.includes(p.socketId)).length;
    const isReady = readyList.includes(gameState.playerId);
    gameState.nextRoundReady = isReady;

    showNextRoundOverlay(state.currentRound >= state.totalRounds);

    const status = document.getElementById('next-round-status');
    if (status && total > 0) {
        status.textContent = `Pronti ${readyCount}/${total}`;
    }

    const btn = document.getElementById('next-round-btn');
    if (btn) {
        btn.disabled = isReady;
        if (isReady) {
            btn.textContent = 'In attesa...';
        } else {
            btn.textContent = 'Prossimo turno';
        }
    }
}

function requestNextRound() {
    if (!gameState.roomId || gameState.nextRoundReady) {
        return;
    }
    socket.emit('next_round', {
        roomId: gameState.roomId
    });
    const btn = document.getElementById('next-round-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'In attesa...';
    }
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
    gameState.browsingLobby = false;
    showScreen('lobby');
    
    // Richiedi lista stanze
    socket.emit('get_rooms');
    updateLobbyControls();
}

function createRoom() {
    if (gameState.roomId) {
        showNotification('Sei già in una stanza. Chiudila prima di crearne un\'altra.', true);
        return;
    }
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

function joinRoom(roomId, joinMode = null) {
    if (gameState.roomId) {
        if (roomId === gameState.roomId) {
            returnToMyRoom();
        } else {
            showNotification('Sei già in una stanza. Chiudila prima di entrare in un\'altra.', true);
        }
        return;
    }
    const payload = {
        roomId: roomId,
        playerName: gameState.playerName
    };
    if (joinMode) {
        payload.joinMode = joinMode;
    }
    socket.emit('join_room', payload);
}

function openJoinStartedModal(roomId) {
    if (gameState.roomId) {
        showNotification('Sei già in una stanza. Chiudila prima di entrare in un\'altra.', true);
        return;
    }
    joinStartedRoomId = roomId;
    const modal = document.getElementById('join-started-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeJoinStartedModal() {
    const modal = document.getElementById('join-started-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    joinStartedRoomId = null;
}

function joinStartedAsPlayer() {
    if (!joinStartedRoomId) {
        return;
    }
    joinRoom(joinStartedRoomId, 'player');
    closeJoinStartedModal();
}

function joinStartedAsSpectator() {
    if (!joinStartedRoomId) {
        return;
    }
    joinRoom(joinStartedRoomId, 'spectator');
    closeJoinStartedModal();
}

function leaveRoom() {
    socket.emit('leave_room', {
        roomId: gameState.roomId
    });
    
    gameState.roomId = '';
    gameState.roomName = '';
    gameState.isAdmin = false;
    gameState.pendingCardIndex = null;
    gameState.selectedCardElement = null;
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.canPlay = false;
    gameState.awaitingPlay = false;
    gameState.waitingForPlayer = null;
    gameState.playingPhase = false;
    gameState.awaitingNextRound = false;
    gameState.nextRoundReady = false;
    gameState.isSpectator = false;
    gameState.pendingJoin = false;
    gameState.pendingMinLives = null;
    gameState.browsingLobby = false;
    gameState.gameStarted = false;
    clearCardSelection();
    clearSession();
    hideNextRoundOverlay();
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }
    
    showScreen('lobby');
    socket.emit('get_rooms');
    updateLobbyControls();
}

function startGame() {
    console.log('Avvio partita per stanza:', gameState.roomId);
    socket.emit('start_game', {
        roomId: gameState.roomId
    });
}

function kickPlayer(playerId, playerName) {
    if (!gameState.isAdmin || !playerId) {
        return;
    }
    if (!confirm(`Rimuovere ${playerName} dalla stanza?`)) {
        return;
    }
    
    socket.emit('kick_player', {
        roomId: gameState.roomId,
        targetId: playerId
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
        const hasRoom = !!gameState.roomId;
        const isOwnRoom = hasRoom && room.id === gameState.roomId;
        
        const info = document.createElement('div');
        info.className = 'room-info-card';
        info.innerHTML = `
            <h3>${room.name}${isOwnRoom ? ' (La tua stanza)' : ''}</h3>
            <p>👥 ${room.playerCount}/8 giocatori</p>
            <span class="room-status ${statusClass}">${statusText}</span>
        `;
        
        const button = document.createElement('button');
        button.className = 'btn btn-primary';
        if (isOwnRoom) {
            button.textContent = 'Rientra';
            button.addEventListener('click', returnToMyRoom);
        } else if (room.started) {
            button.textContent = hasRoom ? 'Già in una stanza' : 'Guarda / Entra';
            button.disabled = hasRoom;
            if (!hasRoom) {
                button.addEventListener('click', () => openJoinStartedModal(room.id));
            }
        } else {
            const isFull = room.playerCount >= 8;
            button.textContent = hasRoom ? 'Già in una stanza' : (isFull ? 'Stanza piena' : 'Unisciti');
            button.disabled = hasRoom || isFull;
            if (!hasRoom && !isFull) {
                button.addEventListener('click', () => joinRoom(room.id));
            }
        }
        
        roomCard.appendChild(info);
        roomCard.appendChild(button);
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

function playCard(cardOrIndex) {
    if (!gameState.canPlay || gameState.awaitingPlay) {
        return;
    }
    
    const hand = Array.from(document.querySelectorAll('#player-hand .card:not(.played)'));
    let card = null;
    let cardIndex = -1;

    if (typeof cardOrIndex === 'number') {
        cardIndex = cardOrIndex;
        card = hand[cardIndex];
    } else if (cardOrIndex && cardOrIndex.classList) {
        card = cardOrIndex;
        cardIndex = hand.indexOf(card);
    }
    
    if (!card || cardIndex < 0 || card.classList.contains('disabled') || card.classList.contains('played')) {
        return;
    }
    
    if (gameState.selectedCardElement) {
        gameState.selectedCardElement.classList.remove('selected');
    }
    
    gameState.selectedCardElement = card;
    gameState.pendingCardIndex = cardIndex;
    card.classList.add('selected');
    
    const label = document.getElementById('selected-card-label');
    const rankName = card.dataset.rankName || '';
    const suitName = card.dataset.suitName || '';
    label.textContent = rankName && suitName ? `${rankName} di ${suitName}` : 'Carta selezionata';
    document.getElementById('card-confirmation').style.display = 'flex';
}

function confirmSelectedCard() {
    if (!gameState.canPlay || gameState.awaitingPlay || !gameState.selectedCardElement) {
        return;
    }
    
    const hand = Array.from(document.querySelectorAll('#player-hand .card:not(.played)'));
    const index = hand.indexOf(gameState.selectedCardElement);
    if (index === -1) {
        clearCardSelection();
        return;
    }
    
    gameState.pendingCardIndex = index;
    gameState.awaitingPlay = true;
    refreshCardInteractivity();
    hideCardConfirmation();
    
    const isJoker = gameState.selectedCardElement.dataset.isJoker === 'true';
    if (isJoker) {
        document.getElementById('joker-modal').style.display = 'flex';
    } else {
        socket.emit('play_card', {
            roomId: gameState.roomId,
            cardIndex: index
        });
    }
}

function cancelSelectedCard() {
    clearCardSelection();
    refreshCardInteractivity();
}

function selectJokerMode(mode) {
    document.getElementById('joker-modal').style.display = 'none';

    if (gameState.pendingCardIndex === null || gameState.pendingCardIndex === undefined) {
        gameState.awaitingPlay = false;
        refreshCardInteractivity();
        return;
    }

    socket.emit('play_card', {
        roomId: gameState.roomId,
        cardIndex: gameState.pendingCardIndex,
        jokerMode: mode
    });
}

// ============================================
// SOCKET EVENT LISTENERS
// ============================================

// Lista stanze
socket.on('rooms_list', (rooms) => {
    renderRoomsList(rooms);
    updateLobbyControls();
});

// Stanza creata
socket.on('room_created', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = true;
    gameState.turnNotified = false;
    gameState.isSpectator = false;
    gameState.pendingJoin = false;
    gameState.pendingMinLives = null;
    gameState.browsingLobby = false;
    gameState.gameStarted = false;
    saveSession();
    
    document.getElementById('room-title').textContent = '🏠 ' + data.roomName;
    document.getElementById('admin-controls').style.display = 'block';
    document.getElementById('waiting-message').style.display = 'none';
    
    showScreen('room');
    updateSpectatorUI();
    showNotification('Stanza creata!');
});

// Unito alla stanza
socket.on('room_joined', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = false;
    gameState.turnNotified = false;
    gameState.isSpectator = false;
    gameState.pendingJoin = false;
    gameState.pendingMinLives = null;
    gameState.browsingLobby = false;
    gameState.gameStarted = false;
    saveSession();
    
    document.getElementById('room-title').textContent = '🏠 ' + data.roomName;
    document.getElementById('admin-controls').style.display = 'none';
    document.getElementById('waiting-message').style.display = 'block';
    
    showScreen('room');
    updateSpectatorUI();
    showNotification('Ti sei unito alla stanza!');
});

// Entrato come spettatore
socket.on('spectator_joined', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = false;
    gameState.turnNotified = false;
    gameState.isSpectator = true;
    gameState.pendingJoin = false;
    gameState.pendingMinLives = null;
    gameState.browsingLobby = false;
    gameState.gameStarted = true;
    clearSession();
    hideNextRoundOverlay();
    updateSpectatorUI();
    showScreen('game');
    showNotification('Sei entrato come spettatore');
});

// Entrato in attesa del prossimo turno
socket.on('pending_joined', (data) => {
    gameState.roomId = data.roomId;
    gameState.roomName = data.roomName;
    gameState.playerId = data.playerId;
    gameState.isAdmin = false;
    gameState.turnNotified = false;
    gameState.isSpectator = true;
    gameState.pendingJoin = true;
    gameState.pendingMinLives = data.minLives !== undefined ? data.minLives : null;
    gameState.browsingLobby = false;
    gameState.gameStarted = true;
    clearSession();
    hideNextRoundOverlay();
    updateSpectatorUI();
    showScreen('game');
    showNotification('Entrerai dal prossimo turno');
});

// Stato stanza aggiornato
socket.on('room_state', (state) => {
    updateRoomState(state);
});

// Partita iniziata
socket.on('game_started', (data) => {
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.awaitingPlay = false;
    gameState.awaitingNextRound = false;
    gameState.nextRoundReady = false;
    gameState.gameStarted = true;
    hideNextRoundOverlay();
    refreshCardInteractivity();
    if (!gameState.browsingLobby) {
        showScreen('game');
    }
    updateSpectatorUI();
    showNotification('La partita è iniziata!');
});

// Turno iniziato
socket.on('round_started', (data) => {
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.awaitingPlay = false;
    gameState.awaitingNextRound = false;
    gameState.nextRoundReady = false;
    hideNextRoundOverlay();
    refreshCardInteractivity();
    clearCardSelection();
    document.getElementById('trick-area').style.display = 'none';
    document.getElementById('cards-played').innerHTML = '';
    gameState.currentTrick = 0;
    document.getElementById('current-round').textContent = data.round;
    document.getElementById('cards-this-round').textContent = data.cardsThisRound;
    document.getElementById('total-tricks').textContent = data.cardsThisRound;
    
    addGameMessage(`Turno ${data.round} iniziato - ${data.cardsThisRound} carte`, 'info');
    updateSpectatorUI();
});

// Mano del giocatore
socket.on('player_hand', (data) => {
    displayPlayerHand(data);
});

// Richiesta puntata
socket.on('request_bet', (data) => {
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.awaitingPlay = false;
    refreshCardInteractivity();
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
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    refreshCardInteractivity();
    gameState.currentTrick = data.trickNumber;
    document.getElementById('trick-number').textContent = data.trickNumber;
    document.getElementById('trick-area').style.display = 'block';
    ensureTrickGroup(data.trickNumber);
    
    document.getElementById('phase-title').textContent = 'Fase di Gioco';
    document.getElementById('phase-description').textContent = `Mano ${data.trickNumber} di ${data.totalTricks}`;
});

// Richiesta carta
socket.on('request_card', (data) => {
    gameState.isMyTurn = true;
    gameState.awaitingPlay = false;
    clearCardSelection();
    refreshCardInteractivity();
    addGameMessage(`${data.playerName}, gioca una carta!`, 'info');
    notifyMyTurn();
});

// Richiesta modalità jolly (fallback server)
socket.on('request_joker_mode', () => {
    if (gameState.pendingCardIndex === null && gameState.selectedCardElement) {
        const hand = Array.from(document.querySelectorAll('#player-hand .card:not(.played)'));
        const index = hand.indexOf(gameState.selectedCardElement);
        if (index !== -1) {
            gameState.pendingCardIndex = index;
        }
    }
    gameState.awaitingPlay = true;
    refreshCardInteractivity();
    document.getElementById('joker-modal').style.display = 'flex';
});

// Carta giocata
socket.on('card_played', (data) => {
    addGameMessage(`${data.playerName} ha giocato ${data.card.rankName} di ${data.card.suitName}`, 'info');
    
    const trickGroup = ensureTrickGroup(gameState.currentTrick);
    const cardsPlayedDiv = trickGroup ? trickGroup.querySelector('.trick-cards') : document.getElementById('cards-played');
    const playedCardDiv = document.createElement('div');
    playedCardDiv.className = 'played-card';
    playedCardDiv.innerHTML = `
        <div class="player-name">${data.playerName}</div>
        ${createCardHTML(data.card, -1, false)}
    `;
    cardsPlayedDiv.appendChild(playedCardDiv);
    
    if (data.playerName === gameState.playerName) {
        let playedEl = gameState.selectedCardElement;
        
        if (!playedEl) {
            const handCards = document.querySelectorAll('#player-hand .card:not(.played)');
            handCards.forEach(c => {
                if (!playedEl && c.dataset.rankName === data.card.rankName && c.dataset.suitName === data.card.suitName) {
                    playedEl = c;
                }
            });
        }
        
        if (playedEl) {
            playedEl.classList.add('played');
            playedEl.style.display = 'none';
        }
        
        gameState.awaitingPlay = false;
        gameState.isMyTurn = false;
        gameState.turnNotified = false;
        clearCardSelection();
        refreshCardInteractivity();
    }
});

// Mano vinta
socket.on('trick_won', (data) => {
    addGameMessage(`${data.winnerName} vince la mano con ${data.winningCard.rankName} di ${data.winningCard.suitName}!`, 'success');
});

// Turno terminato
socket.on('round_ended', (data) => {
    document.getElementById('trick-area').style.display = 'none';
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.awaitingPlay = false;
    refreshCardInteractivity();
    
    let message = 'Risultati del turno:\n\n';
    data.results.forEach(r => {
        const status = r.correct ? '✅' : '❌';
        message += `${status} ${r.playerName}: ${r.bet}/${r.tricksWon} (${r.lives} ❤️)\n`;
    });
    
    addGameMessage(message, 'info');
    if (!gameState.isSpectator && !gameState.pendingJoin && !gameState.browsingLobby) {
        showNextRoundOverlay(!!data.isLastRound);
    }
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
    
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.awaitingPlay = false;
    gameState.awaitingNextRound = false;
    gameState.nextRoundReady = false;
    hideNextRoundOverlay();
    refreshCardInteractivity();

    renderFinalScreen(data);
    showScreen('final');
});

// Messaggi chat
socket.on('chat_message', (data) => {
    addChatMessage(data);
});

// Errore
socket.on('error', (data) => {
    showNotification(data.message, true);
    
    if (gameState.awaitingPlay) {
        gameState.awaitingPlay = false;
        clearCardSelection();
        refreshCardInteractivity();
    }
});

// Giocatore disconnesso
socket.on('player_disconnected', (data) => {
    showNotification(data.message, true);
});

// Rimozione forzata dalla stanza
socket.on('kicked', (data) => {
    showNotification(data.message || 'Sei stato rimosso dalla stanza', true);
    gameState.roomId = '';
    gameState.roomName = '';
    gameState.isAdmin = false;
    gameState.pendingCardIndex = null;
    gameState.selectedCardElement = null;
    gameState.isMyTurn = false;
    gameState.turnNotified = false;
    gameState.canPlay = false;
    gameState.awaitingPlay = false;
    gameState.waitingForPlayer = null;
    gameState.playingPhase = false;
    gameState.awaitingNextRound = false;
    gameState.nextRoundReady = false;
    gameState.isSpectator = false;
    gameState.pendingJoin = false;
    gameState.pendingMinLives = null;
    clearCardSelection();
    clearSession();
    hideNextRoundOverlay();
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }
    showScreen('lobby');
    socket.emit('get_rooms');
    updateLobbyControls();
});

// Rientro dopo refresh
socket.on('rejoin_success', (data) => {
    const session = loadSession();
    gameState.roomId = data.roomCode;
    gameState.roomName = data.roomName || (session && session.roomName) || data.roomCode;
    gameState.playerId = data.playerId;
    gameState.playerName = data.playerName || gameState.playerName;
    gameState.isAdmin = !!data.isAdmin;
    gameState.turnNotified = false;
    gameState.browsingLobby = false;
    gameState.gameStarted = !!data.gameStarted;
    saveSession();

    document.getElementById('room-title').textContent = '🏠 ' + gameState.roomName;
    document.getElementById('admin-controls').style.display = gameState.isAdmin ? 'block' : 'none';
    document.getElementById('waiting-message').style.display = gameState.isAdmin ? 'none' : 'block';

    showScreen(data.gameStarted ? 'game' : 'room');
    updateSpectatorUI();
    showNotification('Sei rientrato nella partita!');
});

socket.on('rejoin_failed', (data) => {
    clearSession();
    showNotification(data.message || 'Impossibile rientrare nella partita', true);
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

    const me = state.players.find(p => p.socketId === gameState.playerId);
    gameState.isAdmin = !!(me && me.isAdmin);
    gameState.gameStarted = !!state.gameStarted;
    document.getElementById('admin-controls').style.display = gameState.isAdmin ? 'block' : 'none';
    document.getElementById('waiting-message').style.display = gameState.isAdmin ? 'none' : 'block';
    
    state.players.forEach(player => {
        const li = document.createElement('li');
        const isMe = player.socketId === gameState.playerId;
        const adminBadge = player.isAdmin ? ' 👑' : '';
        const isOnline = player.connected !== false;
        const presenceBadge = isOnline ? ' 🟢 Online' : ' 🔴 Offline';
        li.textContent = `${player.name}${adminBadge}${isMe ? ' (Tu)' : ''}${presenceBadge}`;
        li.className = isMe ? 'current-player' : '';
        if (!isOnline) {
            li.classList.add('offline');
        }
        
        if (gameState.isAdmin && !isMe) {
            const kickBtn = document.createElement('button');
            kickBtn.className = 'btn btn-danger btn-small';
            kickBtn.textContent = 'Rimuovi';
            kickBtn.addEventListener('click', () => kickPlayer(player.socketId, player.name));
            li.appendChild(kickBtn);
        }
        
        playersList.appendChild(li);
    });
    
    // Se la partita è iniziata, vai alla schermata gioco
    if (state.gameStarted) {
        if (!gameState.browsingLobby) {
            showScreen('game');
        }
        updatePlayersStatus(state);
    }
    updateLobbyControls();
}

function updatePlayersStatus(state) {
    const statusDiv = document.getElementById('players-status');
    statusDiv.innerHTML = '';
    
    gameState.gameStarted = !!state.gameStarted;
    gameState.waitingForPlayer = state.waitingForPlayer || null;
    gameState.playingPhase = !!state.playingPhase;
    if (state.currentRound) {
        const roundEl = document.getElementById('current-round');
        if (roundEl) {
            roundEl.textContent = state.currentRound;
        }
    }
    if (state.cardsThisRound) {
        const cardsEl = document.getElementById('cards-this-round');
        const totalEl = document.getElementById('total-tricks');
        if (cardsEl) {
            cardsEl.textContent = state.cardsThisRound;
        }
        if (totalEl) {
            totalEl.textContent = state.cardsThisRound;
        }
    }
    const meInPlayers = Array.isArray(state.players)
        ? state.players.some(p => p.socketId === gameState.playerId)
        : false;
    if (meInPlayers && (gameState.isSpectator || gameState.pendingJoin)) {
        gameState.isSpectator = false;
        gameState.pendingJoin = false;
        gameState.pendingMinLives = null;
        saveSession();
        updateSpectatorUI();
    }
    const myTurn = gameState.playingPhase && gameState.waitingForPlayer === gameState.playerName;
    if (myTurn !== gameState.isMyTurn) {
        gameState.isMyTurn = myTurn;
        if (!myTurn) {
            gameState.turnNotified = false;
        } else {
            notifyMyTurn();
        }
        if (!myTurn) {
            gameState.awaitingPlay = false;
        }
        refreshCardInteractivity();
    }
    
    state.players.forEach(player => {
        const div = document.createElement('div');
        div.className = 'player-status';
        
        if (state.waitingForPlayer === player.name) {
            div.classList.add('current');
        }
        const isOnline = player.connected !== false;
        if (!isOnline) {
            div.classList.add('offline');
        }
        
        let html = `<strong>${player.name}</strong><br>`;
        html += `<span class="player-presence ${isOnline ? 'online' : 'offline'}">` +
                `${isOnline ? '🟢 Online' : '🔴 Offline'}</span><br>`;
        html += `❤️ ${player.lives} vite<br>`;
        
        const hasBet = !!player.hasBet;
        if (state.bettingPhase) {
            if (hasBet) {
                html += `🎯 Puntata: ${player.bet}<br>`;
            } else {
                html += `⏳ Deve puntare<br>`;
            }
        } else if (hasBet && player.bet !== null && player.bet !== undefined) {
            html += `🎯 Puntata: ${player.bet}<br>`;
        }
        
        if (state.playingPhase && player.tricksWon !== undefined) {
            html += `🏆 Prese: ${player.tricksWon}`;
        }
        
        div.innerHTML = html;
        statusDiv.appendChild(div);
    });

    updateNextRoundOverlay(state);
}

function displayPlayerHand(data) {
    const handDiv = document.getElementById('player-hand');
    handDiv.innerHTML = '';
    const othersContainer = document.getElementById('other-players-cards');
    othersContainer.innerHTML = '';
    
    const specialNote = document.getElementById('special-round-note');
    gameState.awaitingPlay = false;
    clearCardSelection();
    
    if (data.specialRound && data.hideOwnCard) {
        specialNote.style.display = 'block';
        handDiv.innerHTML = createCardHTML({isHidden: true}, 0, true);
        
        if (data.otherPlayersCards && data.otherPlayersCards.length > 0) {
            const othersDiv = document.createElement('div');
            othersDiv.innerHTML = '<h4>Carte degli altri giocatori:</h4>';
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
            othersContainer.appendChild(othersDiv);
        }
    } else {
        specialNote.style.display = 'none';
        
        data.hand.forEach((card, index) => {
            handDiv.innerHTML += createCardHTML(card, index, true);
        });
    }
    
    refreshCardInteractivity();
}

function createCardHTML(card, index, clickable) {
    if (card.isHidden) {
        const onclick = clickable ? 'onclick="playCard(this)"' : '';
        return `<div class="card hidden" ${onclick} data-index="${index}" data-is-hidden="true">?</div>`;
    }
    
    const suitClass = ['bastoni', 'spade', 'coppe', 'denari'][card.suit];
    const suitSymbol = ['🌲', '⚔️', '🏆', '💰'][card.suit];
    const onclick = clickable ? 'onclick="playCard(this)"' : '';
    const jokerClass = card.isJoker ? ' joker' : '';
    let valueLabel = '';
    if (card.isJoker) {
        if (card.jokerMode === 'prende') {
            valueLabel = '40/40';
        } else if (card.jokerMode === 'lascia') {
            valueLabel = '0/40';
        } else {
            valueLabel = 'J';
        }
    } else if (card.value !== null && card.value !== undefined) {
        const numericValue = Number(card.value);
        if (!Number.isNaN(numericValue)) {
            const ordinal = Math.max(0, Math.min(39, numericValue)) + 1;
            valueLabel = `${ordinal}/40`;
        }
    }
    
    return `
        <div class="card ${suitClass}${jokerClass}" 
             ${onclick}
             data-index="${index}"
             data-is-joker="${card.isJoker}"
             data-rank-name="${card.rankName}"
             data-suit-name="${card.suitName}">
            ${valueLabel ? `<div class="card-value">${valueLabel}</div>` : ''}
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
        if (gameState.roomId) {
            showNotification('Sei già in una stanza. Chiudila prima di crearne un\'altra.', true);
            return;
        }
        document.getElementById('create-room-modal').style.display = 'flex';
    });
    document.getElementById('back-home-btn').addEventListener('click', () => {
        gameState.browsingLobby = false;
        showScreen('home');
    });
    document.getElementById('search-room').addEventListener('input', filterRooms);
    document.getElementById('return-to-room-btn').addEventListener('click', returnToMyRoom);
    
    // Modale Crea Stanza
    document.getElementById('confirm-create-btn').addEventListener('click', createRoom);
    document.getElementById('cancel-create-btn').addEventListener('click', () => {
        document.getElementById('create-room-modal').style.display = 'none';
    });

    // Modale Partita Iniziata
    document.getElementById('join-as-player-btn').addEventListener('click', joinStartedAsPlayer);
    document.getElementById('join-as-spectator-btn').addEventListener('click', joinStartedAsSpectator);
    document.getElementById('cancel-join-started-btn').addEventListener('click', closeJoinStartedModal);
    
    // Pulsanti Stanza
    document.getElementById('start-game-btn').addEventListener('click', startGame);
    document.getElementById('leave-room-btn').addEventListener('click', leaveRoom);
    document.getElementById('back-to-lobby-btn').addEventListener('click', showLobbyList);
    
    // Pulsanti Regole
    document.getElementById('back-from-rules-btn').addEventListener('click', () => showScreen('home'));

    // Pulsante Schermata Finale
    document.getElementById('back-to-lobby-btn').addEventListener('click', leaveRoom);
    
    // Pulsanti Jolly
    document.getElementById('joker-prende-btn').addEventListener('click', () => selectJokerMode('prende'));
    document.getElementById('joker-lascia-btn').addEventListener('click', () => selectJokerMode('lascia'));
    
    // Conferma carta
    document.getElementById('confirm-card-btn').addEventListener('click', confirmSelectedCard);
    document.getElementById('cancel-card-btn').addEventListener('click', cancelSelectedCard);

    // Pulsante Prossimo Turno
    document.getElementById('next-round-btn').addEventListener('click', requestNextRound);

    // Chat
    document.getElementById('chat-send-btn').addEventListener('click', sendChatMessage);
    document.getElementById('chat-input').addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            sendChatMessage();
        }
    });
    document.getElementById('chat-toggle-btn').addEventListener('click', toggleChatPanel);
    
    // Mostra schermata home
    showScreen('home');
    attemptRejoin();
});
