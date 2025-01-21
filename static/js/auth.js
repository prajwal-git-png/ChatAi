class AuthManager {
    constructor() {
        this.isLoggedIn = document.cookie.includes('session');
    }

    async login(username, password) {
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            if (response.ok) {
                return true;
            }
            return false;
        } catch (error) {
            console.error('Login error:', error);
            return false;
        }
    }

    logout() {
        window.location.href = '/logout';
    }

    isAuthenticated() {
        return this.isLoggedIn;
    }

    getAuthHeaders() {
        return {
            'Content-Type': 'application/json'
        };
    }
}