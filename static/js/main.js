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
    selectedCard: null
};

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedPlayerId = sessionStorage.getItem('presina_player_id');
    const savedPlayerName = sessionStorage.getItem('presina_player_name');
    
    if (savedPlayerId && savedPlayerName) {
        App.playerId = savedPlayerId;
        App.playerName = savedPlayerName;
        document.getElementById('player-name').value = savedPlayerName;
    } else {
        // Generate new player ID
        App.playerId = generatePlayerId();
        sessionStorage.setItem('presina_player_id', App.playerId);
    }
    
    setupEventListeners();
});

function generatePlayerId() {
    return 'p_' + Math.random().toString(36).substr(2, 9);
}

// ==================== Screen Navigation ====================
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId + '-screen').classList.add('active');
    App.currentScreen = screenId;
}

// ==================== Event Listeners ====================
function setupEventListeners() {
    // Home screen
    document.getElementById('btn-enter-lobby').addEventListener('click', enterLobby);
    document.getElementById('btn-rules').addEventListener('click', () => showScreen('rules'));
    document.getElementById('btn-back-home').addEventListener('click', () => showScreen('home'));
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
    
    // Room name enter key
    document.getElementById('room-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createRoom();
    });
    
    // Waiting room
    document.getElementById('btn-leave-room').addEventListener('click', leaveRoom);
    document.getElementById('btn-start-game').addEventListener('click', startGame);
    
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
    const name = document.getElementById('player-name').value.trim();
    if (!name) {
        showNotification('Inserisci il tuo nome', 'error');
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
}

function showCreateRoomModal() {
    document.getElementById('create-room-modal').classList.remove('hidden');
    document.getElementById('room-name').value = `Stanza di ${App.playerName}`;
    document.getElementById('room-name').focus();
}

function hideCreateRoomModal() {
    document.getElementById('create-room-modal').classList.add('hidden');
}

function createRoom() {
    const roomName = document.getElementById('room-name').value.trim();
    if (!roomName) {
        showNotification('Inserisci un nome per la stanza', 'error');
        return;
    }
    
    SocketClient.createRoom(roomName);
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

function joinRoom(roomId) {
    SocketClient.joinRoom(roomId);
}

function leaveRoom() {
    SocketClient.leaveRoom();
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
    
    container.innerHTML = rooms.map(room => `
        <div class="room-item">
            <div class="room-info">
                <h4>${escapeHtml(room.name)}</h4>
                <span>${room.player_count}/${room.max_players} giocatori</span>
            </div>
            <div class="room-meta">
                <span class="status-badge status-${room.status}">${getStatusText(room.status)}</span>
                <button class="btn btn-primary btn-small" onclick="joinRoom('${room.room_id}')">
                    ${room.status === 'waiting' ? 'Entra' : 'Guarda'}
                </button>
            </div>
        </div>
    `).join('');
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
    App.isAdmin = App.currentRoom?.admin_id === App.playerId;
    
    // Update admin controls
    const adminControls = document.getElementById('admin-controls');
    if (App.isAdmin) {
        adminControls.classList.remove('hidden');
        const canStart = gameState.players.filter(p => !p.is_spectator).length >= 2;
        document.getElementById('btn-start-game').disabled = !canStart;
    } else {
        adminControls.classList.add('hidden');
    }
    
    // Update players grid
    const container = document.getElementById('waiting-players');
    container.innerHTML = gameState.players.map(player => `
        <div class="player-card ${player.player_id === App.currentRoom?.admin_id ? 'admin' : ''} ${!player.is_online ? 'offline' : ''}">
            ${App.isAdmin && player.player_id !== App.playerId ? `<button class="kick-btn" onclick="kickPlayer('${player.player_id}')">✕</button>` : ''}
            <div class="player-name">${escapeHtml(player.name)}</div>
            <div class="player-status">
                <span class="online-dot ${player.is_online ? 'online' : 'offline'}"></span>
                ${player.is_online ? 'Online' : 'Offline'}
            </div>
        </div>
    `).join('');
}

// ==================== Game Functions ====================
function selectCard(suit, value, displayName) {
    App.selectedCard = { suit, value, displayName };
    
    // Update UI
    document.querySelectorAll('.hand-area .card').forEach(c => c.classList.remove('selected'));
    event.target.classList.add('selected');
    
    document.getElementById('selected-card-name').textContent = displayName;
    document.getElementById('card-confirm').classList.remove('hidden');
}

function confirmCard() {
    if (!App.selectedCard) return;
    
    SocketClient.playCard(App.selectedCard.suit, App.selectedCard.value);
    App.selectedCard = null;
    document.getElementById('card-confirm').classList.add('hidden');
}

function cancelCard() {
    App.selectedCard = null;
    document.querySelectorAll('.hand-area .card').forEach(c => c.classList.remove('selected'));
    document.getElementById('card-confirm').classList.add('hidden');
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
    showScreen('lobby');
    SocketClient.listRooms();
}

// ==================== Chat Functions ====================
function toggleChat() {
    const chatBody = document.getElementById('chat-body');
    chatBody.classList.toggle('collapsed');
    document.getElementById('chat-badge').classList.add('hidden');
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

function showNotification(message, type = 'info') {
    const container = document.getElementById('notifications');
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 4000);
}

// Export for use in other modules
window.App = App;
window.showScreen = showScreen;
window.showNotification = showNotification;
window.updateRoomsList = updateRoomsList;
window.updateWaitingRoom = updateWaitingRoom;
window.selectCard = selectCard;
window.makeBet = makeBet;
window.joinRoom = joinRoom;
window.kickPlayer = kickPlayer;
window.escapeHtml = escapeHtml;
