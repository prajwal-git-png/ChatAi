// Message handling functionality
class MessageHandler {
    constructor() {
        this.chatMessages = document.getElementById('chat-messages');
    }

    async sendMessage(message) {
        if (!message.trim()) return;
        
        try {
            showTypingIndicator();
            const response = await this.fetchBotResponse(message);
            removeTypingIndicator();
            
            if (response.ok) {
                const data = await response.json();
                return data.response;
            }
            throw new Error('Network response was not ok');
        } catch (error) {
            console.error('Error:', error);
            return 'Sorry, I encountered an error. Please try again.';
        }
    }

    appendMessage(content, isUser) {
        // Reference existing appendMessage function
        // Lines 157-222 from original code
    }

    private async fetchBotResponse(message) {
        return await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
    }
} 