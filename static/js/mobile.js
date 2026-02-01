/**
 * Presina - Mobile UI Controller
 * Handles all mobile-specific UI interactions
 */

const MobileUI = {
    
    // State
    currentTab: 'game',
    selectedCard: null,
    unreadChatCount: 0,
    
    // ==================== Initialization ====================
    init() {
        this.setupEventListeners();
        this.checkMobile();
        
        // Listen for window resize
        window.addEventListener('resize', () => this.checkMobile());
        
        // Check if mobile on load
        this.checkMobile();
    },
    
    checkMobile() {
        const isMobile = window.innerWidth <= 768;
        document.body.classList.toggle('is-mobile', isMobile);
        return isMobile;
    },
    
    isMobile() {
        return window.innerWidth <= 768;
    },
    
    setupEventListeners() {
        // Mobile chat input enter key
        const mobileChatInput = document.getElementById('mobile-chat-input');
        if (mobileChatInput) {
            mobileChatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.sendChatMessage();
            });
        }
        
        // Swipe to close sheets
        this.setupSwipeGestures();
        
        // Passive event listeners per scroll fluido su container scrollabili
        // Ottimizza le performance touch senza bloccare il main thread
        const scrollContainers = [
            '.mobile-hand',
            '.mobile-chat-messages',
            '.mobile-players-list',
            '.mobile-sheet-content'
        ];
        
        scrollContainers.forEach(selector => {
            const el = document.querySelector(selector);
            if (el) {
                el.addEventListener('touchstart', () => {}, { passive: true });
                el.addEventListener('touchmove', () => {}, { passive: true });
            }
        });
    },
    
    setupSwipeGestures() {
        let startY = 0;
        let currentY = 0;
        
        const sheets = document.querySelectorAll('.mobile-sheet');
        sheets.forEach(sheet => {
            sheet.addEventListener('touchstart', (e) => {
                startY = e.touches[0].clientY;
            }, { passive: true });
            
            sheet.addEventListener('touchmove', (e) => {
                currentY = e.touches[0].clientY;
                const diff = currentY - startY;
                
                // If scrolling down from top, add resistance
                if (diff > 0 && sheet.scrollTop === 0) {
                    sheet.style.transform = `translateY(${diff * 0.5}px)`;
                }
            }, { passive: true });
            
            sheet.addEventListener('touchend', (e) => {
                const diff = currentY - startY;
                sheet.style.transform = '';
                
                // Close if swiped down more than 100px
                if (diff > 100 && sheet.scrollTop === 0) {
                    this.closeSheets();
                }
            }, { passive: true });
        });
    },
    
    // ==================== Tab Navigation ====================
    switchTab(tab) {
        this.currentTab = tab;
        
        // Update tab buttons
        document.querySelectorAll('.mobile-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        if (tab === 'chat') {
            this.unreadChatCount = 0;
            this.updateChatBadge();
        }
    },
    
    // ==================== Bottom Sheets ====================
    openPlayersSheet() {
        this.closeSheets();
        document.getElementById('mobile-players-sheet-overlay').classList.add('active');
        document.getElementById('mobile-players-sheet').classList.add('active');
        this.switchTab('players');
    },
    
    openChatSheet() {
        this.closeSheets();
        document.getElementById('mobile-chat-sheet-overlay').classList.add('active');
        document.getElementById('mobile-chat-sheet').classList.add('active');
        this.switchTab('chat');
        this.unreadChatCount = 0;
        this.updateChatBadge();
        
        // Scroll to bottom
        const messagesContainer = document.getElementById('mobile-chat-messages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    },
    
    openBettingSheet() {
        this.closeSheets();
        document.getElementById('mobile-betting-sheet-overlay').classList.add('active');
        document.getElementById('mobile-betting-sheet').classList.add('active');
    },
    
    closeSheets() {
        document.querySelectorAll('.mobile-sheet-overlay').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.mobile-sheet').forEach(el => el.classList.remove('active'));
        this.switchTab('game');
    },
    
    // ==================== Menu ====================
    toggleMenu() {
        // Could expand to show game menu with options
        // For now, just a placeholder
        console.log('Menu toggled');
    },
    
    // ==================== Update Game UI (called from GameUI) ====================
    updateGameScreen(gameState) {
        if (!this.isMobile()) return;
        
        this.updateMobileHeader(gameState);
        this.updateMobilePlayerBar(gameState);
        this.updateMobileHand(gameState);
        this.updateMobilePlayersList(gameState);
        this.updateMobileBetting(gameState);
        this.updateMobileSpectatorBanner(gameState);
        this.updateMobileSpecialNote(gameState);
        this.updateMobileTurnResults(gameState);
        this.updateMobileJollyChoice(gameState);
        this.updateMobileQuickActions(gameState);
    },
    
    updateMobileHeader(gameState) {
        // Header is updated by GameUI.updateHeader
        // Just need to ensure phase indicator is correct
    },
    
    updateMobilePlayerBar(gameState) {
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        if (!myPlayer) return;
        
        document.getElementById('mobile-player-name').textContent = myPlayer.name;
        document.getElementById('mobile-player-lives').textContent = myPlayer.lives;
        document.getElementById('mobile-player-bet').textContent = myPlayer.bet !== null ? myPlayer.bet : '-';
        document.getElementById('mobile-player-tricks').textContent = myPlayer.tricks_won || 0;
    },
    
    updateMobileHand(gameState) {
        const handContainer = document.getElementById('mobile-hand');
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        const isMyTurn = gameState.current_player_id === App.playerId && gameState.phase === 'playing';
        const isSpecialTurn = gameState.is_special_turn;
        
        document.getElementById('mobile-cards-count').textContent = 
            myPlayer?.hand?.length ? `${myPlayer.hand.length} carte` : '0 carte';
        
        if (!myPlayer || !myPlayer.hand || myPlayer.hand.length === 0) {
            if (isSpecialTurn) {
                handContainer.innerHTML = '<p class="mobile-empty-state-text">La tua carta è nascosta!</p>';
            } else {
                handContainer.innerHTML = '';
            }
            return;
        }
        
        // Special turn: show card backs
        if (isSpecialTurn) {
            handContainer.innerHTML = myPlayer.hand.map((card, index) => `
                <div class="card card-back ${isMyTurn ? '' : 'disabled'}"
                     onclick="${isMyTurn ? `MobileUI.selectCard('${card.suit}', ${card.value}, 'Carta nascosta')` : ''}"
                     aria-label="Carta nascosta"></div>
            `).join('');
            return;
        }
        
        // Normal turn: show actual cards
        const sortedHand = [...myPlayer.hand].sort((a, b) => a.strength - b.strength);
        
        handContainer.innerHTML = sortedHand.map(card => {
            const isDisabled = !isMyTurn ? 'disabled' : '';
            const clickHandler = isMyTurn ? 
                `onclick="MobileUI.selectCard('${card.suit}', ${card.value}, '${card.display_name}')"` : '';
            
            return `
                <img src="/carte_napoletane/${card.suit}/${card.suit}_${card.value}.jpg" 
                     class="card ${isDisabled}"
                     ${clickHandler}
                     alt="${card.display_name}">
            `;
        }).join('');
    },
    
    updateMobilePlayersList(gameState) {
        const container = document.querySelector('#mobile-players-sheet-content .mobile-players-list');
        if (!container) return;
        
        container.innerHTML = gameState.players.map(player => {
            const isCurrent = player.player_id === gameState.current_player_id || 
                             player.player_id === gameState.current_better_id;
            const isMe = player.player_id === App.playerId;
            const isOffline = !player.is_online;
            const isAway = player.is_away && player.is_online;
            
            let statusText = '';
            if (gameState.phase === 'betting') {
                if (player.bet !== null) {
                    statusText = `Puntato: ${player.bet}`;
                } else if (player.player_id === gameState.current_better_id) {
                    statusText = 'Sta puntando...';
                } else {
                    statusText = 'In attesa...';
                }
            } else {
                statusText = `Puntata: ${player.bet !== null ? player.bet : '-'} | Prese: ${player.tricks_won}`;
            }
            
            const dotClass = isOffline ? 'offline' : (isAway ? 'away' : 'online');
            
            return `
                <div class="mobile-player-item ${isCurrent ? 'current' : ''} ${isMe ? 'me' : ''} ${player.is_spectator ? 'spectator' : ''} ${isOffline ? 'offline' : ''}">
                    <div class="mobile-player-item-dot ${dotClass}"></div>
                    <div class="mobile-player-item-info">
                        <div class="mobile-player-item-name">
                            ${player.name} ${isMe ? '(Tu)' : ''} ${player.is_spectator ? '👁️' : ''}
                        </div>
                        <div class="mobile-player-item-status">${statusText}</div>
                    </div>
                    <div class="mobile-player-item-stats">
                        <div class="mobile-player-item-lives">❤️ ${player.lives}</div>
                    </div>
                </div>
            `;
        }).join('');
    },
    
    updateMobileBetting(gameState) {
        const isMyTurn = gameState.current_better_id === App.playerId;
        const betTabBtn = document.getElementById('mobile-bet-tab-btn');
        
        // Show/hide bet tab button
        if (betTabBtn) {
            betTabBtn.style.display = (gameState.phase === 'betting' && isMyTurn) ? 'flex' : 'none';
        }
        
        // Update bet grid if betting is open
        if (gameState.phase === 'betting') {
            const betGrid = document.getElementById('mobile-bet-grid');
            const forbiddenNote = document.getElementById('mobile-bet-forbidden-note');
            const forbiddenBet = gameState.forbidden_bet;
            
            if (betGrid) {
                betGrid.innerHTML = '';
                for (let i = 0; i <= gameState.cards_this_turn; i++) {
                    const isForbidden = i === forbiddenBet;
                    const btnClass = isForbidden ? 'forbidden' : '';
                    const onclick = isForbidden ? '' : `onclick="MobileUI.makeBet(${i})"`;
                    
                    betGrid.innerHTML += `
                        <button class="mobile-bet-btn ${btnClass}" ${onclick}>${i}</button>
                    `;
                }
            }
            
            if (forbiddenNote) {
                if (forbiddenBet !== null) {
                    forbiddenNote.textContent = `Non puoi puntare ${forbiddenBet}`;
                    forbiddenNote.classList.remove('hidden');
                } else {
                    forbiddenNote.classList.add('hidden');
                }
            }
            
            // Auto-open betting sheet if it's my turn
            if (isMyTurn && !document.getElementById('mobile-betting-sheet').classList.contains('active')) {
                this.openBettingSheet();
            }
        }
    },
    
    updateMobileSpectatorBanner(gameState) {
        const banner = document.getElementById('mobile-spectator-banner');
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        
        if (myPlayer && (myPlayer.is_spectator || myPlayer.join_next_turn)) {
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }
    },
    
    updateMobileSpecialNote(gameState) {
        const note = document.getElementById('mobile-special-note');
        
        if (gameState.is_special_turn) {
            note.classList.remove('hidden');
        } else {
            note.classList.add('hidden');
        }
    },
    
    updateMobileQuickActions(gameState) {
        const container = document.getElementById('mobile-quick-actions');
        const myPlayer = gameState.players.find(p => p.player_id === App.playerId);
        
        if (!myPlayer || myPlayer.is_spectator) {
            container.innerHTML = '';
            return;
        }
        
        let html = '';
        
        // Show betting button during betting phase
        if (gameState.phase === 'betting' && gameState.current_better_id === App.playerId) {
            html += `<button class="mobile-quick-btn primary" onclick="MobileUI.openBettingSheet()">🎯 Punta</button>`;
        }
        
        // Show turn indicator
        if (gameState.current_player_id === App.playerId) {
            html += `<span style="color: var(--primary); font-size: 12px; font-weight: 600;">🎯 Tuo turno!</span>`;
        }
        
        container.innerHTML = html;
    },
    
    updateMobileTurnResults(gameState) {
        const resultsPanel = document.getElementById('mobile-turn-results');
        
        if (gameState.phase !== 'turn_results') {
            resultsPanel.classList.remove('active');
            return;
        }
        
        resultsPanel.classList.add('active');
        
        const content = document.getElementById('mobile-turn-results-content');
        const nextBtn = document.getElementById('mobile-btn-next-turn');
        const readyCount = document.getElementById('mobile-ready-count');
        
        content.innerHTML = gameState.turn_results.map(result => {
            const isCorrect = result.correct;
            const statusClass = isCorrect ? 'correct' : 'wrong';
            const statusText = isCorrect ? '✅ Corretta' : '❌ Sbagliata';
            
            return `
                <div class="mobile-result-card ${statusClass}">
                    <div class="mobile-result-card-header">
                        <span class="mobile-result-card-name">${escapeHtml(result.name)}</span>
                        <span class="mobile-result-card-status ${statusClass}">${statusText}</span>
                    </div>
                    <div class="mobile-result-card-stats">
                        <span>Puntata: ${result.bet}</span>
                        <span>Prese: ${result.tricks_won}</span>
                        <span>Vite: ${result.lives} ${result.life_change !== 0 ? `(${result.life_change > 0 ? '+' : ''}${result.life_change})` : ''}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        // Admin button
        const isAdmin = gameState.admin_id === App.playerId;
        if (isAdmin) {
            nextBtn.classList.remove('hidden');
            nextBtn.disabled = false;
            nextBtn.textContent = 'Prossimo Turno';
            nextBtn.onclick = () => {
                SocketClient.readyNextTurn();
                nextBtn.disabled = true;
                nextBtn.textContent = 'In attesa...';
            };
            readyCount.textContent = 'Sei l\'admin: clicca per proseguire';
        } else {
            nextBtn.classList.add('hidden');
            readyCount.textContent = 'In attesa dell\'admin...';
        }
    },
    
    updateMobileJollyChoice(gameState) {
        const jollyChoice = document.getElementById('mobile-jolly-choice');
        
        if (gameState.waiting_jolly && gameState.pending_jolly_player === App.playerId) {
            jollyChoice.classList.remove('hidden');
        } else {
            jollyChoice.classList.add('hidden');
        }
    },
    
    // ==================== Chat ====================
    updateChatBadge() {
        const badge = document.getElementById('mobile-chat-badge');
        if (this.unreadChatCount > 0) {
            badge.textContent = this.unreadChatCount > 9 ? '9+' : this.unreadChatCount;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    },
    
    addChatMessage(name, message, isOwn = false) {
        const container = document.getElementById('mobile-chat-messages');
        if (!container) return;
        
        const msgDiv = document.createElement('div');
        msgDiv.className = `mobile-chat-message ${isOwn ? 'own' : 'other'}`;
        msgDiv.innerHTML = `
            ${!isOwn ? `<div class="msg-name">${escapeHtml(name)}</div>` : ''}
            <div>${escapeHtml(message)}</div>
        `;
        
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
        
        // Increment badge if chat is not open
        const chatSheet = document.getElementById('mobile-chat-sheet');
        if (!chatSheet.classList.contains('active') && !isOwn) {
            this.unreadChatCount++;
            this.updateChatBadge();
        }
    },
    
    sendChatMessage() {
        const input = document.getElementById('mobile-chat-input');
        const message = input.value.trim();
        if (message) {
            SocketClient.sendMessage(message);
            input.value = '';
        }
    },
    
    // ==================== Card Selection ====================
    selectCard(suit, value, displayName) {
        this.selectedCard = { suit, value, displayName };
        
        const confirm = document.getElementById('mobile-card-confirm');
        const img = document.getElementById('mobile-card-confirm-img');
        
        // If special turn, show card back
        if (displayName === 'Carta nascosta') {
            img.src = '';
            img.className = 'mobile-card-confirm-card card-back';
        } else {
            img.src = `/carte_napoletane/${suit}/${suit}_${value}.jpg`;
            img.className = 'mobile-card-confirm-card';
        }
        
        confirm.classList.remove('hidden');
    },
    
    confirmCard() {
        if (!this.selectedCard) return;
        
        SocketClient.playCard(this.selectedCard.suit, this.selectedCard.value);
        document.getElementById('mobile-card-confirm').classList.add('hidden');
        this.selectedCard = null;
    },
    
    cancelCard() {
        this.selectedCard = null;
        document.getElementById('mobile-card-confirm').classList.add('hidden');
        
        // Remove selection from cards
        document.querySelectorAll('#mobile-hand .card').forEach(c => c.classList.remove('selected'));
    },
    
    // ==================== Betting ====================
    makeBet(bet) {
        SocketClient.makeBet(bet);
        this.closeSheets();
    },
    
    // ==================== Jolly ====================
    chooseJolly(choice) {
        SocketClient.chooseJolly(choice);
        document.getElementById('mobile-jolly-choice').classList.add('hidden');
    },
    
    // ==================== Trick Winner ====================
    showTrickWinner(winnerName, cardName, isWinner = true) {
        const popup = document.getElementById('mobile-trick-popup');
        const title = document.getElementById('mobile-trick-popup-title');
        const card = document.getElementById('mobile-trick-popup-card');
        
        if (isWinner) {
            popup.classList.remove('loser');
            title.textContent = 'Hai vinto la mano!';
            card.textContent = cardName;
        } else {
            popup.classList.add('loser');
            title.textContent = `${winnerName} ha vinto`;
            card.textContent = `con ${cardName}`;
        }
        
        popup.classList.add('active');
        
        setTimeout(() => {
            popup.classList.remove('active');
        }, 3000);
    }
};

// Utility function for HTML escaping (if not already defined)
if (typeof escapeHtml !== 'function') {
    window.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    MobileUI.init();
});

// Export
window.MobileUI = MobileUI;
