// frontend/js/themes.js
const themes = {
    default: {
        name: 'Default',
        background: 'linear-gradient(45deg, #1a1a2e, #16213e, #0f3460)',
        primary: '#00ff88',
        secondary: '#00ddff',
        accent: '#ffd700',
        cardBg: 'rgba(255, 255, 255, 0.05)',
        textColor: '#ffffff'
    },
    light: {
        name: 'Light Mode',
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
        primary: '#2ecc71',
        secondary: '#3498db',
        accent: '#f39c12',
        cardBg: 'rgba(255, 255, 255, 0.9)',
        textColor: '#2c3e50'
    },
    christmas: {
        name: 'Christmas',
        background: 'linear-gradient(45deg, #0f4c75, #1e5f74, #133b5c)',
        primary: '#ff0000',
        secondary: '#00ff00',
        accent: '#ffd700',
        cardBg: 'rgba(255, 255, 255, 0.1)',
        textColor: '#ffffff',
        particles: '❄️'
    },
    halloween: {
        name: 'Halloween',
        background: 'linear-gradient(45deg, #1a0033, #330066, #4d0099)',
        primary: '#ff6600',
        secondary: '#9933ff',
        accent: '#ffcc00',
        cardBg: 'rgba(0, 0, 0, 0.3)',
        textColor: '#ffffff',
        particles: '🎃'
    },
    summer: {
        name: 'Summer',
        background: 'linear-gradient(45deg, #ff9a00, #ff5e00, #ff0099)',
        primary: '#00ffff',
        secondary: '#ffff00',
        accent: '#00ff00',
        cardBg: 'rgba(255, 255, 255, 0.2)',
        textColor: '#ffffff'
    }
};

class ThemeManager {
    constructor() {
        this.currentTheme = 'default';
        this.autoRotate = false;
    }
    
    apply(themeName) {
        const theme = themes[themeName] || themes.default;
        this.currentTheme = themeName;
        
        document.documentElement.style.setProperty('--bg-gradient', theme.background);
        document.documentElement.style.setProperty('--primary-color', theme.primary);
        document.documentElement.style.setProperty('--secondary-color', theme.secondary);
        document.documentElement.style.setProperty('--accent-color', theme.accent);
        document.documentElement.style.setProperty('--card-bg', theme.cardBg);
        document.documentElement.style.setProperty('--text-color', theme.textColor);
        
        // Special effects for holiday themes
        if (theme.particles) {
            this.addThemeParticles(theme.particles);
        }
    }
    
    addThemeParticles(particleType) {
        const container = document.getElementById('themeParticles');
        container.innerHTML = '';
        
        for (let i = 0; i < 20; i++) {
            const particle = document.createElement('div');
            particle.className = 'theme-particle';
            particle.textContent = particleType;
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 10 + 's';
            container.appendChild(particle);
        }
    }
    
    startAutoRotate(interval = 3600000) { // 1 hour default
        this.autoRotate = true;
        setInterval(() => {
            const themeNames = Object.keys(themes);
            const currentIndex = themeNames.indexOf(this.currentTheme);
            const nextIndex = (currentIndex + 1) % themeNames.length;
            this.apply(themeNames[nextIndex]);
        }, interval);
    }
}