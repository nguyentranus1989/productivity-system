// Dynamic API URL based on environment
const API_BASE_URL = (() => {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:5000/api';
    } else if (hostname === '134.199.194.237') {
        return 'http://134.199.194.237:5000/api';
    } else {
        // Fallback for any other domain
        return `http://${hostname}:5000/api`;
    }
})();

console.log('API configured for:', API_BASE_URL);
const API_KEY = 'dev-api-key-123';

// Main API class
class ProductivityAPI {
    constructor() {
        this.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
        };
    }

    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                ...options,
                headers: { ...this.headers, ...options.headers }
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }
        // Add this helper method
    getCentralDate() {
        // Get current time
        const now = new Date();
        
        // Calculate Central Time offset (UTC-6 for CST, UTC-5 for CDT)
        // During August, it's CDT (UTC-5)
        const utcTime = now.getTime() + (now.getTimezoneOffset() * 60000);
        const centralTime = new Date(utcTime + (3600000 * -5)); // UTC-5 for CDT
        
        // Format as YYYY-MM-DD
        const year = centralTime.getFullYear();
        const month = String(centralTime.getMonth() + 1).padStart(2, '0');
        const day = String(centralTime.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    }


    // Dashboard endpoints
    async getDepartmentStats() {
        return this.request('/dashboard/departments/stats');
    }

    async getLeaderboardRange(startDate, endDate) {
        return this.request(`/dashboard/analytics/date-range?start_date=${startDate}&end_date=${endDate}`);
    }

    async getLeaderboard(date = null) {
        const targetDate = date || this.getCentralDate();
        return this.request(`/dashboard/leaderboard?date=${targetDate}`);
    }

    async getRecentActivities(limit = 10) {
        return this.request(`/dashboard/activities/recent?limit=${limit}`);
    }

    async getActiveAlerts() {
        return this.request('/dashboard/alerts/active');
    }

    async getHourlyProductivity(date = null) {
        const targetDate = date || this.getCentralDate();
        return this.request(`/dashboard/analytics/hourly?date=${targetDate}`);
    }
    
    // Add a method to get current Central Time
    getCurrentCentralTime() {
        const now = new Date();
        return new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));
    }
    async getTeamMetrics() {
        return this.request('/dashboard/analytics/team-metrics');
    }

    async getClockTimes(date = null) {
        return this.request('/dashboard/clock-times/today');
    }    

    // Employee endpoints
    async getEmployees() {
        return this.request('/dashboard/employees');
    }

    async getEmployeeStats(employeeId) {
        return this.request(`/dashboard/employees/${employeeId}/stats`);
    }

    async getEmployeeActivities(employeeId, limit = 10) {
        return this.request(`/dashboard/activities?employee_id=${employeeId}&limit=${limit}`);
    }

    // Connecteam endpoints
    async getWorkingNow() {
        return this.request('/connecteam/working/now');
    }

    async getWorkingToday() {
        return this.request('/connecteam/working/today');
    }

    // Gamification endpoints
    async getAchievements() {
        return this.request('/dashboard/gamification/achievements');
    }

    async getDepartmentBattle() {
        return this.request('/dashboard/departments/battle');
    }

    async getHourlyHeatmap() {
        return this.request('/dashboard/analytics/hourly-heatmap');
    }

    async getStreakLeaders() {
        return this.request('/dashboard/analytics/streak-leaders');
    }

    async getLiveLeaderboard() {
        return this.request('/dashboard/leaderboard/live');
    }

    async getAchievementTicker() {
        return this.request('/dashboard/analytics/achievement-ticker');
    }
    // In your ProductivityAPI class, add:
    async getBottleneckCurrent() {
        return this.request('/dashboard/bottleneck/current');
    }
    async getCostAnalysis(startDate = null, endDate = null) {
        let params = '';
        if (startDate && endDate) {
            params = `?start_date=${startDate}&end_date=${endDate}`;
        } else if (startDate) {
            params = `?start_date=${startDate}&end_date=${startDate}`;
        } else {
            // No dates provided, use today
            const today = this.getCentralDate();
            params = `?start_date=${today}&end_date=${today}`;
        }
        return this.request(`/dashboard/cost-analysis${params}`);
    }

    async getCostTrends(range = 'week') {
        return this.request(`/dashboard/cost-trends?range=${range}`);
    }
}

// Shop Floor Display Manager
class ShopFloorDisplay {
    constructor() {
        this.api = new ProductivityAPI();
        this.updateInterval = null;
        this.clockInterval = null;
    }

    async init() {
        try {
            // Start clock display
            this.startClock();
            
            // Load initial data
            await this.loadLeaderboard();
            await this.loadTicker();
            
            // Start real-time updates
            this.startRealtimeUpdates();
            
            // Auto-refresh at midnight Central Time
            this.scheduleMiddnightRefresh();
        } catch (error) {
            console.error('Error initializing display:', error);
        }
    }

    startClock() {
        const updateClock = () => {
            const now = this.api.getCurrentCentralTime();
            const dateStr = now.toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            const timeStr = now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            // Update clock display if element exists
            const clockElement = document.getElementById('currentDateTime');
            if (clockElement) {
                clockElement.innerHTML = `${dateStr} at ${timeStr}`;
            }
            
            // Update any date displays
            const dateElements = document.querySelectorAll('.current-date');
            dateElements.forEach(el => {
                el.textContent = dateStr;
            });
        };
        
        // Update immediately
        updateClock();
        
        // Update every second
        this.clockInterval = setInterval(updateClock, 1000);
    }

    scheduleMiddnightRefresh() {
        const scheduleNext = () => {
            const now = this.api.getCurrentCentralTime();
            const tomorrow = new Date(now);
            tomorrow.setDate(tomorrow.getDate() + 1);
            tomorrow.setHours(0, 0, 5, 0); // 5 seconds after midnight
            
            const msUntilMidnight = tomorrow - now;
            
            setTimeout(() => {
                console.log('Midnight refresh triggered');
                window.location.reload();
            }, msUntilMidnight);
        };
        
        scheduleNext();
    }

    async loadLeaderboard() {
        try {
            // Always use current date
            const today = this.api.getCentralDate();
            console.log('Loading leaderboard for:', today);
            
            const [leaderboard, teamStats, streakLeaders] = await Promise.all([
                this.api.getLeaderboard(),
                this.api.getTeamMetrics(),
                this.api.getStreakLeaders()
            ]);

            this.updateLeaderboard(leaderboard);
            this.updateTeamStats(teamStats);
            this.updateStreakLeaders(streakLeaders);

        } catch (error) {
            console.error('Failed to load leaderboard:', error);
        }
    }

    async loadTicker() {
        try {
            const achievements = await this.api.getAchievementTicker();
            console.log('Achievement ticker:', achievements);
            this.updateAchievementTicker(achievements);
        } catch (error) {
            console.error('Error loading ticker:', error);
        }
    }

    // In dashboard-api.js, update the updateLeaderboard function in the ShopFloorDisplay class:
    updateLeaderboard(employees) {
        const container = document.getElementById('leaderboardContent');
        if (!container) {
            console.error('Leaderboard container not found!');
            return;
        }

        console.log('Updating leaderboard with', employees.length, 'employees');

        // Create the HTML for all employees
        const content = employees.map((emp, index) => {
            let rankClass = '';
            let rankDisplay = emp.rank;
            
            if (emp.rank === 1) {
                rankClass = 'rank-1';
                rankDisplay = '🥇';
            } else if (emp.rank === 2) {
                rankClass = 'rank-2';
                rankDisplay = '🥈';
            } else if (emp.rank === 3) {
                rankClass = 'rank-3';
                rankDisplay = '🥉';
            }
            
            return `
                <div class="employee-card">
                    <div class="rank ${rankClass}">${rankDisplay}</div>
                    <div class="employee-info">
                        <div class="employee-name">${emp.name}</div>
                        <div class="employee-stats">
                            <span>⏱️ ${emp.time_worked}</span>
                            <span>📦 ${emp.items_today} items</span>
                            <span>⚡ ${emp.items_per_minute}/min</span>
                            <span>${emp.clock_status} ${emp.status_text}</span>
                        </div>
                        <div class="employee-activities">
                            <span style="font-size: 1.1em; opacity: 0.9;">
                                ${emp.activity_display}
                            </span>
                        </div>
                        ${emp.badge ? `<div class="employee-badge" style="font-size: 0.85em; margin-top: 5px; color: #00ff88;">${emp.badge}</div>` : ''}
                    </div>
                    <div class="employee-score">${emp.score}</div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" style="width: ${emp.progress || 0}%"></div>
                    </div>
                </div>
            `;
        }).join('');

        // Update the content
        container.innerHTML = content;
        
        // Update the title
        const titleElement = document.querySelector('.leaderboard h2');
        if (titleElement) {
            const activeCount = employees.filter(emp => emp.is_clocked_in).length;
            titleElement.textContent = `🌟 Today's Leaders (${activeCount} Active) 🌟`;
        }
    }
    updateTeamStats(stats) {
        console.log('Updating team stats:', stats);
        
        // Update circular progress
        const progressPercent = Math.round((stats.points_today / stats.daily_goal) * 100);
        this.animateCircularProgress(progressPercent);
        
        // Update progress text
        const progressText = document.querySelector('.progress-text');
        if (progressText) {
            progressText.textContent = `${progressPercent}%`;
        }
        
        // Update items count
        const itemsLabel = document.querySelector('.goal-progress .stat-label');
        if (itemsLabel) {
            itemsLabel.textContent = `${stats.items_today.toLocaleString()} / ${stats.daily_goal.toLocaleString()} items`;
        }
        
        // Update stat cards
        const statCards = document.querySelectorAll('.stat-card');
        if (statCards.length >= 4) {
            // Active employees (showing both active/total) - Fixed to handle undefined
            const totalEmployees = stats.total_employees || stats.total_employees_today || 0;
            statCards[0].querySelector('.stat-value').textContent = `${stats.active_employees}/${totalEmployees}`;
            statCards[0].querySelector('.stat-label').textContent = 'Active / Total Team';
            
            // vs Yesterday
            const vsYesterday = stats.vs_yesterday >= 0 ? `⬆ ${Math.abs(stats.vs_yesterday)}%` : `⬇ ${Math.abs(stats.vs_yesterday)}%`;
            statCards[1].querySelector('.stat-value').textContent = vsYesterday;
            statCards[1].querySelector('.stat-value').className = stats.vs_yesterday >= 0 ? 'stat-value stat-good' : 'stat-value stat-warning';
            
            // Total hours worked
            statCards[2].querySelector('.stat-value').textContent = `${stats.total_hours_worked}`;
            statCards[2].querySelector('.stat-label').textContent = 'Total Hours Today';
            
            // Changed from Top Department to Total Items Finished
            const itemsFinished = stats.items_finished || stats.items_today || 0;
            statCards[3].querySelector('.stat-value').textContent = itemsFinished.toLocaleString();
            statCards[3].querySelector('.stat-label').textContent = 'Total Items Finished';
        }
    }

    updateStreakLeaders(leaders) {
        console.log('Updating streak leaders:', leaders);
        
        // Find the Streak Champions container
        const goalProgress = document.querySelector('.goal-progress');
        if (!goalProgress) {
            console.error('Goal progress container not found');
            return;
        }
        
        // Get the QC passed total from team metrics
        this.api.getTeamMetrics().then(stats => {
            const finishedToday = stats.items_finished || stats.items_today || 0;
            
            // Replace the entire content with QC passed display
            goalProgress.innerHTML = `
                <h3 style="text-align: center; font-size: 3em; margin-bottom: 10px;">🎯 Finished Today</h3>
                <div style="text-align: center; padding: 20px 10px;">
                    <div style="font-size: 7em; font-weight: bold; color: #00ff88; margin-bottom: 5px; line-height: 1;">
                        ${finishedToday.toLocaleString()}
                    </div>
                    <div style="font-size: 1.3em; opacity: 0.9;">
                        💪 Team Power!
                    </div>
                </div>
                ${leaders && leaders.length > 0 ? `
                    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <h4 style="margin-bottom: 10px; text-align: center;">🔥 Streak Leaders</h4>
                        ${leaders.slice(0, 3).map((leader, index) => {
                            const icon = index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉';
                            return `
                                <div style="display: flex; align-items: center; padding: 8px; margin-bottom: 5px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                                    <span style="font-size: 1.3em; margin-right: 10px;">${icon}</span>
                                    <span style="flex: 1; font-size: 0.95em;">${leader.name}</span>
                                    <span style="font-weight: bold; color: #fbbf24; font-size: 0.95em;">${leader.streak_days} days</span>
                                </div>
                            `;
                        }).join('')}
                    </div>
                ` : ''}
            `;
        }).catch(error => {
            console.error('Error fetching team metrics for finished items:', error);
            goalProgress.innerHTML = `
                <h3 style="text-align: center; font-size: 1.5em; margin-bottom: 10px;">🎯 Finished Today</h3>
                <div style="text-align: center; padding: 20px 10px;">
                    <div style="font-size: 5.5em; font-weight: bold; color: #00ff88; margin-bottom: 5px; line-height: 1;">--</div>
                    <div style="font-size: 1.3em; opacity: 0.9;">💪 Team Power!</div>
                </div>
            `;
        });
    }
    updateAchievementTicker(achievements) {
        const tickerContent = document.querySelector('.ticker-content');
        if (!tickerContent || !achievements || achievements.length === 0) {
            console.log('No ticker content or achievements');
            return;
        }

        console.log('Updating ticker with achievements:', achievements);

        // Clear existing static content
        tickerContent.innerHTML = '';
        
        // Create dynamic content with double for seamless loop
        const tickerHTML = achievements.map(achievement => `
            <div class="achievement-item">
                <span class="achievement-icon">🎯</span>
                <span>${achievement}</span>
            </div>
        `).join('');
        
        // Add content twice for seamless scrolling
        tickerContent.innerHTML = tickerHTML + tickerHTML;
    }

    animateCircularProgress(targetPercent) {
        const circle = document.querySelector('.circular-progress circle:last-child');
        if (circle && circle.style) {
            const circumference = 2 * Math.PI * 90;
            const offset = circumference - (targetPercent / 100) * circumference;
            circle.style.strokeDashoffset = offset;
        }
    }

    startRealtimeUpdates() {
        // Clear existing interval if any
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // Update every 10 seconds
        this.updateInterval = setInterval(() => {
            this.loadLeaderboard();
            this.loadTicker();
        }, 10000);
        
        // Also update when window gains focus
        window.addEventListener('focus', () => {
            this.loadLeaderboard();
            this.loadTicker();
        });
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.clockInterval) {
            clearInterval(this.clockInterval);
        }
    }
}

// Manager Dashboard Handler
class ManagerDashboard {
    constructor() {
        this.api = new ProductivityAPI();
        this.charts = {};
        this.refreshInterval = null;
        this.clockInterval = null;
        this.lastRefreshTime = null;
        this.isRefreshing = false;
    }

    async init() {
        console.log('Initializing Manager Dashboard...');
        
        // Start the clock display
        this.startClock();
        
        // Initial data load
        await this.loadAllData();
        
        // Start auto-refresh
        this.startAutoRefresh();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Schedule midnight refresh
        this.scheduleMidnightRefresh();
        
        console.log('Manager Dashboard initialized');
    }

    // Add the clock functionality
    startClock() {
        const updateDateTime = () => {
            const now = this.api.getCurrentCentralTime();
            
            // Format date and time
            const dateTimeStr = now.toLocaleString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                timeZoneName: 'short'
            });
            
            // Update main datetime display
            const headerElement = document.getElementById('dashboardDateTime');
            if (headerElement) {
                headerElement.innerHTML = `
                    <i class="bi bi-clock"></i> ${dateTimeStr}
                    <small class="ms-2 badge bg-info">Central Time</small>
                `;
            }
            
            // Update page title with time
            document.title = `Manager Dashboard - ${now.toLocaleTimeString('en-US')}`;
            
            // Update shift indicator
            this.updateShiftIndicator(now);
        };
        
        // Initial update
        updateDateTime();
        
        // Update every second
        this.clockInterval = setInterval(updateDateTime, 1000);
    }

    updateShiftIndicator(currentTime) {
        const hour = currentTime.getHours();
        let shift = '';
        let shiftClass = '';
        
        if (hour >= 6 && hour < 14) {
            shift = 'Morning Shift';
            shiftClass = 'badge bg-warning text-dark';
        } else if (hour >= 14 && hour < 22) {
            shift = 'Afternoon Shift';
            shiftClass = 'badge bg-info';
        } else {
            shift = 'Night Shift';
            shiftClass = 'badge bg-dark';
        }
        
        const shiftElement = document.getElementById('currentShift');
        if (shiftElement) {
            shiftElement.className = shiftClass;
            shiftElement.textContent = shift;
        }
    }

    // Load all data with better error handling
    async loadAllData() {
        if (this.isRefreshing) {
            console.log('Refresh already in progress, skipping...');
            return;
        }
        
        this.isRefreshing = true;
        this.showRefreshingIndicator();
        
        try {
            // Load all components in parallel
            const results = await Promise.allSettled([
                this.loadDepartmentStats(),
                this.loadHourlyChart(),
                this.loadLeaderboard(),
                this.loadTeamMetrics(),
                this.loadRecentActivity(),
                this.loadAlerts()
            ]);
            
            // Check for failures
            const failures = results.filter(r => r.status === 'rejected');
            if (failures.length > 0) {
                console.error('Some components failed to load:', failures);
                this.showNotification(`Failed to load ${failures.length} components`, 'warning');
            }
            
            // Update last refresh time
            this.lastRefreshTime = new Date();
            this.updateLastRefreshTime();
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showNotification('Failed to load dashboard data', 'danger');
        } finally {
            this.isRefreshing = false;
            this.hideRefreshingIndicator();
        }
    }

    // Alias for compatibility
    async refresh() {
        await this.loadAllData();
    }

    // Enhanced auto-refresh with focus detection
    startAutoRefresh() {
        // Clear any existing interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            console.log('Auto-refresh triggered');
            this.loadAllData();
        }, 30000);
        
        // Refresh when window gains focus
        window.addEventListener('focus', () => {
            // Only refresh if last refresh was more than 10 seconds ago
            if (!this.lastRefreshTime || (Date.now() - this.lastRefreshTime.getTime()) > 10000) {
                console.log('Window focus refresh triggered');
                this.loadAllData();
            }
        });
        
        // Refresh when coming back online
        window.addEventListener('online', () => {
            console.log('Connection restored - refreshing');
            this.showNotification('Connection restored', 'success');
            this.loadAllData();
        });
    }

    // Schedule refresh at midnight
    scheduleMidnightRefresh() {
        const scheduleNext = () => {
            const now = this.api.getCurrentCentralTime();
            const tomorrow = new Date(now);
            tomorrow.setDate(tomorrow.getDate() + 1);
            tomorrow.setHours(0, 0, 5, 0); // 5 seconds after midnight
            
            const msUntilMidnight = tomorrow - now;
            
            setTimeout(() => {
                console.log('Midnight refresh triggered');
                window.location.reload(); // Full page reload at midnight
            }, msUntilMidnight);
        };
        
        scheduleNext();
    }

    // Set up additional event listeners
    setupEventListeners() {
        // Manual refresh button
        const refreshBtn = document.getElementById('refreshDashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Refreshing...';
                
                await this.loadAllData();
                
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
                this.showNotification('Dashboard refreshed', 'success');
            });
        }
    }

    // Update department stats
    async loadDepartmentStats() {
        try {
            const stats = await this.api.getDepartmentStats();
            this.updateDepartmentCards(stats);
        } catch (error) {
            console.error('Failed to load department stats:', error);
            throw error;
        }
    }

    updateDepartmentCards(departments) {
        const container = document.getElementById('departmentStats');
        if (!container) return;

        // Add animation class for smooth updates
        container.style.opacity = '0.7';
        
        container.innerHTML = departments.map(dept => `
            <div class="col-md-3 mb-3">
                <div class="stat-card h-100">
                    <div class="d-flex justify-content-between align-items-start">
                        <h4>${dept.department_name}</h4>
                        <span class="badge bg-primary">${dept.employee_count}</span>
                    </div>
                    <div class="stat-value">${dept.total_items.toLocaleString()}</div>
                    <div class="stat-label">Items Processed</div>
                    <div class="stat-details mt-2">
                        <small class="d-block">Avg: ${dept.avg_rate} items/min</small>
                        <small class="d-block">Efficiency: ${dept.efficiency || 0}%</small>
                    </div>
                    <div class="stat-progress mt-3">
                        <div class="progress" style="height: 8px;">
                            <div class="progress-bar ${dept.vs_target >= 0 ? 'bg-success' : 'bg-warning'}" 
                                 style="width: ${Math.min(100 + dept.vs_target, 100)}%"></div>
                        </div>
                        <small class="text-muted">${dept.vs_target >= 0 ? '+' : ''}${dept.vs_target}% vs target</small>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Restore opacity with transition
        setTimeout(() => {
            container.style.opacity = '1';
        }, 100);
    }

    // Load hourly chart with dynamic date
    async loadHourlyChart() {
        try {
            // Use dynamic date from API
            const hourlyData = await this.api.getHourlyProductivity();
            this.renderHourlyChart(hourlyData);
        } catch (error) {
            console.error('Failed to load hourly data:', error);
            throw error;
        }
    }

    renderHourlyChart(data) {
        const ctx = document.getElementById('hourlyChart');
        if (!ctx) return;

        if (this.charts.hourly) {
            this.charts.hourly.destroy();
        }

        // Add current time marker
        const now = this.api.getCurrentCentralTime();
        const currentHour = now.getHours();
        
        this.charts.hourly = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.hour),
                datasets: [{
                    label: 'Items Processed',
                    data: data.map(d => d.items_processed),
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.4
                }, {
                    label: 'Active Employees',
                    data: data.map(d => d.active_employees),
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#ffffff'
                        }
                    },
                    title: {
                        display: true,
                        text: `Hourly Productivity - ${now.toLocaleDateString('en-US')}`,
                        color: '#ffffff'
                    },
                    annotation: {
                        annotations: {
                            currentTime: {
                                type: 'line',
                                xMin: currentHour - 6,
                                xMax: currentHour - 6,
                                borderColor: 'rgb(255, 99, 132)',
                                borderWidth: 2,
                                label: {
                                    content: 'Now',
                                    enabled: true,
                                    position: 'top'
                                }
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#ffffff'
                        }
                    }
                }
            }
        });
    }

    // Load leaderboard with dynamic date
    async loadLeaderboard() {
        try {
            // API automatically uses current date
            const leaderboard = await this.api.getLeaderboard();
            this.updateLeaderboard(leaderboard);
            
            // Update active employee count
            const activeCount = leaderboard.filter(emp => emp.is_clocked_in).length;
            const totalCount = leaderboard.length;
            const countElement = document.getElementById('activeEmployeeCount');
            if (countElement) {
                countElement.textContent = `${activeCount}/${totalCount} Active`;
            }
        } catch (error) {
            console.error('Error loading leaderboard:', error);
            throw error;
        }
    }

    updateLeaderboard(employees) {
        const container = document.getElementById('leaderboard');
        if (!container) return;

        container.innerHTML = employees.slice(0, 10).map((emp, index) => {
            const rankBadge = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`;
            const statusIcon = emp.is_clocked_in ? '🟢' : '🔴';
            
            return `
                <tr class="${emp.is_clocked_in ? '' : 'table-secondary'}">
                    <td class="fw-bold">${rankBadge}</td>
                    <td>${statusIcon} ${emp.name}</td>
                    <td>${emp.department}</td>
                    <td>${emp.items_today.toLocaleString()}</td>
                    <td class="fw-bold">${emp.score}</td>
                    <td>${emp.items_per_minute}/min</td>
                    <td>
                        <div class="progress" style="height: 20px;">
                            <div class="progress-bar bg-success progress-bar-striped ${emp.is_clocked_in ? 'progress-bar-animated' : ''}" 
                                 style="width: ${emp.progress}%">${Math.round(emp.progress)}%</div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Other methods remain similar but with enhanced features...
    
    async loadTeamMetrics() {
        try {
            const metrics = await this.api.getTeamMetrics();
            this.updateTeamMetrics(metrics);
        } catch (error) {
            console.error('Failed to load team metrics:', error);
            throw error;
        }
    }

    updateTeamMetrics(metrics) {
        const updateElement = (id, value, animate = true) => {
            const element = document.getElementById(id);
            if (element) {
                if (animate) {
                    element.style.transition = 'all 0.3s ease';
                    element.style.transform = 'scale(0.8)';
                    setTimeout(() => {
                        element.textContent = value;
                        element.style.transform = 'scale(1)';
                    }, 150);
                } else {
                    element.textContent = value;
                }
            }
        };

        updateElement('activeEmployees', metrics.active_employees);
        updateElement('itemsToday', metrics.items_today.toLocaleString());
        updateElement('pointsToday', metrics.points_today.toLocaleString());
        
        const vsYesterday = document.getElementById('vsYesterday');
        if (vsYesterday) {
            const arrow = metrics.vs_yesterday >= 0 ? '↑' : '↓';
            const color = metrics.vs_yesterday >= 0 ? 'text-success' : 'text-danger';
            vsYesterday.innerHTML = `<span class="${color} fw-bold">${arrow} ${Math.abs(metrics.vs_yesterday)}%</span>`;
        }
    }

    async loadRecentActivity() {
        try {
            const activities = await this.api.getRecentActivities(10);
            this.updateActivityFeed(activities);
        } catch (error) {
            console.error('Failed to load activities:', error);
            throw error;
        }
    }

    updateActivityFeed(activities) {
        const container = document.getElementById('activityFeed');
        if (!container) return;

        container.innerHTML = activities.map(activity => {
            const time = this.formatRelativeTime(new Date(activity.timestamp));
            const icon = activity.type === 'clock_in' ? '🟢' : '🔴';
            return `
                <div class="activity-item fade-in">
                    <span class="activity-icon">${icon}</span>
                    <span class="activity-text">${activity.description}</span>
                    <span class="activity-time text-muted">${time}</span>
                </div>
            `;
        }).join('');
    }

    async loadAlerts() {
        try {
            const alerts = await this.api.getActiveAlerts();
            this.updateAlerts(alerts);
            
            // Update alert badge
            const alertBadge = document.getElementById('alertCount');
            if (alertBadge) {
                alertBadge.textContent = alerts.length || '';
                alertBadge.style.display = alerts.length > 0 ? 'inline' : 'none';
            }
        } catch (error) {
            console.error('Failed to load alerts:', error);
            throw error;
        }
    }

    updateAlerts(alerts) {
        const container = document.getElementById('alerts');
        if (!container) return;

        if (alerts.length === 0) {
            container.innerHTML = '<div class="alert alert-success">✅ All systems operating normally</div>';
            return;
        }

        container.innerHTML = alerts.map(alert => `
            <div class="alert alert-${alert.severity === 'critical' ? 'danger' : 'warning'} alert-dismissible fade show">
                <i class="bi bi-exclamation-triangle-fill"></i>
                <strong>${alert.title}:</strong> ${alert.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `).join('');
    }

    // Helper methods
    formatRelativeTime(date) {
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
        return date.toLocaleDateString();
    }

    updateLastRefreshTime() {
        const element = document.getElementById('lastRefreshTime');
        if (element && this.lastRefreshTime) {
            element.textContent = this.lastRefreshTime.toLocaleTimeString('en-US');
        }
    }

    showRefreshingIndicator() {
        const indicator = document.getElementById('refreshingIndicator');
        if (indicator) {
            indicator.style.display = 'inline-block';
        }
    }

    hideRefreshingIndicator() {
        const indicator = document.getElementById('refreshingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        notification.style.zIndex = '9999';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // Cleanup method
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        if (this.clockInterval) {
            clearInterval(this.clockInterval);
        }
        console.log('Manager Dashboard destroyed');
    }
}

// Employee Portal Handler
class EmployeePortal {
    constructor() {
        this.api = new ProductivityAPI();
        this.employeeId = null;
    }

    async init() {
        // Get employee ID from URL or selector
        this.employeeId = this.getEmployeeId();
        if (!this.employeeId) {
            await this.showEmployeeSelector();
            return;
        }

        await this.loadEmployeeData();
        setInterval(() => this.loadEmployeeData(), 30000);
    }

    getEmployeeId() {
        // Try to get from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('id');
    }

    async showEmployeeSelector() {
        const employees = await this.api.getEmployees();
        const container = document.getElementById('employeeSelector');
        if (!container) return;

        container.innerHTML = `
            <h3>Select Your Name</h3>
            <select class="form-select" id="employeeSelect">
                <option value="">Choose...</option>
                ${employees.map(emp => `<option value="${emp.id}">${emp.name}</option>`).join('')}
            </select>
            <button class="btn btn-primary mt-3" onclick="employeePortal.selectEmployee()">Continue</button>
        `;
    }

    selectEmployee() {
        const select = document.getElementById('employeeSelect');
        if (select && select.value) {
            window.location.href = `?id=${select.value}`;
        }
    }

    async loadEmployeeData() {
        try {
            const [stats, activities] = await Promise.all([
                this.api.getEmployeeStats(this.employeeId),
                this.api.getEmployeeActivities(this.employeeId)
            ]);

            this.updateEmployeeStats(stats);
            this.updateActivities(activities);
        } catch (error) {
            console.error('Failed to load employee data:', error);
        }
    }

    updateEmployeeStats(stats) {
        document.getElementById('employeeName').textContent = stats.name;
        document.getElementById('itemsToday').textContent = stats.items_today;
        document.getElementById('pointsToday').textContent = stats.points_today;
        document.getElementById('currentRank').textContent = `#${stats.rank}`;
        document.getElementById('itemsPerHour').textContent = 
            stats.items_per_hour || 0;

        // Update streak display
        const streakElement = document.getElementById('currentStreak');
        if (streakElement) {
            streakElement.innerHTML = stats.streak_days > 0 
                ? `🔥 ${stats.streak_days} days!`
                : 'Start your streak today!';
        }

        // Update progress bar
        const percentage = Math.round((stats.items_today / stats.daily_goal) * 100);
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.textContent = `${percentage}%`;
        }
    }

    updateActivities(activities) {
        const container = document.getElementById('recentActivities');
        if (!container) return;

        container.innerHTML = activities.map(activity => {
            const time = new Date(activity.timestamp).toLocaleTimeString();
            return `
                <li class="list-group-item">
                    <div class="d-flex justify-content-between">
                        <span>${activity.description}</span>
                        <small class="text-muted">${time}</small>
                    </div>
                </li>
            `;
        }).join('');
    }
}

// Initialize based on current page
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    
    if (path.includes('shop-floor.html')) {
        console.log('Initializing Shop Floor Display...');
        const display = new ShopFloorDisplay();
        display.init();
        
        // Clean up on page unload
        window.addEventListener('beforeunload', () => display.destroy());
    } else if (path.includes('manager.html')) {
        const dashboard = new ManagerDashboard();
        dashboard.init();
        window.managerDashboard = dashboard;
    } else if (path.includes('employee.html')) {
        window.employeePortal = new EmployeePortal();
        window.employeePortal.init();
    }
});