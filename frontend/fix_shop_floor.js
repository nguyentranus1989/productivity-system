// Add this to shop-floor.html to make it dynamic
const shopFloorUpdater = {
    api: null,
    
    init() {
        this.api = new ProductivityAPI();
        this.loadLeaderboard();
        // Refresh every 30 seconds
        setInterval(() => this.loadLeaderboard(), 30000);
    },
    
    async loadLeaderboard() {
        try {
            const today = this.api.getCentralDate();
            const leaderboard = await this.api.getLeaderboard(today);
            
            // Get the leaderboard container
            const container = document.querySelector('.leaderboard-grid');
            if (!container) return;
            
            // Clear existing cards
            container.innerHTML = '<h2>🌟 Today\'s Leaders (<span id="activeCount">0</span> Active) 🌟</h2>';
            
            // Count active employees
            const activeCount = leaderboard.filter(e => e.is_clocked_in).length;
            document.getElementById('activeCount').textContent = activeCount;
            
            // Show top 5 employees
            leaderboard.slice(0, 5).forEach((employee, index) => {
                const card = document.createElement('div');
                card.className = 'employee-card';
                card.style.animationDelay = `${index * 0.1}s`;
                
                // Determine status emoji and text
                const statusEmoji = employee.is_clocked_in ? '🟢' : '🔴';
                const statusText = employee.is_clocked_in ? 'Working' : 'Off';
                const timeDisplay = employee.time_worked || '0:00';
                
                card.innerHTML = `
                    <div class="rank">${index + 1}</div>
                    <div class="employee-info">
                        <div class="employee-avatar">${statusEmoji}</div>
                        <div>
                            <div class="employee-name">${employee.name}</div>
                            <div class="employee-stats">
                                <span>${statusEmoji} ${employee.items_today || 0} items</span>
                                <span>⏱️ ${timeDisplay}</span>
                                <span>${statusText}</span>
                            </div>
                            <div class="employee-activities">
                                ${employee.activity_display || ''}
                            </div>
                        </div>
                    </div>
                    <div class="employee-score">${Math.round(employee.score || 0)}</div>
                `;
                
                container.appendChild(card);
            });
            
        } catch (error) {
            console.error('Error loading leaderboard:', error);
        }
    }
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    shopFloorUpdater.init();
});
