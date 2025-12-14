# Performance Analysis: frontend/manager.html

**Date:** 2025-12-13
**Reviewer:** Code Reviewer Agent
**File:** `frontend/manager.html` (6,032 lines, 325KB)
**Focus:** JavaScript performance optimization

---

## Executive Summary

Analysis of manager.html reveals **12 critical performance issues** causing unnecessary API overhead, DOM thrashing, and redundant computations. Most impactful: sequential API calls in loadDashboardData (lines 2619-2652), duplicate unmapped-users fetches (lines 4532, 4608), and full table rebuilds every 2min. Combined overhead: **~15-20 API calls every 2 minutes + excessive DOM manipulation**.

**Quick wins:** Parallelize 5 sequential calls (save 2-3s), cache unmapped users (eliminate duplicate fetches), implement virtual scrolling for large tables.

---

## Critical Issues (HIGH PRIORITY)

### 1. Sequential API Calls in Dashboard Load
**Lines:** 2619-2652
**Impact:** HIGH
**Description:** loadDashboardData makes 6 API calls sequentially instead of parallel. Each call waits for previous to complete.

```javascript
// CURRENT (SEQUENTIAL - SLOW)
const leaderboard = await api.getLeaderboard(currentDate);
const departmentStats = await api.getDepartmentStats(currentDate);
const teamMetrics = await api.getTeamMetrics();
const recentActivities = await api.getRecentActivities(10);
const alerts = await api.getActiveAlerts();
await updateProductivityChart(); // Another API call inside
```

**Problem:** If each call takes 200ms, total = 1200ms. Parallel would be ~200ms.

**Fix:**
```javascript
// PARALLEL (FAST)
const [leaderboard, departmentStats, teamMetrics, recentActivities, alerts] =
  await Promise.all([
    api.getLeaderboard(currentDate),
    api.getDepartmentStats(currentDate),
    api.getTeamMetrics(),
    api.getRecentActivities(10),
    api.getActiveAlerts()
  ]);
// Handle updateProductivityChart separately or include in Promise.all
```

**Effort:** 15 minutes
**Performance Gain:** 70-80% faster dashboard load (1200ms → 200-300ms)

---

### 2. Duplicate Unmapped Users Fetch
**Lines:** 4532, 4608
**Impact:** HIGH
**Description:** mapEmployee() and openSmartMapping() both fetch `/api/dashboard/unmapped-users` independently. Same data fetched twice when mapping employees.

```javascript
// Line 4532 - mapEmployee
const unmappedData = await fetch(`${API_BASE}/api/dashboard/unmapped-users`, {...});

// Line 4608 - openSmartMapping (called from mapping workflow)
const unmappedData = await fetch(`${API_BASE}/api/dashboard/unmapped-users`, {...});
```

**Fix:** Implement caching with 5-minute TTL:
```javascript
let unmappedUsersCache = null;
let unmappedUsersCacheTime = 0;
const CACHE_TTL = 300000; // 5 minutes

async function getUnmappedUsers() {
  const now = Date.now();
  if (unmappedUsersCache && (now - unmappedUsersCacheTime) < CACHE_TTL) {
    return unmappedUsersCache;
  }

  const response = await fetch(`${API_BASE}/api/dashboard/unmapped-users`, {
    headers: {'X-API-Key': 'dev-api-key-123'}
  });
  unmappedUsersCache = await response.json();
  unmappedUsersCacheTime = now;
  return unmappedUsersCache;
}
```

**Effort:** 20 minutes
**Performance Gain:** Eliminates 50% of unmapped-users API calls

---

### 3. Full DOM Rebuild in updateDepartmentCards
**Lines:** 2770-2826
**Impact:** HIGH
**Description:** Every 2 minutes (refresh interval), updateDepartmentCards clears entire container and rebuilds all cards from scratch, even if data unchanged.

```javascript
// Line 2783 - DESTROYS ALL DOM
container.innerHTML = '';

stats.forEach(dept => {
  const card = document.createElement('div');
  card.innerHTML = `...massive template...`;  // Lines 2796-2823
  container.appendChild(card);
});
```

**Problem:**
- Forces layout recalculation for entire grid
- Destroys event listeners (if any)
- Causes visual flicker
- Inefficient for 6-10 department cards

**Fix:** Targeted updates with data diffing:
```javascript
function updateDepartmentCards(stats) {
  const container = document.getElementById('departmentGrid');
  const existingCards = new Map();

  // Index existing cards
  container.querySelectorAll('.department-card').forEach(card => {
    const name = card.dataset.deptName;
    existingCards.set(name, card);
  });

  stats.forEach(dept => {
    const existing = existingCards.get(dept.department_name);
    if (existing) {
      // UPDATE ONLY CHANGED VALUES
      updateCardValues(existing, dept);
    } else {
      // CREATE NEW
      createDepartmentCard(dept);
    }
  });
}
```

**Effort:** 45 minutes
**Performance Gain:** 60-70% faster updates, eliminates flicker

---

### 4. N+1 Pattern in Date Range View
**Lines:** 5115-5152
**Impact:** HIGH
**Description:** loadTodayComparison iterates rangeLeaderboard and fetches today's data ONCE, but then does O(n) DOM lookups inside forEach loop.

```javascript
// Line 5117 - Single fetch (GOOD)
const todayData = await api.getLeaderboard(dashboardData.startDate || api.getCentralDate());

// Lines 5119-5149 - O(n) DOM operations (BAD)
rangeLeaderboard.forEach(emp => {
  const todayEmp = todayData.find(t => t.name === emp.name);  // OK
  const todayCell = document.getElementById(`today-${emp.id}`);  // DOM lookup per iteration
  const trendCell = document.getElementById(`trend-${emp.id}`);   // DOM lookup per iteration

  if (todayEmp && todayCell) {
    todayCell.innerHTML = `<strong>${todayItems}</strong>`;  // Triggers reflow
    // ... more innerHTML updates
  }
});
```

**Problem:**
- 20 employees × 2 getElementById calls = 40 DOM queries
- Each innerHTML triggers layout recalculation

**Fix:** Batch DOM updates with DocumentFragment:
```javascript
async function loadTodayComparison(rangeLeaderboard) {
  const todayData = await api.getLeaderboard(dashboardData.startDate || api.getCentralDate());

  // CREATE INDEX
  const todayMap = new Map(todayData.map(emp => [emp.name, emp]));

  // BATCH UPDATES
  const updates = [];
  rangeLeaderboard.forEach(emp => {
    const todayEmp = todayMap.get(emp.name);
    if (todayEmp) {
      updates.push({
        todayId: `today-${emp.id}`,
        trendId: `trend-${emp.id}`,
        todayItems: todayEmp.items_today || 0,
        avgItems: emp.avg_daily_items
      });
    }
  });

  // SINGLE REFLOW
  requestAnimationFrame(() => {
    updates.forEach(u => {
      document.getElementById(u.todayId).innerHTML = `<strong>${u.todayItems}</strong>`;
      // ... update trend
    });
  });
}
```

**Effort:** 30 minutes
**Performance Gain:** 3-5x faster for 20+ employees

---

### 5. Inefficient Polling in Recalculation Modal
**Lines:** 2338, 2347-2443
**Impact:** MEDIUM
**Description:** Recalculation progress polling runs every 1 second without backoff or optimization.

```javascript
// Line 2338 - Aggressive 1s polling
recalcPollInterval = setInterval(pollRecalculationStatus, 1000);

async function pollRecalculationStatus() {
  const response = await fetch(`${API_BASE}/api/system/recalculate/status/${recalcJobId}`, {...});
  // ... update UI
}
```

**Problem:**
- 1 API call per second during recalculation (could run 60+ seconds)
- No exponential backoff
- Continues even if API errors
- Doesn't stop on tab visibility change

**Fix:** Implement adaptive polling:
```javascript
let pollDelay = 1000;
const MAX_DELAY = 5000;

async function pollRecalculationStatus() {
  try {
    const response = await fetch(...);
    const data = await response.json();

    updateRecalcUI(data);

    if (data.status === 'completed' || data.status === 'failed') {
      clearInterval(recalcPollInterval);
      return;
    }

    // ADAPTIVE: Increase delay after initial burst
    if (data.progress < 20) pollDelay = 1000;  // Fast updates at start
    else if (data.progress < 80) pollDelay = 2000;  // Slower mid-way
    else pollDelay = 3000;  // Slowest near end

  } catch (error) {
    console.error('Poll error:', error);
    pollDelay = Math.min(pollDelay * 1.5, MAX_DELAY);  // Backoff on error
  }

  // Reschedule with new delay
  setTimeout(pollRecalculationStatus, pollDelay);
}
```

**Effort:** 25 minutes
**Performance Gain:** 40-60% fewer API calls during recalculation

---

## High Priority Issues

### 6. Missing Debounce on Search Inputs
**Lines:** 1714, 4544, 4557, 5318
**Impact:** MEDIUM
**Description:** Multiple search filter functions (filterPopupEmployees, filterConnecteamList, filterPodfactoryList, filterAvailableWorkers) execute on every keystroke without debounce.

```javascript
// Line 1206 - Executes filterPopupEmployees on EVERY keypress
oninput="filterPopupEmployees()"
```

**Problem:** User types "John Smith" = 10 keystrokes × filter execution. For 100+ employees, this causes jank.

**Fix:** Add debounce utility:
```javascript
function debounce(func, delay) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), delay);
  };
}

const debouncedFilter = debounce(filterPopupEmployees, 300);

// In HTML:
oninput="debouncedFilter()"
```

**Effort:** 30 minutes (implement utility + update 4 search inputs)
**Performance Gain:** Eliminates 80-90% of redundant filter operations

---

### 7. Redundant querySelectorAll in showLoadingStates
**Lines:** 2694-2698
**Impact:** MEDIUM
**Description:** showLoadingStates queries all `.metric-change` elements and updates them, called every dashboard refresh.

```javascript
function showLoadingStates() {
  document.querySelectorAll('.metric-change').forEach(el => {
    el.innerHTML = '<span class="loading"></span>';
  });
}
```

**Problem:** querySelectorAll is slow. Called frequently (every 2 min auto-refresh + manual refreshes).

**Fix:** Cache selectors during init:
```javascript
let metricChangeElements = [];

// On page load
document.addEventListener('DOMContentLoaded', () => {
  metricChangeElements = Array.from(document.querySelectorAll('.metric-change'));
});

function showLoadingStates() {
  metricChangeElements.forEach(el => {
    el.innerHTML = '<span class="loading"></span>';
  });
}
```

**Effort:** 10 minutes
**Performance Gain:** 5-10x faster loading state updates

---

### 8. Inefficient Name Similarity Calculation
**Lines:** 4580-4603
**Impact:** MEDIUM
**Description:** calculateNameSimilarity uses Dice coefficient with bigram generation. Called for EVERY unmapped Connecteam user during smart mapping (potentially 50+ users).

```javascript
window.openSmartMapping = async function(employeeId, employeeName) {
  const unmappedData = await fetch(...);

  // Line 4613 - CALCULATES SIMILARITY FOR ALL USERS
  const usersWithScores = unmappedData.connecteam_users.map(user => ({
    ...user,
    similarity: calculateNameSimilarity(employeeName, user.name)  // O(n²) string ops
  })).sort((a, b) => b.similarity - a.similarity);
}
```

**Problem:**
- Bigram generation is O(n²) for string length
- Runs synchronously on main thread
- Blocks UI if 100+ users

**Fix:**
1. Limit calculation to top N candidates using simple heuristics first
2. Use Web Worker for heavy computation (if >50 users)
3. Cache results per employeeName

```javascript
// Simple pre-filter
const candidates = unmappedData.connecteam_users.filter(user => {
  const nameLower = employeeName.toLowerCase();
  const userLower = user.name.toLowerCase();
  const words = nameLower.split(' ');

  // Quick check: does user name contain any word from employee name?
  return words.some(word => userLower.includes(word));
});

// Only calculate similarity for filtered candidates (likely 5-10 instead of 50+)
const usersWithScores = candidates.map(user => ({...}));
```

**Effort:** 35 minutes
**Performance Gain:** 70-90% faster smart mapping modal

---

## Medium Priority Issues

### 9. Table Rebuilds in Cost Analysis
**Lines:** 5664-5809
**Impact:** MEDIUM
**Description:** updateCostTable rebuilds entire table HTML on filter change, even though only visibility needs updating.

```javascript
function updateCostTable() {
  const tbody = document.getElementById('costTableBody');
  tbody.innerHTML = ''; // DESTROYS EVERYTHING

  filteredData.forEach(emp => {
    const row = document.createElement('tr');
    row.innerHTML = `...large template...`; // Lines 5674-5799
    tbody.appendChild(row);
  });
}
```

**Fix:** Use CSS classes for filtering instead of DOM manipulation:
```javascript
// On initial load, add data attributes
row.dataset.department = emp.department;
row.dataset.name = emp.name.toLowerCase();

// On filter
function updateCostTable() {
  const rows = document.querySelectorAll('#costTableBody tr');
  const searchTerm = document.getElementById('costSearchInput').value.toLowerCase();
  const deptFilter = document.getElementById('costDeptFilter').value;

  rows.forEach(row => {
    const matchesSearch = !searchTerm || row.dataset.name.includes(searchTerm);
    const matchesDept = !deptFilter || row.dataset.department === deptFilter;
    row.style.display = (matchesSearch && matchesDept) ? '' : 'none';
  });
}
```

**Effort:** 40 minutes
**Performance Gain:** 90-95% faster filtering (no DOM rebuilds)

---

### 10. Redundant Clock Updates
**Lines:** 3295-3299, Clock updates in multiple places
**Impact:** LOW-MEDIUM
**Description:** Multiple clock update intervals running simultaneously (1s intervals).

**Problem:** Checked code shows at least 2-3 clock update mechanisms. Wastes CPU cycles.

**Fix:** Consolidate to single clock update service:
```javascript
class ClockService {
  constructor() {
    this.subscribers = [];
    this.interval = null;
  }

  start() {
    if (this.interval) return;
    this.update();
    this.interval = setInterval(() => this.update(), 1000);
  }

  update() {
    const now = new Date();
    this.subscribers.forEach(fn => fn(now));
  }

  subscribe(callback) {
    this.subscribers.push(callback);
  }
}

const clockService = new ClockService();
clockService.subscribe((now) => {
  document.getElementById('currentDateTime').textContent = formatTime(now);
  // Other clock-dependent updates
});
clockService.start();
```

**Effort:** 35 minutes
**Performance Gain:** Eliminates duplicate interval timers

---

### 11. Unoptimized Health Check Polling
**Lines:** 2514-2516
**Impact:** MEDIUM
**Description:** System health check runs every 60s unconditionally, regardless of user interaction or section visibility.

```javascript
setInterval(() => {
  if (shouldRefresh()) updateSystemHealth();
}, 60000);
```

**Problem:**
- Runs even when dashboard-section not active
- No error handling/backoff
- Fixed 60s interval (could be adaptive based on health status)

**Fix:** Smart polling with section awareness:
```javascript
function startHealthPolling() {
  const pollHealth = async () => {
    // Only poll if system controls section visible or status bar visible
    const isRelevant = document.getElementById('system-status-container').offsetParent !== null;

    if (!isRelevant || !shouldRefresh()) {
      setTimeout(pollHealth, 60000);  // Check again in 60s
      return;
    }

    try {
      await updateSystemHealth();
      setTimeout(pollHealth, 60000);  // All good, standard interval
    } catch (error) {
      console.error('Health check failed:', error);
      setTimeout(pollHealth, 120000);  // Back off on error
    }
  };

  pollHealth();
}
```

**Effort:** 20 minutes
**Performance Gain:** 30-50% fewer health checks

---

### 12. Missing Virtualization for Large Tables
**Lines:** 5069-5100 (range leaderboard table), Cost table, Employee table
**Impact:** MEDIUM
**Description:** Large tables render all rows upfront. For 100+ employees in date range view, renders 100+ DOM rows even though only 10-15 visible.

**Problem:**
- Initial render slow (100 rows)
- Scroll performance degrades
- Memory overhead

**Fix:** Implement virtual scrolling:
```javascript
// Use library like react-window or implement simple version
class VirtualTable {
  constructor(container, rowHeight, totalRows, renderRow) {
    this.container = container;
    this.rowHeight = rowHeight;
    this.totalRows = totalRows;
    this.renderRow = renderRow;
    this.visibleRows = Math.ceil(container.clientHeight / rowHeight) + 2; // Buffer
  }

  render(scrollTop) {
    const startIndex = Math.floor(scrollTop / this.rowHeight);
    const endIndex = Math.min(startIndex + this.visibleRows, this.totalRows);

    // Only render visible rows + buffer
    // ...implementation
  }
}
```

**Effort:** 2-3 hours (or use library: 30 minutes)
**Performance Gain:** 80-90% faster initial render for 100+ rows, smooth scrolling

---

## Additional Observations

### Caching Opportunities
- **Leaderboard data:** Cache for 30s to avoid redundant fetches on quick tab switches
- **Department stats:** Cache with invalidation on target updates
- **PodFactory email suggestions:** Already fetched, could cache per employee name

### Memory Leaks (Potential)
- **Line 2338, 3328, 5407:** Multiple setInterval calls without proper cleanup tracking
- **Event listeners:** Some inline onclick handlers in dynamically created HTML may not clean up properly

### Bundle Size
- **325KB HTML file** includes all JS inline
- Consider code splitting if file grows further
- Chart.js loaded but only used in one section

---

## Prioritized Action Plan

### Week 1 (Quick Wins - 3-4 hours)
1. **Issue #1:** Parallelize dashboard API calls (15 min) - **Highest ROI**
2. **Issue #2:** Cache unmapped users (20 min)
3. **Issue #7:** Cache querySelectorAll (10 min)
4. **Issue #6:** Add debounce to search (30 min)
5. **Issue #5:** Adaptive polling for recalc (25 min)

**Expected improvement:** 60-70% faster dashboard loads, 50% fewer API calls

### Week 2 (High Impact - 4-5 hours)
1. **Issue #3:** Targeted DOM updates for dept cards (45 min)
2. **Issue #4:** Batch DOM updates in date range (30 min)
3. **Issue #8:** Optimize name similarity (35 min)
4. **Issue #9:** CSS-based table filtering (40 min)
5. **Issue #11:** Smart health polling (20 min)

**Expected improvement:** Eliminate UI jank, 40-50% fewer reflows

### Week 3 (Long-term - 6-8 hours)
1. **Issue #12:** Virtual scrolling for tables (2-3 hrs)
2. **Issue #10:** Consolidate clock service (35 min)
3. Add comprehensive caching layer (2 hrs)
4. Implement service worker for offline support (2 hrs)

**Expected improvement:** Support 200+ employees smoothly

---

## Performance Metrics (Estimated)

| Metric | Current | After Week 1 | After Week 2 | After Week 3 |
|--------|---------|-------------|-------------|-------------|
| Dashboard Load Time | 1200ms | 300ms | 250ms | 200ms |
| API Calls (2 min) | 15-20 | 8-10 | 6-8 | 5-7 |
| Table Render (100 rows) | 800ms | 800ms | 400ms | 50ms |
| Filter Response | 200ms | 50ms | 40ms | 30ms |
| Memory Usage (1hr) | 150MB | 120MB | 100MB | 80MB |

---

## Tools for Measurement

1. **Chrome DevTools Performance tab:** Record dashboard load, identify bottlenecks
2. **Network tab:** Monitor API call patterns, identify duplicates
3. **Lighthouse:** Run audit for performance score
4. **React DevTools Profiler:** (if migrating to React) - Currently N/A

---

## Unresolved Questions

1. **Backend performance:** Are API endpoints optimized? 200ms response time assumed but not verified.
2. **Data volume:** How many employees in production? Analysis assumes 20-50, but system may have 100-200.
3. **Browser support:** Are modern APIs (requestAnimationFrame, IntersectionObserver) available for all users?
4. **Mobile usage:** Any mobile dashboard access? Current optimizations desktop-focused.
5. **Real-time requirements:** Is 2-minute auto-refresh adequate or need WebSocket for true real-time?

---

## Conclusion

Manager.html has **significant performance optimization potential**. Prioritized fixes can reduce load times by 70%+ and API overhead by 50%+ with minimal effort (<8 hours total). Most critical: parallelize API calls (#1) and eliminate duplicate fetches (#2). Recommend starting with Week 1 quick wins for immediate user experience improvement.

**Next Steps:**
1. Run Chrome Performance audit to validate assumptions
2. Implement Week 1 fixes
3. A/B test with production data
4. Gather user feedback on perceived performance

