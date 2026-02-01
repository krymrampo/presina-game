/**
 * Presina - Chat Module
 * Handles chat functionality
 */

const Chat = {
    messages: [],
    isOpen: false,
    
    addMessage(msgData) {
        this.messages.push(msgData);
        
        // Keep only last 100 messages
        if (this.messages.length > 100) {
            this.messages = this.messages.slice(-100);
        }
        
        this.renderMessages();
        
        // Show badge if chat is closed
        if (!this.isOpen && (App.currentScreen === 'game' || App.currentScreen === 'game-over')) {
            document.getElementById('chat-badge').classList.remove('hidden');
        }
    },
    
    loadHistory(messages) {
        this.messages = messages || [];
        this.renderMessages();
    },
    
    renderMessages() {
        // Render in game chat
        const gameChatMessages = document.getElementById('chat-messages');
        if (gameChatMessages) {
            gameChatMessages.innerHTML = this.renderMessageList();
            gameChatMessages.scrollTop = gameChatMessages.scrollHeight;
        }
        
        // Render in waiting room chat
        const waitingChatMessages = document.getElementById('waiting-chat-messages');
        if (waitingChatMessages) {
            waitingChatMessages.innerHTML = this.renderMessageList();
            waitingChatMessages.scrollTop = waitingChatMessages.scrollHeight;
        }
    },
    
    renderMessageList() {
        return this.messages.map(msg => {
            const isOwn = msg.player_id === App.playerId;
            const time = new Date(msg.timestamp * 1000).toLocaleTimeString('it-IT', {
                hour: '2-digit',
                minute: '2-digit'
            });
            
            return `
                <div class="chat-message ${isOwn ? 'own' : ''}">
                    <span class="msg-name">${escapeHtml(msg.player_name)}</span>
                    <span class="msg-time">[${time}]</span>:
                    <span class="msg-text">${escapeHtml(msg.message)}</span>
                </div>
            `;
        }).join('');
    },
    
    toggle() {
        this.isOpen = !this.isOpen;
        const chatContainer = document.getElementById('game-chat');
        
        if (this.isOpen) {
            chatContainer.classList.remove('collapsed');
            document.getElementById('chat-badge').classList.add('hidden');
        } else {
            chatContainer.classList.add('collapsed');
        }
    },
    
    clear() {
        this.messages = [];
        this.renderMessages();
    }
};

// Export
window.Chat = Chat;
