/**
 * Presina - Game UI
 * Handles all game screen rendering and updates
 */

const GameUI = {
    
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
        this.updateMessages(gameState);
    },
    
    // ==================== Header ====================
    updateHeader(gameState) {
        document.getElementById('turn-number').textContent = `Turno ${gameState.current_turn + 1}/5`;
        document.getElementById('cards-info').textContent = `${gameState.cards_this_turn} carte`;
        
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
        
        handArea.innerHTML = myPlayer.hand.map(card => {
            const isDisabled = !isMyTurn ? 'disabled' : '';
            const clickHandler = isMyTurn ? 
                `onclick="selectCard('${card.suit}', ${card.value}, '${card.display_name}')"` : '';
            
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
        // Played cards
        const playedCards = document.getElementById('played-cards');
        
        if (gameState.cards_on_table && gameState.cards_on_table.length > 0) {
            playedCards.innerHTML = gameState.cards_on_table.map(([playerId, card]) => {
                const player = gameState.players.find(p => p.player_id === playerId);
                const jollyText = card.jolly_choice ? ` (${card.jolly_choice})` : '';
                
                return `
                    <div class="played-card-wrapper" title="${player?.name}: ${card.display_name}${jollyText}">
                        <img src="/carte_napoletane/${card.suit}/${card.suit}_${card.value}.jpg" 
                             class="card">
                    </div>
                `;
            }).join('');
        } else {
            playedCards.innerHTML = '';
        }
        
        // Player positions around table
        const positions = document.getElementById('table-positions');
        const activePlayers = gameState.players.filter(p => !p.is_spectator);
        
        positions.innerHTML = activePlayers.map((player, index) => {
            const isCurrent = player.player_id === gameState.current_player_id || 
                             player.player_id === gameState.current_better_id;
            const isOffline = !player.is_online;
            const isMe = player.player_id === App.playerId;
            
            let betInfo = '';
            if (player.bet !== null) {
                betInfo = `Puntata: ${player.bet} | Prese: ${player.tricks_won}`;
            } else if (gameState.phase === 'betting') {
                betInfo = player.player_id === gameState.current_better_id ? 'Sta puntando...' : 'In attesa';
            }
            
            return `
                <div class="table-position pos-${index} ${isCurrent ? 'current-turn' : ''} ${isOffline ? 'offline' : ''} ${isMe ? 'is-me' : ''}">
                    <div class="player-name">${isMe ? '👤 ' : ''}${escapeHtml(player.name)}</div>
                    <div class="player-bet">${betInfo}</div>
                </div>
            `;
        }).join('');
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
        
        // Ready count
        const readyPlayers = gameState.players.filter(p => p.ready_for_next_turn && p.is_online && !p.is_spectator);
        const totalOnline = gameState.players.filter(p => p.is_online && !p.is_spectator).length;
        document.getElementById('ready-count').textContent = `Pronti: ${readyPlayers.length}/${totalOnline}`;
        
        // Update button
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        const btn = document.getElementById('btn-next-turn');
        if (myPlayer && myPlayer.ready_for_next_turn) {
            btn.disabled = true;
            btn.textContent = 'In attesa degli altri...';
        } else {
            btn.disabled = false;
            btn.textContent = 'Prossimo Turno';
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
