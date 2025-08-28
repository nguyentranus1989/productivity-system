// config.js
const CONFIG = {
  API_BASE: (window.location.hostname === 'localhost' || 
            window.location.hostname === '127.0.0.1' ||
            window.location.hostname === '' ||
            window.location.protocol === 'file:')
    ? 'http://134.199.194.237/api'
    : '/api'
};

console.log('API Configuration loaded. Using:', CONFIG.API_BASE);