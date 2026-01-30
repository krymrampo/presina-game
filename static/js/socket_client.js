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
        });
        
        socket.on('error', (data) => {
            console.error('Socket error:', data);
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
        });
        
        socket.on('player_joined', (data) => {
            if (App.currentScreen === 'waiting-room') {
                updateWaitingRoom(data.game_state);
            }
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
            // Player reconnected - UI updates via game_state
        });
        
        // Timer sync - request game state periodically to check for timeouts
        setInterval(() => {
            if (App.currentScreen === 'game' && App.currentRoom && App.gameState) {
                // Only request state if game is in active phase
                const phase = App.gameState.phase;
                if (phase === 'betting' || phase === 'playing' || phase === 'waiting_jolly') {
                    SocketClient.getGameState();
                }
            }
        }, 5000);  // Check every 5 seconds
        
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
        });
        
        socket.on('rejoin_failed', (data) => {
            document.getElementById('existing-room-banner').classList.add('hidden');
        });
        
        // Game events
        socket.on('game_started', (data) => {
            App.gameState = data.game_state;
            showScreen('game');
            GameUI.updateGameScreen(data.game_state);
        });
        
        socket.on('game_state', (data) => {
            App.gameState = data.game_state;
            
            if (data.game_state.phase === 'game_over') {
                showScreen('game-over');
                GameUI.updateGameOver(data.game_state);
            } else if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
            } else if (data.game_state.phase === 'trick_complete') {
                // Trick just completed - show cards for 3 seconds then advance
                if (App.currentScreen !== 'game') {
                    showScreen('game');
                }
                GameUI.updateGameScreen(data.game_state);
                // Clear card selection
                if (typeof clearCardSelection === 'function') {
                    clearCardSelection();
                }
                // After 3 seconds, advance (only one client needs to trigger this)
                if (!App.trickAdvanceScheduled) {
                    App.trickAdvanceScheduled = true;
                    setTimeout(() => {
                        App.trickAdvanceScheduled = false;
                        SocketClient.advanceTrick();
                    }, 3000);
                }
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
            // Clear card selection popup before showing jolly choice
            if (typeof clearCardSelection === 'function') {
                clearCardSelection();
            }
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

    addDummyPlayer() {
        this.socket.emit('add_dummy_player', {
            admin_id: App.playerId
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
    
    advanceTrick() {
        this.socket.emit('advance_trick', {
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
