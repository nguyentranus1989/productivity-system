/**
 * Theme Switcher - Manages theme selection across pages
 * Supports: Original, Cyberpunk, Executive themes
 * Persists selection to localStorage
 */

const ThemeSwitcher = {
    // Available themes configuration
    themes: {
        'original': {
            label: 'Original',
            description: 'Classic dark purple theme',
            managerCss: 'css/manager.css',
            shopFloorCss: null // Uses inline styles
        },
        'cyberpunk': {
            label: 'Cyberpunk',
            description: 'Neon cyan & pink futuristic',
            managerCss: 'css/manager-cyberpunk.css',
            shopFloorCss: 'css/shop-floor-cyberpunk.css'
        },
        'executive': {
            label: 'Executive',
            description: 'Premium dark slate professional',
            managerCss: 'css/manager-executive.css',
            shopFloorCss: 'css/shop-floor-executive.css'
        }
    },

    // Storage key
    STORAGE_KEY: 'selectedTheme',

    // Default theme
    DEFAULT_THEME: 'cyberpunk',

    /**
     * Initialize theme on page load
     * @param {string} pageType - 'manager' or 'shop-floor'
     */
    init(pageType = 'manager') {
        const saved = this.getSavedTheme();
        this.apply(saved, pageType);

        // Listen for storage changes (sync across tabs)
        window.addEventListener('storage', (e) => {
            if (e.key === this.STORAGE_KEY && e.newValue) {
                this.apply(e.newValue, pageType, false);
            }
        });
    },

    /**
     * Get saved theme from localStorage
     * @returns {string} Theme name
     */
    getSavedTheme() {
        return localStorage.getItem(this.STORAGE_KEY) || this.DEFAULT_THEME;
    },

    /**
     * Apply theme to current page
     * @param {string} themeName - Theme to apply
     * @param {string} pageType - 'manager' or 'shop-floor'
     * @param {boolean} save - Whether to save to localStorage
     */
    apply(themeName, pageType = 'manager', save = true) {
        const theme = this.themes[themeName];
        if (!theme) {
            console.warn(`Theme "${themeName}" not found, using default`);
            themeName = this.DEFAULT_THEME;
        }

        // Get or create theme CSS link
        let themeLink = document.getElementById('theme-css');

        if (pageType === 'manager') {
            if (themeLink) {
                themeLink.href = theme.managerCss;
            }
        } else if (pageType === 'shop-floor') {
            // Shop floor uses data-theme attribute for variable overrides
            document.documentElement.setAttribute('data-theme', themeName);

            // Load external override CSS if exists
            if (theme.shopFloorCss) {
                let overrideLink = document.getElementById('theme-override-css');
                if (!overrideLink) {
                    overrideLink = document.createElement('link');
                    overrideLink.id = 'theme-override-css';
                    overrideLink.rel = 'stylesheet';
                    document.head.appendChild(overrideLink);
                }
                overrideLink.href = theme.shopFloorCss;
            } else {
                // Remove override if original theme
                const overrideLink = document.getElementById('theme-override-css');
                if (overrideLink) {
                    overrideLink.remove();
                }
            }
        }

        // Update active state in UI if settings modal exists
        this.updateUI(themeName);

        // Save to localStorage
        if (save) {
            localStorage.setItem(this.STORAGE_KEY, themeName);
        }

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('themeChanged', {
            detail: { theme: themeName, pageType }
        }));
    },

    /**
     * Update settings modal UI to show active theme
     * @param {string} activeTheme - Currently active theme
     */
    updateUI(activeTheme) {
        const buttons = document.querySelectorAll('.theme-option-btn');
        buttons.forEach(btn => {
            const isActive = btn.dataset.theme === activeTheme;
            btn.classList.toggle('active', isActive);

            // Update visual indicator
            const indicator = btn.querySelector('.theme-active-indicator');
            if (indicator) {
                indicator.style.display = isActive ? 'block' : 'none';
            }
        });
    },

    /**
     * Get current theme name
     * @returns {string} Current theme name
     */
    getCurrent() {
        return this.getSavedTheme();
    },

    /**
     * Get all available themes
     * @returns {Object} Themes configuration
     */
    getThemes() {
        return this.themes;
    }
};

// Auto-detect page type and initialize
document.addEventListener('DOMContentLoaded', () => {
    const isShopFloor = window.location.pathname.includes('shop-floor');
    const pageType = isShopFloor ? 'shop-floor' : 'manager';
    ThemeSwitcher.init(pageType);
});
