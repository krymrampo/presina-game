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
            
            // Try to rejoin if we were in a game
            if (App.playerId && App.currentRoom) {
                console.log('Attempting to rejoin game...');
                setTimeout(() => {
                    this.rejoinGame();
                }, 500);  // Small delay to ensure socket is ready
            }
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.connected = false;
        });
        
        socket.on('error', (data) => {
            console.error('Socket error:', data);
            
            // Shake animation on card confirm popup if visible
            const cardConfirm = document.getElementById('card-confirm');
            if (cardConfirm && !cardConfirm.classList.contains('hidden')) {
                cardConfirm.classList.add('animate-shake');
                setTimeout(() => cardConfirm.classList.remove('animate-shake'), 500);
            }
            
            // If we were trying to play a card and got an error, re-enable the confirm button
            if (App.selectedCard) {
                const confirmBtn = document.getElementById('btn-confirm-card');
                if (confirmBtn && cardConfirm && !cardConfirm.classList.contains('hidden')) {
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = '✓ Gioca';
                }
            }
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
            // Save room to sessionStorage for rejoin after refresh
            sessionStorage.setItem('presina_room', JSON.stringify(data.room));
            // Hide rejoin banner if visible
            const banner = document.getElementById('existing-room-banner');
            if (banner) banner.classList.add('hidden');
            showScreen('waiting-room');
            updateWaitingRoom(data.game_state);
        });
        
        socket.on('join_error', (data) => {
            // Handle join errors (e.g., wrong access code)
            // Shake the private join modal if visible
            const joinModal = document.getElementById('join-private-modal');
            const modalContent = joinModal?.querySelector('.modal-content');
            if (modalContent && joinModal && !joinModal.classList.contains('hidden')) {
                modalContent.classList.add('animate-shake');
                setTimeout(() => modalContent.classList.remove('animate-shake'), 500);
            }
            alert(data.message || 'Errore durante l\'accesso alla stanza');
        });
        
        socket.on('room_joined', (data) => {
            App.currentRoom = data.room;
            App.gameState = data.game_state;
            // Save room to sessionStorage for rejoin after refresh
            sessionStorage.setItem('presina_room', JSON.stringify(data.room));
            // Hide rejoin banner if visible
            const banner = document.getElementById('existing-room-banner');
            if (banner) banner.classList.add('hidden');
            
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
            sessionStorage.removeItem('presina_room');
            showScreen('lobby');
            this.listRooms();
        });
        
        socket.on('left_room', (data) => {
            App.currentRoom = null;
            sessionStorage.removeItem('presina_room');
        });
        
        socket.on('player_disconnected', (data) => {
            // Player went offline
        });
        
        socket.on('player_reconnected', (data) => {
            // Player reconnected - UI updates via game_state
        });
        
        // Timer sync - request game state periodically to sync with server
        setInterval(() => {
            if (App.currentScreen === 'game' && App.currentRoom && App.gameState) {
                // Only request state if game is in active phase
                const phase = App.gameState.phase;
                if (phase === 'betting' || phase === 'playing' || phase === 'waiting_jolly') {
                    SocketClient.getGameState();
                }
            }
        }, 1000);  // Sync every 1 second for smoother updates
        
        // Rejoin events
        socket.on('rejoin_success', (data) => {
            App.currentRoom = data.room;
            App.gameState = data.game_state;
            // Update saved room info
            sessionStorage.setItem('presina_room', JSON.stringify(data.room));
            // Hide rejoin banner if visible
            const banner = document.getElementById('existing-room-banner');
            if (banner) banner.classList.add('hidden');
            
            if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
            } else {
                showScreen('game');
                GameUI.updateGameScreen(data.game_state);
            }
        });
        
        socket.on('rejoin_failed', (data) => {
            const banner = document.getElementById('existing-room-banner');
            if (banner) banner.classList.add('hidden');
            // Clear saved room as it's no longer valid
            App.currentRoom = null;
            sessionStorage.removeItem('presina_room');
            alert('Non è stato possibile rientrare nella partita: ' + (data.message || 'Stanza non disponibile'));
        });
        
        // Game events
        socket.on('game_started', (data) => {
            App.gameState = data.game_state;
            showScreen('game');
            GameUI.updateGameScreen(data.game_state);
        });
        
        socket.on('game_state', (data) => {
            // Save previous state before updating (needed for card play detection)
            const previousPlayerId = App.gameState?.current_player_id;
            const previousPlayer = App.gameState?.players?.find(p => p.player_id === App.playerId);
            const previousHandSize = previousPlayer?.hand?.length || 0;
            
            App.gameState = data.game_state;
            
            if (data.game_state.phase === 'game_over') {
                showScreen('game-over');
                GameUI.updateGameOver(data.game_state);
                clearCardSelection();
            } else if (data.game_state.phase === 'waiting') {
                showScreen('waiting-room');
                updateWaitingRoom(data.game_state);
                clearCardSelection();
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
                // Show trick winner popup
                if (data.game_state.trick_winner) {
                    const isCurrentPlayerWinner = data.game_state.trick_winner.player_id === App.playerId;
                    GameUI.showTrickWinner(
                        data.game_state.trick_winner.player_name,
                        data.game_state.trick_winner.card?.display_name || '',
                        isCurrentPlayerWinner
                    );
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
                
                // Check if we should clear card selection BEFORE updating UI
                // Only clear if: a card was played (hand size decreased) or turn changed to another player
                if (App.selectedCard && typeof clearCardSelection === 'function') {
                    const myPlayer = data.game_state.players?.find(p => p.player_id === App.playerId);
                    const currentHandSize = myPlayer?.hand?.length || 0;
                    
                    const cardWasPlayed = currentHandSize < previousHandSize;
                    const isMyTurn = data.game_state.current_player_id === App.playerId;
                    const turnChanged = previousPlayerId === App.playerId && !isMyTurn;
                    
                    // Only close the popup if the card was actually played or turn changed
                    if (cardWasPlayed || turnChanged) {
                        clearCardSelection();
                    }
                }
                
                GameUI.updateGameScreen(data.game_state);
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
    
    createRoom(roomName, isPublic = true, accessCode = null) {
        this.socket.emit('create_room', {
            player_id: App.playerId,
            player_name: App.playerName,
            room_name: roomName,
            is_public: isPublic,
            access_code: accessCode
        });
    },
    
    joinRoom(roomId, accessCode = null) {
        this.socket.emit('join_room', {
            player_id: App.playerId,
            player_name: App.playerName,
            room_id: roomId,
            access_code: accessCode
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
