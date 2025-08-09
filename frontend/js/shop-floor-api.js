// frontend/js/shop-floor-api.js
class ShopFloorAPI {
    constructor() {
        this.baseURL = 'http://localhost:5000/api';
        this.apiKey = 'dev-api-key-123';
        this.updateInterval = 5000; // 5 seconds
        this.lastUpdate = null;
    }
    
    async fetchData(endpoint) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                headers: {
                    'X-API-Key': this.apiKey,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) throw new Error(`API Error: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('API fetch error:', error);
            return null;
        }
    }
    
    async getLeaderboard() {
        const data = await this.fetchData('/cache/leaderboard');
        if (data && data.data) {
            return data.data.scores || [];
        }
        return [];
    }
    
    async getTeamStats() {
        const data = await this.fetchData('/cache/team/stats');
        if (data && data.data) {
            return data.data;
        }
        return null;
    }
    
    async getCurrentlyWorking() {
        const data = await this.fetchData('/connecteam/working/now');
        if (data && data.employees) {
            return data.employees;
        }
        return [];
    }
    
    startLiveUpdates(callback) {
        // Initial load
        this.updateDashboard(callback);
        
        // Set interval for updates
        setInterval(() => {
            this.updateDashboard(callback);
        }, this.updateInterval);
    }
    
    async updateDashboard(callback) {
        const [leaderboard, teamStats, working] = await Promise.all([
            this.getLeaderboard(),
            this.getTeamStats(),
            this.getCurrentlyWorking()
        ]);
        
        const data = {
            leaderboard,
            teamStats,
            working,
            timestamp: new Date()
        };
        
        // Check for changes and trigger animations/sounds
        if (this.lastUpdate) {
            this.detectChanges(this.lastUpdate, data);
        }
        
        this.lastUpdate = data;
        callback(data);
    }
    
    detectChanges(oldData, newData) {
        // Check for new achievements
        if (newData.leaderboard.length > 0 && oldData.leaderboard.length > 0) {
            const oldLeader = oldData.leaderboard[0];
            const newLeader = newData.leaderboard[0];
            
            if (oldLeader.employee_id !== newLeader.employee_id) {
                this.triggerNewLeader(newLeader);
            }
            
            // Check for score improvements
            newData.leaderboard.forEach(employee => {
                const oldEmployee = oldData.leaderboard.find(e => e.employee_id === employee.employee_id);
                if (oldEmployee && employee.points_earned > oldEmployee.points_earned) {
                    this.triggerScoreIncrease(employee);
                }
            });
        }
    }
    
    triggerNewLeader(leader) {
        soundManager.play('levelUp');
        this.showNotification(`🎉 New Leader: ${leader.name}!`, 'success');
    }
    
    triggerScoreIncrease(employee) {
        soundManager.play('tick');
        // Animate the score
        const scoreElement = document.querySelector(`[data-employee-id="${employee.employee_id}"] .employee-score`);
        if (scoreElement) {
            scoreElement.classList.add('score-pop');
            setTimeout(() => scoreElement.classList.remove('score-pop'), 500);
        }
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => notification.classList.add('show'), 100);
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}