class StorageHandler {
    constructor() {
        this.storageKey = 'chats';
    }

    saveChat(chatData) {
        try {
            const chats = this.getChats();
            chats.unshift(chatData);
            
            if (this.isStorageQuotaExceeded()) {
                // Remove oldest chats if storage limit is reached
                chats.splice(-10);
            }
            
            localStorage.setItem(this.storageKey, JSON.stringify(chats));
            return true;
        } catch (error) {
            console.error('Storage error:', error);
            return false;
        }
    }

    getChats(limit = 50) {
        try {
            const chats = JSON.parse(localStorage.getItem(this.storageKey) || '[]');
            return chats.slice(0, limit);
        } catch (error) {
            console.error('Error reading chats:', error);
            return [];
        }
    }

    private isStorageQuotaExceeded() {
        let exceeded = false;
        const testKey = 'storage_test';
        
        try {
            localStorage.setItem(testKey, '0');
            localStorage.removeItem(testKey);
        } catch (e) {
            exceeded = true;
        }
        
        return exceeded;
    }
} 