/**
 * Presina - Game UI
 * Handles all game screen rendering and updates
 */

const GameUI = {
    
    // Cache for previous state to avoid unnecessary re-renders
    _previousHand: null,
    _previousTableCards: null,

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
        
        // Trick info (now in header)
        const trickInfoEl = document.getElementById('trick-info');
        if (trickInfoEl) {
            trickInfoEl.textContent = `Mano ${gameState.current_trick + 1}/${gameState.cards_this_turn}`;
        }
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
            this._previousHand = null;
            return;
        }
        
        // Sort cards by strength (value) ascending
        const sortedHand = [...myPlayer.hand].sort((a, b) => a.strength - b.strength);
        
        // Check if hand changed to avoid unnecessary re-render
        const handKey = sortedHand.map(c => `${c.suit}-${c.value}`).join(',');
        const turnKey = `${gameState.current_turn}-${gameState.current_trick}-${isMyTurn}`;
        const currentKey = `${handKey}|${turnKey}`;
        
        // Don't re-render if card selection popup is open
        const cardConfirm = document.getElementById('card-confirm');
        if (cardConfirm && !cardConfirm.classList.contains('hidden')) {
            return;
        }
        
        if (this._previousHand === currentKey) {
            // Only update disabled state without re-rendering
            const cards = handArea.querySelectorAll('.card');
            cards.forEach(card => {
                if (isMyTurn) {
                    card.classList.remove('disabled');
                } else {
                    card.classList.add('disabled');
                }
            });
            return;
        }
        
        this._previousHand = currentKey;
        
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
        const me = gameState.players.find(p => p.player_id === App.playerId);
        const isSpectator = me && me.is_spectator;
        
        // If I'm a spectator, show all players including me in a special way
        // If I'm playing, only show active players
        const activePlayers = gameState.players.filter(p => !p.is_spectator || p.player_id === App.playerId);
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
            if (player.is_spectator) {
                betInfo = '👁️ Spettatore';
            } else if (gameState.phase === 'betting') {
                // During betting phase
                if (player.bet !== null) {
                    betInfo = `✓ Puntato: <strong>${player.bet}</strong>`;
                } else if (player.player_id === gameState.current_better_id) {
                    betInfo = '🎯 <em>Sta puntando...</em>';
                } else {
                    betInfo = '⏳ In attesa...';
                }
            } else {
                // During playing phase - show bet vs tricks with progress indicator
                if (player.bet !== null) {
                    const diff = player.tricks_won - player.bet;
                    let statusIcon = '';
                    if (diff < 0) statusIcon = '🔸'; // Still needs tricks
                    else if (diff === 0) statusIcon = '✅'; // On target
                    else statusIcon = '⚠️'; // Exceeded
                    
                    betInfo = `${statusIcon} Puntata: <strong>${player.bet}</strong> | Prese: <strong>${player.tricks_won}</strong>`;
                }
            }
            
            const spectatorBadge = player.is_spectator ? ' 👁️' : '';
            
            return `
                <div class="table-position pos-${posIndex} ${isCurrent ? 'current-turn current-turn-pulse' : ''} ${isOffline ? 'offline' : ''} ${isMe ? 'is-me' : ''} ${player.is_spectator ? 'spectator' : ''}">
                    <div class="player-name">${isMe ? '👤 ' : ''}${escapeHtml(player.name)}${spectatorBadge}</div>
                    <div class="player-bet">${betInfo}</div>
                </div>
            `;
        }).join('');
        
        // Played cards - positioned in front of each player
        const playedCards = document.getElementById('played-cards');
        
        if (gameState.cards_on_table && gameState.cards_on_table.length > 0) {
            // Check if cards changed to avoid unnecessary re-render
            const tableKey = gameState.cards_on_table.map(([pid, c]) => `${pid}-${c.suit}-${c.value}`).join(',');
            
            if (this._previousTableCards !== tableKey) {
                this._previousTableCards = tableKey;
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
            }
        } else {
            playedCards.innerHTML = '';
            this._previousTableCards = null;
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
            
            // Determine status color based on bet vs tricks won
            let statusColorClass = '';
            if (player.bet !== null && gameState.phase !== 'betting') {
                if (player.tricks_won < player.bet) {
                    statusColorClass = 'status-pending'; // Orange: still needs tricks
                } else if (player.tricks_won === player.bet) {
                    statusColorClass = 'status-achieved'; // Green: achieved bet
                } else {
                    statusColorClass = 'status-exceeded'; // Red: exceeded bet
                }
            }
            
            return `
                <div class="player-info-card ${isCurrent ? 'current' : ''} ${isMe ? 'me' : ''} ${statusClass} ${statusColorClass}">
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
        const betsSummary = document.getElementById('bets-summary');
        const tableBetsOverlay = document.getElementById('table-bets-overlay');
        const isMyTurn = gameState.current_better_id === App.playerId;
        
        // Handle betting area (in left panel) - only when it's my turn
        if (gameState.phase !== 'betting' || !isMyTurn) {
            bettingArea.classList.add('hidden');
        } else {
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
        }
        
        // Show bets summary in left panel during betting phase
        if (gameState.phase === 'betting') {
            betsSummary.classList.remove('hidden');
            this._updateBetsSummary(gameState);
            
            // Show table overlay with all bets
            tableBetsOverlay.classList.remove('hidden');
            this._updateTableBetsOverlay(gameState);
        } else {
            betsSummary.classList.add('hidden');
            tableBetsOverlay.classList.add('hidden');
        }
    },
    
    // Update bets summary in left panel
    _updateBetsSummary(gameState) {
        const betsList = document.getElementById('bets-list');
        if (!betsList) return;
        
        const activePlayers = gameState.players.filter(p => !p.is_spectator && !p.is_eliminated);
        
        betsList.innerHTML = activePlayers.map(player => {
            const hasBet = player.bet !== null && player.bet !== undefined;
            const isCurrent = player.player_id === gameState.current_better_id;
            const betClass = isCurrent ? 'betting' : '';
            const betDisplay = hasBet ? player.bet : (isCurrent ? '...' : '-');
            
            return `
                <div class="bet-item ${betClass}">
                    <span class="bet-name">${escapeHtml(player.name)}</span>
                    <span class="bet-value">${betDisplay}</span>
                </div>
            `;
        }).join('');
    },
    
    // Update table bets overlay
    _updateTableBetsOverlay(gameState) {
        const tableBetsList = document.getElementById('table-bets-list');
        if (!tableBetsList) return;
        
        const activePlayers = gameState.players.filter(p => !p.is_spectator && !p.is_eliminated);
        const totalBets = activePlayers.reduce((sum, p) => sum + (p.bet !== null ? p.bet : 0), 0);
        
        tableBetsList.innerHTML = activePlayers.map(player => {
            const hasBet = player.bet !== null && player.bet !== undefined;
            const isCurrent = player.player_id === gameState.current_better_id;
            const currentClass = isCurrent ? 'current' : '';
            
            let statusText = '';
            if (hasBet) {
                statusText = `<span class="tb-value">${player.bet}</span>`;
            } else if (isCurrent) {
                statusText = '<span class="tb-status">sta puntando...</span>';
            } else {
                statusText = '<span class="tb-status">in attesa</span>';
            }
            
            return `
                <div class="table-bet-item ${currentClass}">
                    <span class="tb-name">${escapeHtml(player.name)}</span>
                    ${statusText}
                </div>
            `;
        }).join('') + `
            <div class="table-bet-item" style="margin-top: 12px; border-top: 1px solid var(--border-color); padding-top: 12px;">
                <span class="tb-name">TOTALE</span>
                <span class="tb-value">${totalBets} / ${gameState.cards_this_turn}</span>
            </div>
        `;
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
    showTrickWinner(winnerName, cardName, isWinner = true) {
        const overlay = document.getElementById('trick-winner-overlay');
        const popup = document.getElementById('trick-winner-popup');
        const titleEl = popup.querySelector('h3');
        const nameEl = document.getElementById('trick-winner-name');
        const cardEl = document.getElementById('trick-winner-card');
        
        if (isWinner) {
            // Io ho vinto
            titleEl.textContent = `Hai vinto la mano col ${cardName}`;
            nameEl.style.display = 'none';
            cardEl.style.display = 'none';
            popup.classList.remove('loser');
            popup.classList.add('animate-bounce');
        } else {
            // Ha vinto un altro
            titleEl.textContent = `${winnerName} ha vinto la mano`;
            nameEl.style.display = 'none';
            cardEl.textContent = `con ${cardName}`;
            cardEl.style.display = 'block';
            popup.classList.add('loser');
            popup.classList.remove('animate-bounce');
        }
        
        overlay.classList.remove('hidden');
        popup.classList.remove('hidden');
        
        // Highlight winning card with glow animation
        setTimeout(() => {
            const winningCards = document.querySelectorAll('.played-card-position');
            winningCards.forEach(cardEl => {
                // Add glow to all cards on table (the winner will be obvious from popup)
                cardEl.classList.add('animate-glow');
            });
        }, 100);
        
        // Auto hide after 3 seconds
        setTimeout(() => {
            overlay.classList.add('hidden');
            popup.classList.add('hidden');
            // Reset display properties
            nameEl.style.display = '';
            cardEl.style.display = '';
            // Remove glow from cards
            const winningCards = document.querySelectorAll('.played-card-position');
            winningCards.forEach(cardEl => {
                cardEl.classList.remove('animate-glow');
            });
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
            const rowClass = result.correct ? 'correct' : 'wrong';
            const lifeDelta = result.life_change === 0 ? '±0' : `${result.life_change}`;
            const outcomeText = result.correct ? '✅ Corretta' : '❌ Sbagliata';
            
            return `
                <tr class="result-row ${rowClass}">
                    <td class="col-name">${escapeHtml(result.name)}</td>
                    <td class="col-bet">${result.bet}</td>
                    <td class="col-won">${result.tricks_won}</td>
                    <td class="col-result">${outcomeText}</td>
                    <td class="col-lives">❤️ ${result.lives} <span class="life-delta ${rowClass}">${lifeDelta}</span></td>
                </tr>
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
