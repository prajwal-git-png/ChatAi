class HistoryManager {
    constructor(storageHandler, messageLimit = 50) {
        this.storageHandler = storageHandler;
        this.messageLimit = messageLimit;
        this.currentPage = 1;
    }

    loadChatHistory(chatId, page = 1) {
        const chat = this.storageHandler.getChats().find(c => c.id === chatId);
        if (!chat) return;

        const startIndex = (page - 1) * this.messageLimit;
        const messages = chat.messages.slice(startIndex, startIndex + this.messageLimit);
        
        return {
            messages,
            hasMore: chat.messages.length > startIndex + this.messageLimit
        };
    }

    appendHistoryItems(container, chats) {
        const fragment = document.createDocumentFragment();
        
        chats.forEach(chat => {
            const historyItem = this.createHistoryItem(chat);
            fragment.appendChild(historyItem);
        });

        container.appendChild(fragment);
    }
} 