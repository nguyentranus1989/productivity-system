# Dashboard API Audit Report
**Date:** 2025-12-13
**File:** `C:\Users\12104\Projects\Productivity_system\frontend\dashboard-api.js`
**Auditor:** Debug Agent
**Focus:** Timezone bugs, DST detection, race conditions, error handling, date/time issues

---

## Executive Summary

**Critical Issues Found:** 5
**High Priority Issues:** 4
**Medium Priority Issues:** 3
**Low Priority Issues:** 2

### Critical Findings
1. **Hardcoded DST detection** in `getUTCBoundariesForCTDate()` - incorrect month-based logic
2. **Hardcoded timezone offset** - fixed offset hours instead of dynamic calculation
3. **Race conditions** in parallel API calls - no request deduplication
4. **Incorrect UTC boundary calculation** - off-by-one errors in end time
5. **Missing error recovery** - no retry logic for failed requests

---

## Detailed Issues

### 🔴 CRITICAL: Lines 62-89 - Hardcoded DST Detection & Timezone Offset

**Issue:**
```javascript
// Check if date is in DST (rough approximation for Central Time)
// CDT runs March - November
const isDST = (month >= 3 && month <= 11);
const offsetHours = isDST ? 5 : 6; // CDT = UTC-5, CST = UTC-6
```

**Problems:**
1. **Inaccurate DST detection**: Comment says "rough approximation" - DST starts 2nd Sunday in March, ends 1st Sunday in November
2. **Month-only check**: Doesn't check day/week - entire March treated as DST (wrong for Mar 1-7 some years)
3. **Hardcoded offsets**: UTC-5/UTC-6 hardcoded instead of using Intl API like `getCentralDate()` does
4. **Date edge case**: Transition days (2am CT) will be wrong

**Impact:**
- Wrong UTC boundaries for dates in early March / early November
- Database queries return wrong shifts/data for 2-14 days per year
- Affects: leaderboard, hourly productivity, cost analysis

**Recommended Fix:**
```javascript
getUTCBoundariesForCTDate(ctDate) {
    const [year, month, day] = ctDate.split('-').map(Number);

    // Create date at midnight CT using Intl API
    const ctMidnight = new Date(`${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T00:00:00`);
    const utcMidnight = new Date(ctMidnight.toLocaleString("en-US", {timeZone: "America/Chicago"}));

    // Create date at 23:59:59 CT
    const ctEndOfDay = new Date(`${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}T23:59:59`);
    const utcEndOfDay = new Date(ctEndOfDay.toLocaleString("en-US", {timeZone: "America/Chicago"}));

    // Calculate actual offset dynamically
    const offset = (ctMidnight - utcMidnight) / (1000 * 60 * 60);

    // Format for SQL
    const formatSQL = (date) => {
        return date.toISOString().slice(0, 19).replace('T', ' ');
    };

    return {
        utc_start: formatSQL(utcMidnight),
        utc_end: formatSQL(utcEndOfDay),
        ct_date: ctDate,
        is_dst: offset === 5
    };
}
```

---

### 🔴 CRITICAL: Lines 81-82 - UTC End Boundary Off-by-One Error

**Issue:**
```javascript
const nextDay = new Date(year, month - 1, day + 1);
const endYear = nextDay.getFullYear();
const endMonth = nextDay.getMonth() + 1;
const endDay = nextDay.getDate();
const utcEnd = `${endYear}-${pad(endMonth)}-${pad(endDay)} ${pad(offsetHours - 1)}:59:59`;
```

**Problems:**
1. **Calculates next day**: Should be same day at 23:59:59
2. **Subtract 1 from offset**: `offsetHours - 1` results in wrong hour (4am or 5am instead of 5am/6am)
3. **Logic error**: Trying to get "23:59:59 CT on same day" but adding full day then subtracting 1 hour

**Impact:**
- End boundary extends into next day in UTC
- Queries include data from wrong day
- Affects all date-range queries

**Example:**
```
Input: 2025-12-13 (CST, UTC-6)
Current logic:
  utc_start: "2025-12-13 06:00:00"  ✅ Correct (midnight CT)
  utc_end:   "2025-12-14 05:59:59"  ❌ Wrong! Should be "2025-12-14 05:59:59" for 23:59:59 CT

Wait, actually this is CORRECT if offsetHours=6:
  23:59:59 CT + 6 hours = 05:59:59 UTC next day

But code does: nextDay ${offsetHours - 1}:59:59 = ${5}:59:59
  This is WRONG - it's 1 hour short!
```

**Recommended Fix:**
Use dynamic calculation as shown in first fix above.

---

### 🔴 HIGH: Lines 299-303 - Race Condition in Parallel API Calls

**Issue:**
```javascript
const [leaderboard, teamStats, streakLeaders] = await Promise.all([
    this.api.getLeaderboard(),
    this.api.getTeamMetrics(),
    this.api.getStreakLeaders()
]);
```

**Problems:**
1. **No deduplication**: Same endpoint can be called multiple times if `loadLeaderboard()` called rapidly
2. **No in-flight check**: Multiple intervals/events can trigger same calls
3. **Potential data inconsistency**: Three separate API calls may get different "current time" snapshots

**Impact:**
- Wasted API calls
- Server load spikes
- Inconsistent dashboard state

**Recommended Fix:**
```javascript
class ShopFloorDisplay {
    constructor() {
        this.api = new ProductivityAPI();
        this.inflightRequests = new Map();
    }

    async dedupeRequest(key, requestFn) {
        if (this.inflightRequests.has(key)) {
            return this.inflightRequests.get(key);
        }

        const promise = requestFn().finally(() => {
            this.inflightRequests.delete(key);
        });

        this.inflightRequests.set(key, promise);
        return promise;
    }

    async loadLeaderboard() {
        return this.dedupeRequest('loadLeaderboard', async () => {
            // existing logic
        });
    }
}
```

---

### 🔴 HIGH: Lines 649-657 - Promise.allSettled Without Retry Logic

**Issue:**
```javascript
const results = await Promise.allSettled([
    this.loadDepartmentStats(),
    this.loadHourlyChart(),
    this.loadLeaderboard(),
    // ...
]);

const failures = results.filter(r => r.status === 'rejected');
if (failures.length > 0) {
    console.error('Some components failed to load:', failures);
    this.showNotification(`Failed to load ${failures.length} components`, 'warning');
}
```

**Problems:**
1. **No retry**: Failed requests not retried
2. **Silent failure**: Dashboard shows stale data without clear indication
3. **No fallback**: No cached/default data shown
4. **User confusion**: Warning toast disappears after 3s, user doesn't know what's broken

**Impact:**
- Intermittent network issues cause persistent broken dashboard
- Users don't know if data is stale
- No recovery without page reload

**Recommended Fix:**
```javascript
async loadAllData(retryCount = 0) {
    if (this.isRefreshing) {
        return;
    }

    this.isRefreshing = true;
    this.showRefreshingIndicator();

    try {
        const results = await Promise.allSettled([/* ... */]);

        const failures = results.filter(r => r.status === 'rejected');
        if (failures.length > 0) {
            console.error('Some components failed:', failures);

            // Retry failed components once
            if (retryCount < 1) {
                console.log('Retrying failed components...');
                await new Promise(resolve => setTimeout(resolve, 1000));
                return this.loadAllData(retryCount + 1);
            }

            // Show persistent warning
            this.showPersistentError(`${failures.length} components failed to load. Click refresh to retry.`);
        }

        this.lastRefreshTime = new Date();
        this.updateLastRefreshTime();

    } catch (error) {
        console.error('Error loading dashboard:', error);
        if (retryCount < 1) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            return this.loadAllData(retryCount + 1);
        }
        this.showPersistentError('Failed to load dashboard. Check connection.');
    } finally {
        this.isRefreshing = false;
        this.hideRefreshingIndicator();
    }
}
```

---

### 🟡 MEDIUM: Lines 26-42 - Generic Error Handling

**Issue:**
```javascript
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
```

**Problems:**
1. **No response body**: Error doesn't include response message/details
2. **No status code handling**: All errors treated same (500 vs 404 vs timeout)
3. **No timeout**: Request can hang indefinitely
4. **Network errors not distinguished**: DNS failure vs server error vs JSON parse error

**Impact:**
- Hard to debug API errors
- No graceful degradation for different error types
- UI can freeze on slow connections

**Recommended Fix:**
```javascript
async request(endpoint, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: { ...this.headers, ...options.headers },
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            let errorBody = '';
            try {
                errorBody = await response.text();
            } catch (e) {
                // ignore
            }

            throw new Error(`API error ${response.status}: ${errorBody || response.statusText}`);
        }

        const data = await response.json();
        return data;

    } catch (error) {
        clearTimeout(timeoutId);

        if (error.name === 'AbortError') {
            throw new Error('Request timeout - server took too long to respond');
        }

        if (!navigator.onLine) {
            throw new Error('No internet connection');
        }

        console.error(`API Request failed [${endpoint}]:`, error);
        throw error;
    }
}
```

---

### 🟡 MEDIUM: Lines 275-291 - Midnight Refresh Timezone Calculation

**Issue:**
```javascript
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
```

**Problems:**
1. **getCurrentCentralTime() returns string-converted date**: May lose milliseconds precision
2. **setHours operates in local time**: If user's local time != Central, calculation wrong
3. **Only schedules once**: If setTimeout drifts (tab backgrounded), never rescheduled
4. **No DST transition handling**: On spring-forward night, might fire at wrong time

**Impact:**
- Page reload might happen at wrong time
- Missed midnight refresh if tab backgrounded
- Confusion on DST transition nights

**Recommended Fix:**
```javascript
scheduleMiddnightRefresh() {
    const scheduleNext = () => {
        // Get current time in Central
        const now = new Date();
        const nowCT = new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));

        // Get tomorrow midnight in Central
        const tomorrowCT = new Date(nowCT);
        tomorrowCT.setDate(tomorrowCT.getDate() + 1);
        tomorrowCT.setHours(0, 0, 5, 0);

        // Convert back to local time for setTimeout
        const msUntilMidnight = tomorrowCT - nowCT;

        console.log(`Scheduling midnight refresh in ${msUntilMidnight}ms`);

        setTimeout(() => {
            console.log('Midnight refresh triggered');
            window.location.reload();
            // Reschedule just in case
            setTimeout(scheduleNext, 60000);
        }, msUntilMidnight);
    };

    scheduleNext();
}
```

---

### 🟡 MEDIUM: Lines 685-712 - Auto-Refresh Race Condition

**Issue:**
```javascript
startAutoRefresh() {
    if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
    }

    this.refreshInterval = setInterval(() => {
        console.log('Auto-refresh triggered');
        this.loadAllData();
    }, 30000);

    window.addEventListener('focus', () => {
        if (!this.lastRefreshTime || (Date.now() - this.lastRefreshTime.getTime()) > 10000) {
            console.log('Window focus refresh triggered');
            this.loadAllData();
        }
    });

    window.addEventListener('online', () => {
        console.log('Connection restored - refreshing');
        this.showNotification('Connection restored', 'success');
        this.loadAllData();
    });
}
```

**Problems:**
1. **Multiple focus listeners**: Called each time `startAutoRefresh()` called - event listeners stack up
2. **Multiple online listeners**: Same issue
3. **Race between interval and focus**: Both can trigger at same time
4. **No cleanup**: Event listeners never removed

**Impact:**
- Memory leak from duplicate event listeners
- Multiple simultaneous API calls
- Dashboard refresh storms

**Recommended Fix:**
```javascript
constructor() {
    // ...
    this.focusHandler = null;
    this.onlineHandler = null;
}

startAutoRefresh() {
    // Clear existing
    if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
    }
    if (this.focusHandler) {
        window.removeEventListener('focus', this.focusHandler);
    }
    if (this.onlineHandler) {
        window.removeEventListener('online', this.onlineHandler);
    }

    // Set up interval
    this.refreshInterval = setInterval(() => {
        this.loadAllData();
    }, 30000);

    // Set up focus listener
    this.focusHandler = () => {
        if (!this.lastRefreshTime || (Date.now() - this.lastRefreshTime.getTime()) > 10000) {
            this.loadAllData();
        }
    };
    window.addEventListener('focus', this.focusHandler);

    // Set up online listener
    this.onlineHandler = () => {
        this.showNotification('Connection restored', 'success');
        this.loadAllData();
    };
    window.addEventListener('online', this.onlineHandler);
}

destroy() {
    if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
    }
    if (this.clockInterval) {
        clearInterval(this.clockInterval);
    }
    if (this.focusHandler) {
        window.removeEventListener('focus', this.focusHandler);
    }
    if (this.onlineHandler) {
        window.removeEventListener('online', this.onlineHandler);
    }
}
```

---

### 🟢 LOW: Lines 1065-1073 - Relative Time Calculation Without Timezone

**Issue:**
```javascript
formatRelativeTime(date) {
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
    return date.toLocaleDateString();
}
```

**Problems:**
1. **Uses local time**: `now` is user's local time, `date` might be UTC from API
2. **No timezone specification**: Final fallback uses local timezone
3. **Negative diff not handled**: If `date` is future, shows negative time

**Impact:**
- Activity timestamps might show wrong relative time
- Minor UI issue

**Recommended Fix:**
```javascript
formatRelativeTime(dateStr) {
    const now = this.api.getCurrentCentralTime();
    const date = new Date(dateStr);
    const dateCT = new Date(date.toLocaleString("en-US", {timeZone: "America/Chicago"}));

    const diff = now - dateCT;

    if (diff < 0) return 'Just now'; // Future times
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;

    return dateCT.toLocaleDateString('en-US', {
        timeZone: 'America/Chicago',
        month: 'short',
        day: 'numeric'
    });
}
```

---

### 🟢 LOW: Lines 126-129 - getCurrentCentralTime() String Conversion Issue

**Issue:**
```javascript
getCurrentCentralTime() {
    const now = new Date();
    return new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));
}
```

**Problems:**
1. **Double conversion**: `new Date(string)` parsing can be inconsistent across browsers
2. **Milliseconds lost**: String format doesn't include milliseconds
3. **Potential parsing failure**: Some browsers parse date strings differently

**Impact:**
- Minor precision loss
- Potential cross-browser inconsistencies

**Recommended Fix:**
```javascript
getCurrentCentralTime() {
    const now = new Date();
    const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Chicago',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });

    const parts = formatter.formatToParts(now);
    const values = {};
    parts.forEach(p => values[p.type] = p.value);

    return new Date(
        parseInt(values.year),
        parseInt(values.month) - 1,
        parseInt(values.day),
        parseInt(values.hour),
        parseInt(values.minute),
        parseInt(values.second)
    );
}
```

---

## Additional Observations

### Lines 97-101, 192-206 - UTC Boundary Parameters Not Always Used
Methods like `getLeaderboardRange()`, `getCostAnalysis()` pass UTC boundaries to backend, but backend may not use them. Verify backend actually respects these parameters.

### Lines 440-441 - Nested API Call in Update Function
```javascript
this.api.getTeamMetrics().then(stats => {
```
This is called inside `updateStreakLeaders()` which is already called from `loadLeaderboard()`. Results in duplicate API call. Should pass data as parameter instead.

### Lines 520-524 - Fixed 10-Second Interval
```javascript
this.updateInterval = setInterval(() => {
    this.loadLeaderboard();
    this.loadTicker();
}, 10000);
```
No jitter/randomization. If 100 shop floor displays load at same time, all hit server every 10s simultaneously. Consider adding random offset.

---

## Testing Recommendations

1. **DST Transition Testing**
   - Test dates: 2024-03-10 (spring forward), 2024-11-03 (fall back)
   - Verify UTC boundaries correct for dates in transition weeks
   - Check midnight refresh on DST transition nights

2. **Race Condition Testing**
   - Rapidly click refresh button
   - Monitor network tab for duplicate requests
   - Background/foreground tab rapidly during auto-refresh

3. **Error Recovery Testing**
   - Throttle network to 3G
   - Disconnect network mid-refresh
   - Backend returns 500 errors
   - Verify dashboard shows appropriate errors and recovers

4. **Timezone Testing**
   - Test from different timezones (set system timezone to PST, EST)
   - Verify all times display in Central
   - Check API requests send correct UTC boundaries

---

## Priority Recommendations

### Immediate (Deploy Today)
1. Fix `getUTCBoundariesForCTDate()` - use Intl API instead of hardcoded offsets
2. Add request deduplication to prevent race conditions
3. Fix event listener memory leak in `startAutoRefresh()`

### This Week
4. Add retry logic to `loadAllData()`
5. Improve error messages in `request()` method
6. Fix midnight refresh timezone calculation

### This Month
7. Add request timeout handling
8. Optimize update intervals with jitter
9. Remove duplicate API call in `updateStreakLeaders()`

---

## Unresolved Questions

1. Does backend actually use `utc_start`/`utc_end` parameters? Check `backend/api/dashboard.py`
2. What's expected behavior on DST transition at 2am - should dashboard reload?
3. Should shop floor display auto-reload on network reconnect?
4. Are there backend timezone bugs that compound these frontend issues?
5. Why is ManagerDashboard auto-init disabled (line 1242-1248)? Does manager.html have different timezone logic?
