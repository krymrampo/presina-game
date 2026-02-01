/**
 * Presina - Main Application
 * Handles screen navigation and state management
 */

// ==================== State ====================
const App = {
    playerId: null,
    playerName: '',
    currentScreen: 'home',
    currentRoom: null,
    gameState: null,
    isAdmin: false,
    selectedCard: null,
    trickAdvanceScheduled: false,
    pendingJoinRoomId: null,
    gameStatePollInterval: null  // For polling game state when needed
};

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedPlayerId = sessionStorage.getItem('presina_player_id');
    const savedPlayerName = sessionStorage.getItem('presina_player_name');
    const savedRoom = sessionStorage.getItem('presina_room');
    
    if (savedPlayerId && savedPlayerName) {
        App.playerId = savedPlayerId;
        App.playerName = savedPlayerName;
        document.getElementById('player-name').value = savedPlayerName;
        
        // Restore room info if exists
        if (savedRoom) {
            try {
                App.currentRoom = JSON.parse(savedRoom);
                console.log('Restored room from session:', App.currentRoom);
            } catch (e) {
                console.error('Failed to parse saved room:', e);
                sessionStorage.removeItem('presina_room');
            }
        }
    } else {
        // Generate new player ID
        App.playerId = generatePlayerId();
        sessionStorage.setItem('presina_player_id', App.playerId);
    }
    
    setupEventListeners();
    autoEnterLobbyIfSaved();
});

function generatePlayerId() {
    return 'p_' + Math.random().toString(36).substr(2, 9);
}

function autoEnterLobbyIfSaved() {
    const savedPlayerId = sessionStorage.getItem('presina_player_id');
    const savedPlayerName = sessionStorage.getItem('presina_player_name');
    
    if (!savedPlayerId || !savedPlayerName) {
        return;
    }
    
    // Ensure state is restored
    App.playerId = savedPlayerId;
    App.playerName = savedPlayerName;
    document.getElementById('player-name').value = savedPlayerName;
    
    // Go straight to lobby list on refresh
    SocketClient.connect();
    SocketClient.registerPlayer();
    showScreen('lobby');
    SocketClient.listRooms();
    checkAndShowRejoinBanner();
}

// ==================== Screen Navigation ====================
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId + '-screen').classList.add('active');
    App.currentScreen = screenId;

    // Show chat only during game and game-over screens
    const gameChat = document.getElementById('game-chat');
    if (gameChat) {
        if (screenId === 'game' || screenId === 'game-over') {
            gameChat.classList.remove('hidden');
        } else {
            gameChat.classList.add('hidden');
        }
    }
    
    // Start/stop game state polling based on screen
    if (screenId === 'game') {
        startGameStatePolling();
    } else {
        stopGameStatePolling();
    }
}

// ==================== Game State Polling ====================
// Poll game state every 3 seconds when in game screen
// This ensures we stay in sync even if socket events are missed
function startGameStatePolling() {
    stopGameStatePolling(); // Clear any existing interval
    App.gameStatePollInterval = setInterval(() => {
        if (App.currentScreen === 'game' && App.currentRoom) {
            // Don't poll if user is selecting a card (to avoid UI disruption)
            if (!App.selectedCard) {
                SocketClient.requestGameState();
            }
        }
    }, 3000);
}

function stopGameStatePolling() {
    if (App.gameStatePollInterval) {
        clearInterval(App.gameStatePollInterval);
        App.gameStatePollInterval = null;
    }
}

// ==================== Event Listeners ====================
function setupEventListeners() {
    // Home screen
    document.getElementById('btn-enter-lobby').addEventListener('click', enterLobby);
    document.getElementById('btn-back-home-lobby').addEventListener('click', () => showScreen('home'));
    
    // Player name
    document.getElementById('player-name').addEventListener('input', (e) => {
        App.playerName = e.target.value.trim();
        sessionStorage.setItem('presina_player_name', App.playerName);
    });
    
    document.getElementById('player-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') enterLobby();
    });
    
    // Lobby
    document.getElementById('btn-create-room').addEventListener('click', showCreateRoomModal);
    document.getElementById('btn-cancel-create').addEventListener('click', hideCreateRoomModal);
    document.getElementById('btn-confirm-create').addEventListener('click', createRoom);
    document.getElementById('btn-search').addEventListener('click', searchRooms);
    document.getElementById('room-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchRooms();
    });
    document.getElementById('btn-rejoin').addEventListener('click', () => {
        SocketClient.rejoinGame();
    });
    document.getElementById('btn-abandon').addEventListener('click', abandonSavedRoom);
    
    // Room name enter key
    document.getElementById('room-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createRoom();
    });
    
    // Waiting room
    document.getElementById('btn-leave-room').addEventListener('click', leaveRoom);
    document.getElementById('btn-start-game').addEventListener('click', startGame);
    
    // Private room checkbox toggle
    const privateCheck = document.getElementById('room-private-check');
    if (privateCheck) {
        privateCheck.addEventListener('change', (e) => {
            const codeGroup = document.getElementById('room-code-group');
            if (e.target.checked) {
                codeGroup.classList.remove('hidden');
                // Generate random code if empty
                const codeInput = document.getElementById('room-access-code');
                if (!codeInput.value) {
                    codeInput.value = Math.random().toString(36).substring(2, 6).toUpperCase();
                }
            } else {
                codeGroup.classList.add('hidden');
            }
        });
    }
    
    // Join private room modal
    document.getElementById('btn-cancel-join-private').addEventListener('click', hideJoinPrivateModal);
    document.getElementById('btn-confirm-join-private').addEventListener('click', confirmJoinPrivate);
    document.getElementById('join-access-code').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') confirmJoinPrivate();
    });
    
    // Waiting chat
    document.getElementById('btn-send-waiting-chat').addEventListener('click', sendWaitingChatMessage);
    document.getElementById('waiting-chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendWaitingChatMessage();
    });
    
    // Game
    document.getElementById('btn-confirm-card').addEventListener('click', confirmCard);
    document.getElementById('btn-cancel-card').addEventListener('click', cancelCard);
    document.getElementById('btn-jolly-prende').addEventListener('click', () => chooseJolly('prende'));
    document.getElementById('btn-jolly-lascia').addEventListener('click', () => chooseJolly('lascia'));
    document.getElementById('btn-next-turn').addEventListener('click', readyNextTurn);
    
    // Chat toggle
    document.getElementById('chat-toggle').addEventListener('click', toggleChat);
    document.getElementById('btn-send-chat').addEventListener('click', sendChatMessage);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });
    
    // Game over
    document.getElementById('btn-back-lobby').addEventListener('click', backToLobby);
}

// ==================== Lobby Functions ====================
function enterLobby() {
    if (window.AuthUI && AuthUI.isLoggedIn()) {
        AuthUI.enterLobby();
        return;
    }
    const name = document.getElementById('player-name').value.trim();
    if (!name) {
        alert('Inserisci il tuo nome');
        return;
    }
    
    App.playerName = name;
    sessionStorage.setItem('presina_player_name', name);
    document.getElementById('player-name-display').textContent = name;
    
    // Connect socket and register
    SocketClient.connect();
    SocketClient.registerPlayer();
    
    showScreen('lobby');
    SocketClient.listRooms();
    
    // Show rejoin banner if we have a saved room
    checkAndShowRejoinBanner();
}

function checkAndShowRejoinBanner() {
    const savedRoom = sessionStorage.getItem('presina_room');
    const banner = document.getElementById('existing-room-banner');
    
    if (savedRoom && banner) {
        try {
            const roomData = JSON.parse(savedRoom);
            banner.querySelector('span').textContent = `Hai una partita in corso: "${roomData.name}"`;
            banner.classList.remove('hidden');
            App.currentRoom = roomData;
        } catch (e) {
            console.error('Failed to parse saved room:', e);
        }
    }
}

function abandonSavedRoom() {
    if (!confirm('Vuoi abbandonare questa stanza? Non potrai rientrare.')) {
        return;
    }
    
    SocketClient.abandonRoom();
    
    // Clear local session immediately
    App.currentRoom = null;
    App.gameState = null;
    sessionStorage.removeItem('presina_room');
    
    const banner = document.getElementById('existing-room-banner');
    if (banner) banner.classList.add('hidden');
    
    SocketClient.listRooms();
}

function showCreateRoomModal() {
    document.getElementById('create-room-modal').classList.remove('hidden');
    document.getElementById('room-name').value = `Stanza di ${App.playerName}`;
    document.getElementById('room-private-check').checked = false;
    document.getElementById('room-code-group').classList.add('hidden');
    document.getElementById('room-access-code').value = '';
    document.getElementById('room-name').focus();
}

function showJoinPrivateModal(roomId) {
    App.pendingJoinRoomId = roomId;
    document.getElementById('join-private-modal').classList.remove('hidden');
    document.getElementById('join-access-code').value = '';
    document.getElementById('join-access-code').focus();
}

function hideJoinPrivateModal() {
    document.getElementById('join-private-modal').classList.add('hidden');
    App.pendingJoinRoomId = null;
}

function confirmJoinPrivate() {
    const code = document.getElementById('join-access-code').value.trim();
    if (!code) {
        alert('Inserisci il codice di accesso');
        return;
    }
    if (App.pendingJoinRoomId) {
        SocketClient.joinRoom(App.pendingJoinRoomId, code);
        hideJoinPrivateModal();
    }
}

function hideCreateRoomModal() {
    document.getElementById('create-room-modal').classList.add('hidden');
}

function createRoom() {
    const roomName = document.getElementById('room-name').value.trim();
    if (!roomName) {
        alert('Inserisci un nome per la stanza');
        return;
    }
    
    const isPrivate = document.getElementById('room-private-check').checked;
    const accessCode = isPrivate ? document.getElementById('room-access-code').value.trim() : null;
    
    if (isPrivate && !accessCode) {
        alert('Inserisci un codice di accesso per la stanza privata');
        return;
    }
    
    SocketClient.createRoom(roomName, !isPrivate, accessCode);
    hideCreateRoomModal();
}

function searchRooms() {
    const query = document.getElementById('room-search').value.trim();
    if (query) {
        SocketClient.searchRooms(query);
    } else {
        SocketClient.listRooms();
    }
}

function joinRoom(roomId, isPrivate = false) {
    if (isPrivate) {
        showJoinPrivateModal(roomId);
    } else {
        SocketClient.joinRoom(roomId);
    }
}

function leaveRoom() {
    // Ask confirmation if game is in progress
    if (App.gameState && App.gameState.phase !== 'waiting' && App.gameState.phase !== 'game_over') {
        if (!confirm('Sei sicuro di voler abbandonare la partita in corso?')) {
            return;
        }
    }
    SocketClient.leaveRoom();
    // Clear saved room on explicit leave
    App.currentRoom = null;
    App.gameState = null;
    sessionStorage.removeItem('presina_room');
    showScreen('lobby');
    SocketClient.listRooms();
}

function kickPlayer(playerId) {
    SocketClient.kickPlayer(playerId);
}

function startGame() {
    SocketClient.startGame();
}



// ==================== Room UI Updates ====================
function updateRoomsList(rooms) {
    const container = document.getElementById('rooms-list');
    
    if (!rooms || rooms.length === 0) {
        container.innerHTML = '<p class="empty-message">Nessuna stanza disponibile. Creane una!</p>';
        return;
    }
    
    container.innerHTML = rooms.map(room => {
        const isPrivate = room.is_private || !room.is_public;
        const lockIcon = isPrivate ? '🔒 ' : '';
        const onClickAction = isPrivate ? `joinRoom('${room.room_id}', true)` : `joinRoom('${room.room_id}')`;
        
        return `
        <div class="room-item ${isPrivate ? 'private' : ''}">
            <div class="room-info">
                <h4>${lockIcon}${escapeHtml(room.name)}</h4>
                <span>${room.player_count}/${room.max_players} giocatori</span>
            </div>
            <div class="room-meta">
                <span class="status-badge status-${room.status}">${getStatusText(room.status)}</span>
                <button class="btn btn-primary btn-small" onclick="${onClickAction}">
                    ${isPrivate ? '🔒 Entra' : 'Entra'}
                </button>
            </div>
        </div>
    `}).join('');
}

function getStatusText(status) {
    switch(status) {
        case 'waiting': return 'In attesa';
        case 'playing': return 'In gioco';
        case 'finished': return 'Finita';
        default: return status;
    }
}

function updateWaitingRoom(gameState) {
    App.gameState = gameState;
    
    // Update room title
    document.getElementById('room-title').textContent = App.currentRoom?.name || 'Stanza';
    
    // Check if admin
    if (gameState.admin_id && App.currentRoom) {
        App.currentRoom.admin_id = gameState.admin_id;
    }
    App.isAdmin = gameState.admin_id === App.playerId;
    
    // Update admin controls
    const adminControls = document.getElementById('admin-controls');
    const roomCodeDisplay = document.getElementById('room-code-display');
    
    if (App.isAdmin) {
        adminControls.classList.remove('hidden');
        const canStart = gameState.players.filter(p => !p.is_spectator).length >= 2;
        document.getElementById('btn-start-game').disabled = !canStart;
        
        // Show access code for private rooms
        if (App.currentRoom?.access_code) {
            roomCodeDisplay.classList.remove('hidden');
            document.getElementById('display-access-code').textContent = App.currentRoom.access_code;
        } else {
            roomCodeDisplay.classList.add('hidden');
        }
    } else {
        adminControls.classList.add('hidden');
    }
    
    // Update players grid
    const container = document.getElementById('waiting-players');
    container.innerHTML = gameState.players.map(player => {
        // Determine status: online, away, or offline
        let statusClass = 'online';
        let statusText = 'Online';
        let statusDotClass = 'online';
        
        if (!player.is_online) {
            statusClass = 'offline';
            statusText = 'Offline';
            statusDotClass = 'offline';
        } else if (player.is_away) {
            statusClass = 'away';
            statusText = 'Assente';
            statusDotClass = 'away'; // yellow/amber color
        }
        
        return `
        <div class="player-card ${player.player_id === gameState.admin_id ? 'admin' : ''} ${statusClass}">
            ${App.isAdmin && player.player_id !== App.playerId ? `<button class="kick-btn" onclick="kickPlayer('${player.player_id}')">✕</button>` : ''}
            <div class="player-name">${escapeHtml(player.name)}</div>
            <div class="player-status">
                <span class="online-dot ${statusDotClass}"></span>
                ${statusText}
            </div>
        </div>
    `}).join('');
}

// ==================== Game Functions ====================
function selectCard(suit, value, displayName, event) {
    App.selectedCard = { suit, value, displayName };
    
    // Update UI
    document.querySelectorAll('.hand-area .card').forEach(c => c.classList.remove('selected'));
    if (event && event.target) {
        event.target.classList.add('selected');
    }
    
    document.getElementById('selected-card-name').textContent = displayName;
    document.getElementById('card-confirm-overlay').classList.remove('hidden');
    document.getElementById('card-confirm').classList.remove('hidden');
}

function confirmCard() {
    if (!App.selectedCard) return;
    
    // Disable button while waiting for server response
    const confirmBtn = document.getElementById('btn-confirm-card');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Giocando...';
    
    SocketClient.playCard(App.selectedCard.suit, App.selectedCard.value);
    // Don't clear selection yet - wait for server response
    // App.selectedCard will be cleared on successful game_state update
}

function cancelCard() {
    App.selectedCard = null;
    document.querySelectorAll('.hand-area .card').forEach(c => c.classList.remove('selected'));
    document.getElementById('card-confirm-overlay').classList.add('hidden');
    document.getElementById('card-confirm').classList.add('hidden');
    // Reset button state
    const confirmBtn = document.getElementById('btn-confirm-card');
    confirmBtn.disabled = false;
    confirmBtn.textContent = '✓ Gioca';
}

// Called after successful card play to reset UI
function clearCardSelection() {
    App.selectedCard = null;
    document.querySelectorAll('.hand-area .card').forEach(c => c.classList.remove('selected'));
    document.getElementById('card-confirm-overlay').classList.add('hidden');
    document.getElementById('card-confirm').classList.add('hidden');
    const confirmBtn = document.getElementById('btn-confirm-card');
    confirmBtn.disabled = false;
    confirmBtn.textContent = '✓ Gioca';
}

function makeBet(bet) {
    SocketClient.makeBet(bet);
}

function chooseJolly(choice) {
    SocketClient.chooseJolly(choice);
    document.getElementById('jolly-choice').classList.add('hidden');
}

function readyNextTurn() {
    SocketClient.readyNextTurn();
    document.getElementById('btn-next-turn').disabled = true;
    document.getElementById('btn-next-turn').textContent = 'In attesa...';
}

function backToLobby() {
    SocketClient.leaveRoom();
    App.currentRoom = null;
    App.gameState = null;
    sessionStorage.removeItem('presina_room');
    showScreen('lobby');
    SocketClient.listRooms();
}

// ==================== Chat Functions ====================
function toggleChat() {
    Chat.toggle();
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (message) {
        SocketClient.sendMessage(message);
        input.value = '';
    }
}

function sendWaitingChatMessage() {
    const input = document.getElementById('waiting-chat-input');
    const message = input.value.trim();
    if (message) {
        SocketClient.sendMessage(message);
        input.value = '';
    }
}

// ==================== Utility Functions ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for use in other modules
window.App = App;
window.showScreen = showScreen;
window.updateRoomsList = updateRoomsList;
window.updateWaitingRoom = updateWaitingRoom;
window.selectCard = selectCard;
window.makeBet = makeBet;
window.joinRoom = joinRoom;
window.kickPlayer = kickPlayer;
window.escapeHtml = escapeHtml;
window.clearCardSelection = clearCardSelection;
