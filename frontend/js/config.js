// Global configuration - auto-detects environment
window.AppConfig = {
    getApiUrl() {
        const hostname = window.location.hostname;
        
        // Production server
        if (hostname === '134.199.194.237' || hostname.includes('yourdomain.com')) {
            return 'http://134.199.194.237:5000';
        }
        
        // Local development
        return 'http://localhost:5000';
    },
    
    apiKey: 'dev-api-key-123',
    
    // Helper to build API endpoints
    api(endpoint) {
        return `${this.getApiUrl()}/api${endpoint}`;
    }
};

console.log('AppConfig loaded:', window.AppConfig.getApiUrl());