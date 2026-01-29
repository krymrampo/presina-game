/**
 * Presina - Socket.IO Client
 * Handles all socket communication with the server
 */

const SocketClient = {
    socket: null,
    connected: false,
    
    // ==================== Connection ====================
    connect() {
        if (this.socket && this.connected) return;
        
        this.socket = io({
            transports: ['polling'],
            upgrade: false
        });
        
        this.setupEventHandlers();
    },
    
    setupEventHandlers() {
        const socket = this.socket;
        
        // Connection events
        socket.on('connect', () => {
            console.log('Connected to server');
            this.connected = true;
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.connected = false;
            showNotification('Connessione persa. Riconnessione...', 'error');
        });
        
        socket.on('error', (data) => {
            console.error('Socket error:', data);
            showNotification(data.message || 'Errore', 'error');
        });
        
        // Registration
        socket.on('registered', (data) => {
            console.log('Registered as:', data);
        });
        
        // Lobby events
        socket.on('rooms_list', (data) => {
            updateRoomsList(data.rooms);
        });
        
        socket.on('room_created', (data) => {
            App.currentRoom = data.room;
            App.gameState = data.game_state;
            showScreen('waiting-room');
            updateWaitingRoom(data.game_state);
            showNotification('Stanza creata!', 'success');
        });
        
        socket.on('room_joined', (data) => {
            App.currentRoom = data.room;
            App.gameState = data.game_state;
            
            if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
            } else {
                showScreen('game');
                GameUI.updateGameScreen(data.game_state);
            }
            showNotification(data.message, 'success');
        });
        
        socket.on('player_joined', (data) => {
            if (App.currentScreen === 'waiting-room') {
                updateWaitingRoom(data.game_state);
            }
            showNotification(`${data.player_name} è entrato`, 'info');
        });
        
        socket.on('player_left', (data) => {
            if (App.currentScreen === 'waiting-room') {
                updateWaitingRoom(data.game_state);
            }
        });
        
        socket.on('player_kicked', (data) => {
            if (App.currentScreen === 'waiting-room') {
                updateWaitingRoom(data.game_state);
            }
        });
        
        socket.on('kicked', (data) => {
            showNotification(data.message, 'error');
            App.currentRoom = null;
            showScreen('lobby');
            this.listRooms();
        });
        
        socket.on('left_room', (data) => {
            App.currentRoom = null;
        });
        
        socket.on('player_disconnected', (data) => {
            // Player went offline
        });
        
        socket.on('player_reconnected', (data) => {
            showNotification('Un giocatore si è riconnesso', 'info');
        });
        
        // Rejoin events
        socket.on('rejoin_success', (data) => {
            App.currentRoom = data.room;
            App.gameState = data.game_state;
            
            if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
            } else {
                showScreen('game');
                GameUI.updateGameScreen(data.game_state);
            }
            showNotification('Riconnesso alla partita!', 'success');
        });
        
        socket.on('rejoin_failed', (data) => {
            showNotification(data.message, 'error');
            document.getElementById('existing-room-banner').classList.add('hidden');
        });
        
        // Game events
        socket.on('game_started', (data) => {
            App.gameState = data.game_state;
            showScreen('game');
            GameUI.updateGameScreen(data.game_state);
            showNotification('La partita è iniziata!', 'success');
        });
        
        socket.on('game_state', (data) => {
            App.gameState = data.game_state;
            
            if (data.game_state.phase === 'game_over') {
                showScreen('game-over');
                GameUI.updateGameOver(data.game_state);
            } else if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
            } else {
                if (App.currentScreen !== 'game') {
                    showScreen('game');
                }
                GameUI.updateGameScreen(data.game_state);
                // Clear card selection after successful state update
                if (typeof clearCardSelection === 'function') {
                    clearCardSelection();
                }
            }
        });
        
        socket.on('jolly_choice_required', (data) => {
            document.getElementById('jolly-choice').classList.remove('hidden');
        });
        
        // Chat events
        socket.on('chat_message', (data) => {
            Chat.addMessage(data);
        });
        
        socket.on('chat_history', (data) => {
            Chat.loadHistory(data.messages);
        });
    },
    
    // ==================== Player Actions ====================
    registerPlayer() {
        this.socket.emit('register_player', {
            player_id: App.playerId,
            name: App.playerName
        });
    },
    
    // ==================== Lobby Actions ====================
    listRooms() {
        this.socket.emit('list_rooms');
    },
    
    searchRooms(query) {
        this.socket.emit('search_rooms', { query });
    },
    
    createRoom(roomName) {
        this.socket.emit('create_room', {
            player_id: App.playerId,
            player_name: App.playerName,
            room_name: roomName
        });
    },
    
    joinRoom(roomId) {
        this.socket.emit('join_room', {
            player_id: App.playerId,
            player_name: App.playerName,
            room_id: roomId
        });
    },
    
    leaveRoom() {
        this.socket.emit('leave_room', {
            player_id: App.playerId
        });
    },
    
    kickPlayer(playerId) {
        this.socket.emit('kick_player', {
            admin_id: App.playerId,
            player_id: playerId
        });
    },
    
    rejoinGame() {
        this.socket.emit('rejoin_game', {
            player_id: App.playerId
        });
    },
    
    // ==================== Game Actions ====================
    startGame() {
        this.socket.emit('start_game', {
            player_id: App.playerId
        });
    },
    
    makeBet(bet) {
        this.socket.emit('make_bet', {
            player_id: App.playerId,
            bet: bet
        });
    },
    
    playCard(suit, value, jollyChoice = null) {
        this.socket.emit('play_card', {
            player_id: App.playerId,
            suit: suit,
            value: value,
            jolly_choice: jollyChoice
        });
    },
    
    chooseJolly(choice) {
        this.socket.emit('choose_jolly', {
            player_id: App.playerId,
            choice: choice
        });
    },
    
    readyNextTurn() {
        this.socket.emit('ready_next_turn', {
            player_id: App.playerId
        });
    },
    
    getGameState() {
        this.socket.emit('get_game_state', {
            player_id: App.playerId
        });
    },
    
    // ==================== Chat Actions ====================
    sendMessage(message) {
        this.socket.emit('send_message', {
            player_id: App.playerId,
            message: message
        });
    },
    
    getChatHistory() {
        this.socket.emit('get_chat_history', {
            player_id: App.playerId
        });
    }
};

// Export
window.SocketClient = SocketClient;
