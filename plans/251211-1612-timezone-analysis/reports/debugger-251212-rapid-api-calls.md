# API Call Frequency Issue - Manager Dashboard

**Date:** 2025-12-12
**Reporter:** System Analysis
**Severity:** High - Performance Impact
**Status:** Root Cause Identified

## Executive Summary

Manager dashboard making API calls every 2-6 seconds instead of intended 60-second intervals. Issue caused by **TWO separate initialization systems** running simultaneously, plus navigation triggering additional loads.

**Root Causes:**
1. Dual initialization: `dashboard-api.js` ManagerDashboard class + inline manager.html initialization both active
2. `showSection('dashboard')` navigation calls `loadDashboardData()` without debounce check
3. Both systems set independent 30s/60s intervals

**Impact:** 10-30x increased API load, unnecessary database queries, potential performance degradation

---

## Technical Analysis

### Issue 1: Dual Initialization System

**dashboard-api.js (Lines 548-1128):**
```javascript
class ManagerDashboard {
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            console.log('Auto-refresh triggered');
            this.loadAllData();
        }, 30000);  // 30 SECONDS
    }
}

// Auto-init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    if (path.includes('manager.html')) {
        const dashboard = new ManagerDashboard();
        dashboard.init();
        window.managerDashboard = dashboard;
    }
});
```

**manager.html (Lines 2342-2403):**
```javascript
// SECOND initialization - also runs on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();  // Immediate load

    refreshInterval = setInterval(() => {
        if (shouldRefresh()) loadDashboardData();
    }, 60000);  // 60 SECONDS
});
```

**Result:** Both systems initialize, creating TWO independent refresh loops (30s + 60s).

### Issue 2: Navigation-Triggered Loads

**manager.html Lines 5064-5098:**
```javascript
function showSection(sectionName) {
    if (sectionName === 'dashboard') {
        loadDashboardData();  // NO DEBOUNCE CHECK
    }
    // ...
}
```

**Navigation links (Line 24, 28, 32, 523):**
```html
<a onclick="showSection('dashboard')">
```

**Result:** Every navigation to dashboard section triggers immediate load, bypassing debounce/lock in `loadDashboardData()` function scope.

### Issue 3: Health Monitoring Interval

**manager.html Lines 1801-1808:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    updateSystemHealth();
    setInterval(() => {
        if (shouldRefresh()) updateSystemHealth();
    }, 60000);  // Additional API calls
});
```

### Issue 4: Bottleneck Section Interval

**manager.html Lines 4492-4498:**
```javascript
setInterval(() => {
    if (shouldRefresh() &&
        document.getElementById('bottleneck-section')?.classList.contains('active')) {
        loadBottleneckData();
    }
}, 60000);
```

---

## Evidence Timeline

### Intervals Created on Page Load:
1. **dashboard-api.js ManagerDashboard:** 30s interval → `loadAllData()` (Lines 689-699)
2. **manager.html main init:** 60s interval → `loadDashboardData()` (Lines 2401-2403)
3. **manager.html health monitoring:** 60s interval → `updateSystemHealth()` (Lines 1806-1808)
4. **manager.html bottleneck:** 60s interval → `loadBottleneckData()` (Lines 4492-4498)
5. **manager.html clock:** 1s interval → `updateClock()` (Line 2371)

### API Call Frequency Calculation:
- ManagerDashboard calls: every 30s
- Inline system calls: every 60s
- Navigation clicks: on-demand (bypasses debounce)
- **Worst case:** 30s interval triggers, plus nav click = 2-6s observed frequency

---

## Debounce Mechanism Analysis

**manager.html Lines 1873-1896:**
```javascript
let lastDashboardLoad = 0;
let dashboardLoadInProgress = false;
const DASHBOARD_DEBOUNCE_MS = 10000;

async function loadDashboardData() {
    if (dashboardLoadInProgress) {
        console.log('Dashboard load already in progress, skipping');
        return;
    }

    const now = Date.now();
    if (now - lastDashboardLoad < DASHBOARD_DEBOUNCE_MS) {
        console.log('Dashboard load debounced (too soon)');
        return;
    }
    // ... load logic
}
```

**Problem:** Debounce only applies to `loadDashboardData()` function. ManagerDashboard class uses separate `loadAllData()` method - **not covered by debounce**.

---

## Root Cause Summary

| Component | Interval | Function | Status |
|-----------|----------|----------|--------|
| dashboard-api.js ManagerDashboard | 30s | `loadAllData()` | **ACTIVE** |
| manager.html inline init | 60s | `loadDashboardData()` | **ACTIVE** |
| manager.html health | 60s | `updateSystemHealth()` | Active (needed) |
| manager.html bottleneck | 60s | `loadBottleneckData()` | Active (conditional) |
| Navigation onclick | on-demand | `loadDashboardData()` | **BYPASSES DEBOUNCE** |

**Conflict:** Two separate dashboard initialization systems + unbounded navigation calls.

---

## API Endpoints Affected

### Called by BOTH systems:
- `/api/dashboard/leaderboard`
- `/api/dashboard/departments/stats`
- `/api/dashboard/analytics/team-metrics`
- `/api/dashboard/activities/recent`
- `/api/dashboard/alerts/active`
- `/api/dashboard/analytics/hourly`

### Additional calls from ManagerDashboard class:
- `/api/dashboard/clock-times/today`
- Various other endpoints

**Estimated API load increase:** 10-30x normal rate during active use.

---

## Recommended Solutions

### Option 1: Disable dashboard-api.js Auto-Init (Quick Fix)
**File:** `frontend/dashboard-api.js` Lines 1235-1252

**Change:**
```javascript
// DISABLE auto-initialization for manager.html
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path.includes('shop-floor.html')) {
        // Keep shop floor init
        const display = new ShopFloorDisplay();
        display.init();
    }
    // REMOVE manager.html init - uses inline system instead
    // else if (path.includes('manager.html')) {
    //     const dashboard = new ManagerDashboard();
    //     dashboard.init();
    //     window.managerDashboard = dashboard;
    // }
});
```

**Impact:** Eliminates dual initialization, keeps inline 60s interval.

### Option 2: Fix showSection Navigation (Required)
**File:** `frontend/manager.html` Lines 5084-5085

**Change:**
```javascript
if (sectionName === 'dashboard') {
    // Don't call immediately - let interval handle refresh
    // OR call with debounce awareness:
    if (Date.now() - lastDashboardLoad >= DASHBOARD_DEBOUNCE_MS) {
        loadDashboardData();
    }
}
```

**Impact:** Prevents navigation-triggered rapid calls.

### Option 3: Consolidate to Single System (Long-term)
- **Either:** Use dashboard-api.js ManagerDashboard class exclusively
- **Or:** Keep inline manager.html initialization
- **NOT BOTH**

---

## Testing Verification

### Before Fix:
1. Open browser DevTools Network tab
2. Load manager.html
3. Filter for `/api/` calls
4. Observe calls every 2-6 seconds

### After Fix:
1. Apply Option 1 + Option 2
2. Reload manager.html
3. Verify calls occur every 60 seconds only
4. Navigate between sections - verify debounce works

---

## Open Questions

1. **Why is dashboard-api.js ManagerDashboard class not used?**
   - Class exists with full implementation but manager.html uses inline code instead
   - Duplication of logic suggests refactoring needed

2. **Should ManagerDashboard class replace inline code?**
   - Class has better structure, error handling, notification system
   - Inline code has same functionality but less organized

3. **What's the intended refresh rate?**
   - dashboard-api.js uses 30s
   - manager.html uses 60s
   - Need product requirement clarification

---

## Files Analyzed

- `frontend/dashboard-api.js` (1253 lines)
- `frontend/manager.html` (5100+ lines)

**Log Locations:**
- Browser console shows dual "Initializing..." messages
- Network tab shows rapid API call frequency
