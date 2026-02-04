/**
 * Presina - Authentication & User Management
 */

const AuthUI = {
    
    currentUser: null,
    authToken: null,
    
    // ==================== Initialization ====================
    init() {
        // Check for saved session
        const savedToken = localStorage.getItem('presina_auth_token');
        const savedUser = localStorage.getItem('presina_user');
        
        if (savedToken && savedUser) {
            this.authToken = savedToken;
            try {
                this.currentUser = JSON.parse(savedUser);
                if (this.currentUser) {
                    this.currentUser.avatar = this.normalizeAvatar(this.currentUser.avatar);
                }
            } catch (e) {
                localStorage.removeItem('presina_auth_token');
                localStorage.removeItem('presina_user');
                this.authToken = null;
                this.currentUser = null;
            }
            if (this.authToken) {
                this.validateSession();
            }
        }
        this.bindEvents();
        this.updateUI();
    },
    
    async validateSession() {
        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${this.authToken}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentUser = data.user;
                this.currentUser.avatar = this.normalizeAvatar(this.currentUser.avatar);
                localStorage.setItem('presina_user', JSON.stringify(this.currentUser));
                if (data.user?.is_guest) {
                    localStorage.setItem('presina_is_guest', 'true');
                } else {
                    localStorage.removeItem('presina_is_guest');
                }
                this.updateUI();
            } else {
                this.logout();
            }
        } catch (error) {
            console.error('Session validation error:', error);
        }
    },
    
    // ==================== UI Updates ====================
    updateUI() {
        const notLoggedSection = document.getElementById('home-not-logged');
        const loggedSection = document.getElementById('home-logged');
        const profileBtn = document.getElementById('btn-profile');
        
        if (this.currentUser) {
            // Show logged in UI
            notLoggedSection.classList.add('hidden');
            loggedSection.classList.remove('hidden');
            
            // Update user info
            const displayNameEl = document.getElementById('user-display-name');
            if (displayNameEl) {
                displayNameEl.textContent = `Ciao, ${this.currentUser.display_name || this.currentUser.username}!`;
            }
            const usernameEl = document.getElementById('user-username');
            if (usernameEl) {
                usernameEl.textContent = `@${this.currentUser.username}`;
            }
            
            // Update avatar
            const homeImg = document.getElementById('user-avatar-img');
            if (homeImg) {
                homeImg.src = this.normalizeAvatar(this.currentUser.avatar);
            }
            
            // Set player name for game
            App.playerName = this.currentUser.display_name || this.currentUser.username;
            sessionStorage.setItem('presina_player_name', App.playerName);
            const playerNameInput = document.getElementById('player-name');
            if (playerNameInput) {
                playerNameInput.value = App.playerName;
                playerNameInput.disabled = true;
            }
            
            if (profileBtn) {
                profileBtn.classList.toggle('hidden', this.isGuest());
            }
            
            if (!this.isGuest()) {
                this.loadUserStats();
            }
            
        } else {
            // Show not logged in UI
            notLoggedSection.classList.remove('hidden');
            loggedSection.classList.add('hidden');
            if (profileBtn) profileBtn.classList.add('hidden');
            const playerNameInput = document.getElementById('player-name');
            if (playerNameInput) playerNameInput.disabled = false;
        }
    },
    
    switchTab(tab) {
        // Update tab buttons
        document.querySelectorAll('.auth-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        // Update forms
        document.getElementById('login-form').classList.toggle('active', tab === 'login');
        document.getElementById('register-form').classList.toggle('active', tab === 'register');
    },
    
    // ==================== Authentication Actions ====================
    async login() {
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        
        if (!username || !password) {
            this.showError('Inserisci username e password');
            return;
        }
        
        this.setLoading('btn-login', true);
        
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.authToken = data.token;
                this.currentUser = data.user;
                this.currentUser.avatar = this.normalizeAvatar(this.currentUser.avatar);
                
                localStorage.setItem('presina_auth_token', this.authToken);
                localStorage.setItem('presina_user', JSON.stringify(this.currentUser));
                localStorage.removeItem('presina_is_guest');
                
                this.updateUI();
                this.showSuccess('Accesso effettuato!');
            } else {
                this.showError(data.error || 'Errore di accesso');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Errore di connessione');
        } finally {
            this.setLoading('btn-login', false);
        }
    },
    
    async register() {
        const username = document.getElementById('register-username').value.trim();
        const password = document.getElementById('register-password').value;
        const displayName = document.getElementById('register-display-name').value.trim();
        
        if (!username || !password) {
            this.showError('Username e password sono obbligatori');
            return;
        }
        
        if (username.length < 3) {
            this.showError('Username troppo corto (min 3 caratteri)');
            return;
        }
        
        if (password.length < 4) {
            this.showError('Password troppo corta (min 4 caratteri)');
            return;
        }
        
        this.setLoading('btn-register', true);
        
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username, 
                    password, 
                    display_name: displayName 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess('Account creato! Ora puoi accedere');
                this.switchTab('login');
                
                // Pre-fill login
                document.getElementById('login-username').value = username;
                document.getElementById('register-username').value = '';
                document.getElementById('register-password').value = '';
                document.getElementById('register-display-name').value = '';
            } else {
                this.showError(data.error || 'Errore registrazione');
            }
        } catch (error) {
            console.error('Register error:', error);
            this.showError('Errore di connessione');
        } finally {
            this.setLoading('btn-register', false);
        }
    },
    
    async guestLogin() {
        this.setLoading('btn-guest', true);
        
        try {
            const guestName = document.getElementById('player-name')?.value?.trim();
            const response = await fetch('/api/auth/guest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name: guestName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.authToken = data.token;
                this.currentUser = data.user;
                this.currentUser.avatar = this.normalizeAvatar(this.currentUser.avatar);
                
                localStorage.setItem('presina_auth_token', this.authToken);
                localStorage.setItem('presina_user', JSON.stringify(this.currentUser));
                localStorage.setItem('presina_is_guest', 'true');
                
                this.updateUI();
            } else {
                this.showError(data.error || 'Errore accesso ospite');
            }
        } catch (error) {
            console.error('Guest login error:', error);
            this.showError('Errore di connessione');
        } finally {
            this.setLoading('btn-guest', false);
        }
    },
    
    async logout() {
        if (this.authToken) {
            try {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.authToken}`
                    },
                    body: JSON.stringify({ token: this.authToken })
                });
            } catch (error) {
                console.error('Logout error:', error);
            }
        }
        
        this.authToken = null;
        this.currentUser = null;
        
        localStorage.removeItem('presina_auth_token');
        localStorage.removeItem('presina_user');
        localStorage.removeItem('presina_is_guest');
        sessionStorage.removeItem('presina_player_name');
        App.playerName = '';
        
        this.updateUI();
        showScreen('home');
    },
    
    // ==================== Profile ====================
    async loadProfile() {
        if (!this.currentUser) return;
        
        // Update profile info
        document.getElementById('profile-display-name').textContent = 
            this.currentUser.display_name || this.currentUser.username;
        const displayNameInput = document.getElementById('display-name-input');
        if (displayNameInput) {
            displayNameInput.value = this.currentUser.display_name || this.currentUser.username;
        }
        document.getElementById('profile-username').textContent = 
            `@${this.currentUser.username}`;
        
        // Update avatar images
        const avatarUrl = this.normalizeAvatar(this.currentUser.avatar);
        const profileImg = document.getElementById('profile-avatar-img');
        const homeImg = document.getElementById('user-avatar-img');
        
        if (profileImg) profileImg.src = avatarUrl;
        if (homeImg) homeImg.src = avatarUrl;
        
        // Format member since
        if (this.currentUser.created_at) {
            const date = new Date(this.currentUser.created_at);
            document.getElementById('profile-member-since').textContent = 
                `Membro dal ${date.toLocaleDateString('it-IT')}`;
        }
        
        const editNameBtn = document.getElementById('btn-edit-display-name');
        const nameEditor = document.getElementById('display-name-editor');
        if (nameEditor) nameEditor.classList.add('hidden');

        // Guests have no stats/profile features
        if (this.isGuest()) {
            if (editNameBtn) editNameBtn.classList.add('hidden');
            if (nameEditor) nameEditor.classList.add('hidden');
            const history = document.getElementById('profile-game-history');
            if (history) {
                history.innerHTML = '<p class="empty-message">Accedi per vedere le statistiche</p>';
            }
            const leaderboard = document.getElementById('profile-leaderboard');
            if (leaderboard) {
                leaderboard.innerHTML = '<p class="empty-message">Disponibile solo per utenti registrati</p>';
            }
            const avatarInput = document.getElementById('avatar-upload-input');
            if (avatarInput) avatarInput.disabled = true;
            const avatarBtn = document.querySelector('label[for="avatar-upload-input"]');
            if (avatarBtn) avatarBtn.classList.add('hidden');
            return;
        }
        
        if (editNameBtn) editNameBtn.classList.remove('hidden');
        const avatarInput = document.getElementById('avatar-upload-input');
        if (avatarInput) avatarInput.disabled = false;
        const avatarBtn = document.querySelector('label[for="avatar-upload-input"]');
        if (avatarBtn) avatarBtn.classList.remove('hidden');
        
        // Load fresh stats
        await this.loadUserStats();
        
        // Load game history
        await this.loadGameHistory();
        
        // Load leaderboard
        await this.loadLeaderboard('wins');
    },
    
    // ==================== Avatar Upload ====================
    async uploadAvatar(input) {
        if (!input.files || !input.files[0]) return;
        
        const file = input.files[0];
        
        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showError('Seleziona un file immagine');
            return;
        }
        
        // Validate file size (max 2MB)
        if (file.size > 2 * 1024 * 1024) {
            this.showError('Immagine troppo grande (max 2MB)');
            return;
        }
        
        // Convert to base64
        const reader = new FileReader();
        reader.onload = async (e) => {
            const base64Image = e.target.result;
            
            try {
                const response = await fetch('/api/user/avatar', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.authToken}`
                    },
                    body: JSON.stringify({ image: base64Image })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Update current user
                    this.currentUser.avatar = data.avatar;
                    localStorage.setItem('presina_user', JSON.stringify(this.currentUser));
                    
                    // Update UI
                    const profileImg = document.getElementById('profile-avatar-img');
                    const homeImg = document.getElementById('user-avatar-img');
                    
                    if (profileImg) profileImg.src = data.avatar;
                    if (homeImg) homeImg.src = data.avatar;
                    
                    this.showSuccess('Foto profilo aggiornata!');
                } else {
                    this.showError(data.error || 'Errore upload');
                }
            } catch (error) {
                console.error('Upload error:', error);
                this.showError('Errore di connessione');
            }
        };
        
        reader.readAsDataURL(file);
    },

    // ==================== Display Name ====================
    startEditDisplayName() {
        if (!this.currentUser || this.isGuest()) return;
        const editor = document.getElementById('display-name-editor');
        const input = document.getElementById('display-name-input');
        const editBtn = document.getElementById('btn-edit-display-name');
        if (input) {
            input.value = this.currentUser.display_name || this.currentUser.username;
            input.focus();
            input.select();
        }
        if (editor) editor.classList.remove('hidden');
        if (editBtn) editBtn.classList.add('hidden');
    },

    cancelEditDisplayName() {
        const editor = document.getElementById('display-name-editor');
        const editBtn = document.getElementById('btn-edit-display-name');
        if (editor) editor.classList.add('hidden');
        if (editBtn && !this.isGuest()) editBtn.classList.remove('hidden');
    },

    async saveDisplayName() {
        if (!this.authToken || !this.currentUser || this.isGuest()) return;
        const input = document.getElementById('display-name-input');
        const newName = (input?.value || '').trim();
        if (!newName) {
            this.showError('Nome non valido');
            return;
        }
        if (newName.length > 20) {
            this.showError('Nome troppo lungo (max 20 caratteri)');
            return;
        }

        try {
            const response = await fetch('/api/user/display_name', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.authToken}`
                },
                body: JSON.stringify({ display_name: newName })
            });
            const data = await response.json();
            if (data.success) {
                this.currentUser.display_name = data.display_name;
                localStorage.setItem('presina_user', JSON.stringify(this.currentUser));

                const displayNameEl = document.getElementById('profile-display-name');
                if (displayNameEl) displayNameEl.textContent = data.display_name;

                // Update home UI + player name
                const userDisplay = document.getElementById('user-display-name');
                if (userDisplay) {
                    userDisplay.textContent = `Ciao, ${data.display_name}!`;
                }
                App.playerName = data.display_name;
                sessionStorage.setItem('presina_player_name', App.playerName);
                const playerNameInput = document.getElementById('player-name');
                if (playerNameInput) {
                    playerNameInput.value = App.playerName;
                }
                const playerNameDisplay = document.getElementById('player-name-display');
                if (playerNameDisplay) {
                    playerNameDisplay.textContent = App.playerName;
                }

                this.cancelEditDisplayName();
                this.showSuccess('Nome aggiornato!');
            } else {
                this.showError(data.error || 'Errore aggiornamento');
            }
        } catch (error) {
            console.error('Update display name error:', error);
            this.showError('Errore di connessione');
        }
    },
    
    async loadUserStats() {
        if (!this.authToken) return;
        
        try {
            const response = await fetch('/api/user/stats', {
                headers: { 'Authorization': `Bearer ${this.authToken}` }
            });
            
            const data = await response.json();
            
            if (data.success && data.stats) {
                const stats = data.stats;
                document.getElementById('profile-stat-games').textContent = stats.games_played || 0;
                document.getElementById('profile-stat-wins').textContent = stats.games_won || 0;
                document.getElementById('profile-stat-losses').textContent = stats.games_lost || 0;
                document.getElementById('profile-stat-winrate').textContent = `${stats.win_rate || 0}%`;
                document.getElementById('profile-stat-lives').textContent = stats.total_lives_lost || 0;
                document.getElementById('profile-stat-streak').textContent = stats.best_streak || 0;
                
                const homeGames = document.getElementById('home-stat-games');
                const homeWins = document.getElementById('home-stat-wins');
                const homeRate = document.getElementById('home-stat-winrate');
                if (homeGames) homeGames.textContent = stats.games_played || 0;
                if (homeWins) homeWins.textContent = stats.games_won || 0;
                if (homeRate) homeRate.textContent = `${stats.win_rate || 0}%`;
            }
        } catch (error) {
            console.error('Load stats error:', error);
        }
    },
    
    async loadGameHistory() {
        if (!this.authToken) return;
        
        try {
            const response = await fetch('/api/user/games?limit=10', {
                headers: { 'Authorization': `Bearer ${this.authToken}` }
            });
            
            const data = await response.json();
            const container = document.getElementById('profile-game-history');
            
            if (data.success && data.games && data.games.length > 0) {
                container.innerHTML = data.games.map(game => {
                    const date = new Date(game.played_at);
                    const isWin = game.won;
                    
                    return `
                        <div class="history-item ${isWin ? 'win' : 'loss'}">
                            <span class="history-result">${isWin ? '🏆' : '💔'}</span>
                            <div class="history-details">
                                <div class="history-room">${escapeHtml(game.room_name)}</div>
                                <div class="history-meta">
                                    ${date.toLocaleDateString('it-IT')} • 
                                    ${game.players_count} giocatori • 
                                    Posizione #${game.final_position}
                                </div>
                            </div>
                            <div class="history-stats">
                                <div class="history-lives">❤️ ${game.final_lives}</div>
                                <div>${game.tricks_won} prese</div>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                container.innerHTML = '<p class="empty-message">Nessuna partita giocata</p>';
            }
        } catch (error) {
            console.error('Load history error:', error);
        }
    },
    
    async loadLeaderboard(category = 'wins') {
        // Update tabs
        document.querySelectorAll('.lb-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.cat === category);
        });
        
        try {
            const response = await fetch(`/api/leaderboard?category=${category}&limit=10`);
            const data = await response.json();
            const container = document.getElementById('profile-leaderboard');
            
            if (data.success && data.leaderboard) {
                container.innerHTML = data.leaderboard.map((entry, idx) => {
                    const isMe = this.currentUser && entry.username === this.currentUser.username;
                    const rankClass = idx === 0 ? 'gold' : idx === 1 ? 'silver' : idx === 2 ? 'bronze' : '';
                    
                    let valueDisplay = '';
                    if (category === 'wins') {
                        valueDisplay = `${entry.games_won} vittorie`;
                    } else if (category === 'win_rate') {
                        valueDisplay = `${entry.win_rate}% win rate`;
                    } else if (category === 'streak') {
                        valueDisplay = `${entry.best_streak} streak`;
                    }
                    
                    return `
                        <div class="lb-item ${isMe ? 'me' : ''}">
                            <div class="lb-rank ${rankClass}">${entry.rank}</div>
                            <div class="lb-info">
                                <div class="lb-name">${escapeHtml(entry.display_name || entry.username)} ${isMe ? '(Tu)' : ''}</div>
                                <div class="lb-stats">${entry.games_played} partite</div>
                            </div>
                            <div class="lb-value">${valueDisplay}</div>
                        </div>
                    `;
                }).join('');
            } else {
                container.innerHTML = '<p class="empty-message">Nessun dato disponibile</p>';
            }
        } catch (error) {
            console.error('Load leaderboard error:', error);
        }
    },
    
    // ==================== Game Stats Tracking ====================
    async recordGameResult(gameResult) {
        // This would be called from the socket client when a game ends
        // For now, just refresh stats
        if (this.authToken) {
            await this.loadUserStats();
        }
    },
    
    // ==================== Navigation ====================
    enterLobby() {
        // Assicurati che il nome del giocatore sia impostato correttamente
        if (this.currentUser) {
            App.playerName = this.currentUser.display_name || this.currentUser.username;
            sessionStorage.setItem('presina_player_name', App.playerName);
            const playerNameInput = document.getElementById('player-name');
            const playerNameDisplay = document.getElementById('player-name-display');
            if (playerNameInput) {
                playerNameInput.value = App.playerName;
            }
            if (playerNameDisplay) {
                playerNameDisplay.textContent = App.playerName;
            }
        }
        
        // Connetti socket e registra
        SocketClient.connect();
        SocketClient.registerPlayer();
        
        // Mostra la lobby
        showScreen('lobby');
        SocketClient.listRooms();
        
        // Mostra banner rejoin se c'è una stanza salvata
        setTimeout(() => {
            if (typeof checkAndShowRejoinBanner === 'function') {
                checkAndShowRejoinBanner();
            }
        }, 500);
    },
    
    // ==================== Helpers ====================
    normalizeAvatar(url) {
        if (!url || url.includes('default-avatar.png')) {
            return '/static/img/logo.png';
        }
        return url;
    },

    bindEvents() {
        document.querySelectorAll('.auth-tab').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
        
        const loginBtn = document.getElementById('btn-login');
        if (loginBtn) loginBtn.addEventListener('click', () => this.login());
        
        const registerBtn = document.getElementById('btn-register');
        if (registerBtn) registerBtn.addEventListener('click', () => this.register());
        
        const guestBtn = document.getElementById('btn-guest');
        if (guestBtn) guestBtn.addEventListener('click', () => this.guestLogin());
        
        const logoutBtn = document.getElementById('btn-logout');
        if (logoutBtn) logoutBtn.addEventListener('click', () => this.logout());
        
        const logoutProfileBtn = document.getElementById('btn-logout-profile');
        if (logoutProfileBtn) logoutProfileBtn.addEventListener('click', () => this.logout());
        
        const profileBtn = document.getElementById('btn-profile');
        if (profileBtn) profileBtn.addEventListener('click', () => showScreen('profile'));
        
        const backProfileBtn = document.getElementById('btn-back-profile');
        if (backProfileBtn) backProfileBtn.addEventListener('click', () => showScreen('home'));
        
        const backHomeProfileBtn = document.getElementById('btn-back-home-profile');
        if (backHomeProfileBtn) backHomeProfileBtn.addEventListener('click', () => showScreen('home'));
        
        const avatarInput = document.getElementById('avatar-upload-input');
        if (avatarInput) {
            avatarInput.addEventListener('change', (e) => this.uploadAvatar(e.target));
        }

        const editNameBtn = document.getElementById('btn-edit-display-name');
        if (editNameBtn) editNameBtn.addEventListener('click', () => this.startEditDisplayName());
        const saveNameBtn = document.getElementById('btn-save-display-name');
        if (saveNameBtn) saveNameBtn.addEventListener('click', () => this.saveDisplayName());
        const cancelNameBtn = document.getElementById('btn-cancel-display-name');
        if (cancelNameBtn) cancelNameBtn.addEventListener('click', () => this.cancelEditDisplayName());
        const displayNameInput = document.getElementById('display-name-input');
        if (displayNameInput) {
            displayNameInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.saveDisplayName();
            });
        }
        
        document.querySelectorAll('.lb-tab').forEach(btn => {
            btn.addEventListener('click', () => this.loadLeaderboard(btn.dataset.cat));
        });
        
        // Enter key submits login/register
        const loginPassword = document.getElementById('login-password');
        if (loginPassword) {
            loginPassword.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.login();
            });
        }
        const registerPassword = document.getElementById('register-password');
        if (registerPassword) {
            registerPassword.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.register();
            });
        }
    },

    setLoading(btnId, loading) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        
        if (loading) {
            btn.disabled = true;
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = '<span class="spinner"></span> Caricamento...';
        } else {
            btn.disabled = false;
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
        }
    },
    
    showError(message) {
        // Remove existing messages
        document.querySelectorAll('.auth-error, .auth-success').forEach(el => el.remove());
        
        const error = document.createElement('div');
        error.className = 'auth-error';
        error.textContent = message;
        
        const activeForm = document.querySelector('.auth-form.active');
        if (activeForm) {
            activeForm.insertBefore(error, activeForm.firstChild);
            
            setTimeout(() => error.remove(), 5000);
        }
    },
    
    showSuccess(message) {
        // Remove existing messages
        document.querySelectorAll('.auth-error, .auth-success').forEach(el => el.remove());
        
        const success = document.createElement('div');
        success.className = 'auth-success';
        success.textContent = message;
        
        const activeForm = document.querySelector('.auth-form.active');
        if (activeForm) {
            activeForm.insertBefore(success, activeForm.firstChild);
            
            setTimeout(() => success.remove(), 5000);
        }
    },
    
    getAuthToken() {
        return this.authToken;
    },
    
    getCurrentUser() {
        return this.currentUser;
    },
    
    isLoggedIn() {
        return !!this.currentUser;
    },
    
    isGuest() {
        return localStorage.getItem('presina_is_guest') === 'true';
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    AuthUI.init();
    
    // Update profile when screen is shown
    const originalShowScreen = window.showScreen;
    window.showScreen = function(screenId) {
        originalShowScreen(screenId);
        if (screenId === 'profile') {
            AuthUI.loadProfile();
        }
    };
});

// Export
window.AuthUI = AuthUI;
