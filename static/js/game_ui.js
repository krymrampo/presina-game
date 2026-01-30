/**
 * Presina - Game UI
 * Handles all game screen rendering and updates
 */

const GameUI = {
    
    // ==================== Timer Element ====================
    _createTimerElement() {
        const timerEl = document.createElement('span');
        timerEl.id = 'turn-timer';
        timerEl.className = 'turn-timer';
        
        // Insert after phase indicator
        const phaseIndicator = document.getElementById('phase-indicator');
        if (phaseIndicator && phaseIndicator.parentNode) {
            phaseIndicator.parentNode.insertBefore(timerEl, phaseIndicator.nextSibling);
        }
        
        return timerEl;
    },

    // ==================== Main Update ====================
    updateGameScreen(gameState) {
        this.updateHeader(gameState);
        this.updateSpectatorBanner(gameState);
        this.updateHand(gameState);
        this.updateTable(gameState);
        this.updatePlayersPanel(gameState);
        this.updateBettingArea(gameState);
        this.updateJollyChoice(gameState);
        this.updateTurnResults(gameState);
    },
    
    // ==================== Header ====================
    updateHeader(gameState) {
        document.getElementById('turn-number').textContent = `Turno ${gameState.current_turn + 1}/5`;
        document.getElementById('cards-info').textContent = `${gameState.cards_this_turn} carte`;
        
        // Update timer if available
        const timeRemaining = gameState.time_remaining;
        if (timeRemaining !== null && timeRemaining !== undefined) {
            const timerEl = document.getElementById('turn-timer') || this._createTimerElement();
            timerEl.textContent = `⏱️ ${timeRemaining}s`;
            timerEl.className = 'turn-timer' + (timeRemaining < 10 ? ' warning' : '');
        }
        
        const phaseIndicator = document.getElementById('phase-indicator');
        phaseIndicator.className = 'phase-indicator';
        
        switch(gameState.phase) {
            case 'betting':
                phaseIndicator.textContent = '🎯 Puntate';
                phaseIndicator.classList.add('phase-betting');
                break;
            case 'playing':
            case 'waiting_jolly':
                phaseIndicator.textContent = '🃏 Gioco';
                phaseIndicator.classList.add('phase-playing');
                break;
            case 'trick_complete':
                phaseIndicator.textContent = '✨ Mano completata';
                phaseIndicator.classList.add('phase-playing');
                break;
            case 'turn_results':
                phaseIndicator.textContent = '📊 Risultati';
                phaseIndicator.classList.add('phase-results');
                break;
            default:
                phaseIndicator.textContent = gameState.phase;
        }
        
        // Trick info
        document.getElementById('trick-info').textContent = `Mano ${gameState.current_trick + 1}/${gameState.cards_this_turn}`;
    },
    
    // ==================== Spectator Banner ====================
    updateSpectatorBanner(gameState) {
        const banner = document.getElementById('spectator-banner');
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        
        if (myPlayer && (myPlayer.is_spectator || myPlayer.join_next_turn)) {
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }
    },
    
    // ==================== Hand ====================
    updateHand(gameState) {
        const handArea = document.getElementById('player-hand');
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        const isMyTurn = gameState.current_player_id === App.playerId && gameState.phase === 'playing';
        
        // Special turn note
        const specialNote = document.getElementById('special-turn-note');
        const othersCards = document.getElementById('others-cards');
        
        if (gameState.is_special_turn) {
            specialNote.classList.remove('hidden');
            
            // Show other players' cards
            othersCards.classList.remove('hidden');
            othersCards.innerHTML = '<h4>Carte degli altri:</h4>';
            
            gameState.players.forEach(player => {
                if (player.player_id !== App.playerId && player.hand && player.hand.length > 0) {
                    const card = player.hand[0];
                    othersCards.innerHTML += `
                        <div class="other-player-card">
                            <span>${escapeHtml(player.name)}:</span>
                            <img src="/carte_napoletane/${card.suit}/${card.suit}_${card.value}.jpg" 
                                 class="card" style="width: 50px; height: 75px; cursor: default;">
                        </div>
                    `;
                }
            });
        } else {
            specialNote.classList.add('hidden');
            othersCards.classList.add('hidden');
        }
        
        // My cards
        if (!myPlayer || !myPlayer.hand || myPlayer.hand.length === 0) {
            if (gameState.is_special_turn) {
                handArea.innerHTML = '<p class="empty-message">La tua carta è nascosta!</p>';
            } else {
                handArea.innerHTML = '<p class="empty-message">Nessuna carta</p>';
            }
            return;
        }
        
        // Sort cards by strength (value) ascending
        const sortedHand = [...myPlayer.hand].sort((a, b) => a.strength - b.strength);
        
        handArea.innerHTML = sortedHand.map(card => {
            const isDisabled = !isMyTurn ? 'disabled' : '';
            const clickHandler = isMyTurn ? 
                `onclick="selectCard('${card.suit}', ${card.value}, '${card.display_name}', event)"` : '';
            
            return `
                <img src="/carte_napoletane/${card.suit}/${card.suit}_${card.value}.jpg" 
                     class="card ${isDisabled}"
                     ${clickHandler}
                     alt="${card.display_name}"
                     title="${card.display_name}">
            `;
        }).join('');
    },
    
    // ==================== Table ====================
    updateTable(gameState) {
        // Player positions around table - calculate first to map positions
        const positions = document.getElementById('table-positions');
        const activePlayers = gameState.players.filter(p => !p.is_spectator);
        const numPlayers = activePlayers.length;
        
        // Find my index in active players
        const myIndex = activePlayers.findIndex(p => p.player_id === App.playerId);
        
        // Map playerId to position index
        const playerPosMap = {};
        
        // Calculate positions so that I am always at position 0 (bottom center)
        positions.innerHTML = activePlayers.map((player, index) => {
            const isCurrent = player.player_id === gameState.current_player_id || 
                             player.player_id === gameState.current_better_id;
            const isOffline = !player.is_online;
            const isMe = player.player_id === App.playerId;
            
            // Calculate relative position: offset so "me" is at position 0
            let relativePos;
            if (myIndex >= 0) {
                relativePos = (index - myIndex + numPlayers) % numPlayers;
            } else {
                relativePos = index;
            }
            
            // Map to visual positions based on number of players
            const posIndex = this.getTablePosition(relativePos, numPlayers);
            playerPosMap[player.player_id] = posIndex;
            
            let betInfo = '';
            if (player.bet !== null) {
                betInfo = `Puntata: ${player.bet} | Prese: ${player.tricks_won}`;
            } else if (gameState.phase === 'betting') {
                betInfo = player.player_id === gameState.current_better_id ? 'Sta puntando...' : 'In attesa';
            }
            
            return `
                <div class="table-position pos-${posIndex} ${isCurrent ? 'current-turn' : ''} ${isOffline ? 'offline' : ''} ${isMe ? 'is-me' : ''}">
                    <div class="player-name">${isMe ? '👤 ' : ''}${escapeHtml(player.name)}</div>
                    <div class="player-bet">${betInfo}</div>
                </div>
            `;
        }).join('');
        
        // Played cards - positioned in front of each player
        const playedCards = document.getElementById('played-cards');
        
        if (gameState.cards_on_table && gameState.cards_on_table.length > 0) {
            playedCards.innerHTML = gameState.cards_on_table.map(([playerId, card]) => {
                const player = gameState.players.find(p => p.player_id === playerId);
                const posIndex = playerPosMap[playerId] || 0;
                const jollyText = card.jolly_choice ? ` (${card.jolly_choice})` : '';
                
                return `
                    <div class="played-card-position pos-${posIndex}" title="${player?.name}: ${card.display_name}${jollyText}">
                        <img src="/carte_napoletane/${card.suit}/${card.suit}_${card.value}.jpg" 
                             class="card" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">
                    </div>
                `;
            }).join('');
        } else {
            playedCards.innerHTML = '';
        }
    },
    
    // Get the visual table position based on relative position and player count
    getTablePosition(relativePos, numPlayers) {
        // Position mappings for different player counts
        // Position 0 = bottom center (me), then clockwise
        const positionMaps = {
            2: [0, 3],           // bottom, top
            3: [0, 2, 5],        // bottom, top-left, top-right
            4: [0, 1, 3, 6],     // bottom, left, top, right
            5: [0, 1, 3, 4, 6],  // bottom, bottom-left, top-left, top-right, bottom-right
            6: [0, 1, 2, 4, 5, 6], // all except top positions
            7: [0, 1, 2, 3, 4, 5, 6], // all positions
            8: [0, 1, 2, 3, 4, 5, 6, 7] // all + center (shouldn't happen)
        };
        
        const map = positionMaps[numPlayers] || positionMaps[8];
        return map[relativePos] !== undefined ? map[relativePos] : relativePos;
    },
    
    // ==================== Players Panel ====================
    updatePlayersPanel(gameState) {
        const container = document.getElementById('players-info');
        
        container.innerHTML = gameState.players.map(player => {
            const isCurrent = player.player_id === gameState.current_player_id || 
                             player.player_id === gameState.current_better_id;
            const isMe = player.player_id === App.playerId;
            const statusClass = !player.is_online ? 'offline' : '';
            
            return `
                <div class="player-info-card ${isCurrent ? 'current' : ''} ${isMe ? 'me' : ''} ${statusClass}">
                    <div class="name-row">
                        <span>
                            <span class="online-dot ${player.is_online ? 'online' : 'offline'}"></span>
                            ${escapeHtml(player.name)}
                            ${player.is_spectator ? ' 👁️' : ''}
                        </span>
                        <span class="lives-display">❤️ ${player.lives}</span>
                    </div>
                    <div class="stats-row">
                        <span>Puntata: ${player.bet !== null ? player.bet : '-'}</span>
                        <span>Prese: ${player.tricks_won}</span>
                    </div>
                </div>
            `;
        }).join('');
    },
    
    // ==================== Betting Area ====================
    updateBettingArea(gameState) {
        const bettingArea = document.getElementById('betting-area');
        const isMyTurn = gameState.current_better_id === App.playerId;
        
        if (gameState.phase !== 'betting' || !isMyTurn) {
            bettingArea.classList.add('hidden');
            return;
        }
        
        bettingArea.classList.remove('hidden');
        
        const betButtons = document.getElementById('bet-buttons');
        const forbiddenBet = gameState.forbidden_bet;
        
        let buttonsHtml = '';
        for (let i = 0; i <= gameState.cards_this_turn; i++) {
            const isForbidden = i === forbiddenBet;
            const btnClass = isForbidden ? 'btn btn-danger bet-btn btn-forbidden' : 'btn btn-primary bet-btn';
            const disabled = isForbidden ? 'disabled' : '';
            const onclick = isForbidden ? '' : `onclick="makeBet(${i})"`;
            
            buttonsHtml += `<button class="${btnClass}" ${disabled} ${onclick}>${i}</button>`;
        }
        
        betButtons.innerHTML = buttonsHtml;
        
        // Forbidden bet note
        const forbiddenNote = document.getElementById('forbidden-bet-note');
        if (forbiddenBet !== null) {
            forbiddenNote.textContent = `Non puoi puntare ${forbiddenBet} (la somma sarebbe uguale alle carte)`;
            forbiddenNote.classList.remove('hidden');
        } else {
            forbiddenNote.classList.add('hidden');
        }
    },
    
    // ==================== Jolly Choice ====================
    updateJollyChoice(gameState) {
        const jollyChoice = document.getElementById('jolly-choice');
        
        if (gameState.waiting_jolly && gameState.pending_jolly_player === App.playerId) {
            jollyChoice.classList.remove('hidden');
        } else {
            jollyChoice.classList.add('hidden');
        }
    },
    
    // ==================== Trick Winner Popup ====================
    showTrickWinner(winnerName, cardName) {
        const overlay = document.getElementById('trick-winner-overlay');
        const popup = document.getElementById('trick-winner-popup');
        const nameEl = document.getElementById('trick-winner-name');
        const cardEl = document.getElementById('trick-winner-card');
        
        nameEl.textContent = winnerName;
        cardEl.textContent = `con ${cardName}`;
        
        overlay.classList.remove('hidden');
        popup.classList.remove('hidden');
        
        // Auto hide after 3 seconds
        setTimeout(() => {
            overlay.classList.add('hidden');
            popup.classList.add('hidden');
        }, 3000);
    },
    
    // ==================== Turn Results ====================
    updateTurnResults(gameState) {
        const resultsArea = document.getElementById('turn-results');
        
        if (gameState.phase !== 'turn_results') {
            resultsArea.classList.add('hidden');
            return;
        }
        
        resultsArea.classList.remove('hidden');
        
        const resultsList = document.getElementById('results-list');
        resultsList.innerHTML = gameState.turn_results.map(result => {
            const correctClass = result.correct ? 'correct' : 'wrong';
            const lifeChange = result.life_change === 0 ? '✓' : `${result.life_change}`;
            const lifeIcon = result.correct ? '✅' : '❌';
            
            return `
                <div class="result-item ${correctClass}">
                    <span class="result-name">${escapeHtml(result.name)}</span>
                    <span class="result-stats">Puntata: ${result.bet} | Prese: ${result.tricks_won}</span>
                    <span class="result-lives">${lifeIcon} ❤️${result.lives}</span>
                </div>
            `;
        }).join('');
        
        // Only show button for admin
        const isAdmin = gameState.admin_id === App.playerId;
        const btn = document.getElementById('btn-next-turn');
        const readyCount = document.getElementById('ready-count');
        
        if (isAdmin) {
            btn.classList.remove('hidden');
            btn.disabled = false;
            btn.textContent = 'Prossimo Turno';
            readyCount.textContent = 'Sei l\'admin: clicca per proseguire';
        } else {
            btn.classList.add('hidden');
            readyCount.textContent = 'In attesa dell\'admin...';
        }
    },
    
    // ==================== Messages ====================
    updateMessages(gameState) {
        const messagesList = document.getElementById('messages-list');
        
        if (!gameState.messages || gameState.messages.length === 0) {
            messagesList.innerHTML = '';
            return;
        }
        
        // Show only last 10 messages
        const recentMessages = gameState.messages.slice(-10);
        
        messagesList.innerHTML = recentMessages.map(msg => `
            <div class="game-message ${msg.type}">
                ${escapeHtml(msg.content)}
            </div>
        `).join('');
        
        // Scroll to bottom
        messagesList.scrollTop = messagesList.scrollHeight;
    },
    
    // ==================== Game Over ====================
    updateGameOver(gameState) {
        const standings = document.getElementById('final-standings');
        
        if (!gameState.game_results || gameState.game_results.length === 0) {
            standings.innerHTML = '<p>Nessun risultato</p>';
            return;
        }
        
        standings.innerHTML = gameState.game_results.map((result, index) => {
            const positionEmoji = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `${index + 1}.`;
            const isFirst = index === 0 ? 'first' : '';
            
            return `
                <div class="standing-item ${isFirst}">
                    <span class="standing-position">${positionEmoji}</span>
                    <span class="standing-name">${escapeHtml(result.name)}</span>
                    <span class="standing-lives">❤️ ${result.lives}</span>
                </div>
            `;
        }).join('');
    }
};

// Export
window.GameUI = GameUI;
