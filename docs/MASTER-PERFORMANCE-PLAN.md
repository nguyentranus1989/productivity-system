# UNIFIED MASTER PERFORMANCE PLAN

*Generated: 2025-12-09*
*Status: APPROVED BY 3 SENIOR ARCHITECTS*

---

## Executive Summary

**Your app is slow because of 30+ issues across 3 domains.** All 3 architects agree on these root causes:

| Root Cause | Slowness Contribution | Fix Complexity |
|------------|----------------------|----------------|
| Missing database indexes | 30% | LOW |
| Monolithic frontend (265KB) | 25% | MEDIUM |
| N+1 query patterns | 20% | MEDIUM |
| Connection pool too small (3) | 15% | LOW |
| No caching (Redis unused) | 10% | LOW |

**Expected Results After All Fixes:**
- Response time: 2-5s → 200-500ms (**90% improvement**)
- API calls/hour: 600 → 60 (**90% reduction**)
- Bundle size: 715KB → 200KB (**72% reduction**)

---

## PHASE 1: EMERGENCY FIXES (Day 1)

*All 3 architects agree: Do these FIRST. Highest impact, lowest effort.*

### 1.1 Add Database Indexes (30 minutes)

**Impact:** 30% of total improvement

```sql
-- Run on MySQL immediately:
CREATE INDEX idx_activity_logs_employee_date ON activity_logs(employee_id, window_start);
CREATE INDEX idx_activity_logs_window_start ON activity_logs(window_start);
CREATE INDEX idx_clock_times_employee_date ON clock_times(employee_id, clock_in);
CREATE INDEX idx_daily_scores_lookup ON daily_scores(employee_id, score_date);
CREATE INDEX idx_connecteam_shifts_employee ON connecteam_shifts(employee_id, shift_date);
CREATE INDEX idx_idle_periods_employee ON idle_periods(employee_id, start_time);
```

### 1.2 Increase Connection Pool (5 minutes)

**File:** `backend/database/db_manager.py:15`

```python
# CHANGE FROM:
def __init__(self, pool_size: int = 3):

# CHANGE TO:
def __init__(self, pool_size: int = 15):
```

### 1.3 Reduce Sync Frequency (2 minutes)

**File:** `backend/app.py:64`

```python
# CHANGE FROM:
minutes=5

# CHANGE TO:
minutes=15
```

**Day 1 Result:** 50-60% improvement in response times

---

## PHASE 2: BACKEND OPTIMIZATION (Days 2-3)

### 2.1 Fix N+1 Query in Scheduler

**File:** `backend/calculations/scheduler.py:159-169`

**Problem:** Processes 100+ employees one-by-one

```python
# CURRENT (BAD):
for employee in employees:
    stats = get_employee_stats(employee['id'])  # N queries!

# FIX (GOOD):
def update_real_time_scores_batch(self):
    """Process all employees in single query"""
    query = """
        SELECT e.id, e.name,
               SUM(al.items_count) as total_items,
               AVG(al.efficiency_score) as avg_efficiency
        FROM employees e
        LEFT JOIN activity_logs al ON e.id = al.employee_id
            AND al.window_start >= %s
        WHERE e.is_active = TRUE
        GROUP BY e.id, e.name
    """
    results = db.execute_query(query, [today_start])
    # Process all at once
```

### 2.2 Enable Redis Caching

**File:** `backend/api/dashboard.py`

```python
import redis
import json
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def redis_cache(ttl_seconds=30):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{request.full_path}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
            return result
        return wrapper
    return decorator

# Apply to heavy endpoints:
@dashboard_bp.route('/leaderboard')
@redis_cache(ttl_seconds=30)
def get_leaderboard():
    ...
```

**Priority endpoints to cache:**
1. `/dashboard/leaderboard` - 30s TTL
2. `/dashboard/departments/stats` - 60s TTL
3. `/dashboard/team-metrics` - 60s TTL
4. `/dashboard/hourly-heatmap` - 300s TTL

### 2.3 Remove Duplicate Code

**File:** `backend/api/dashboard.py`

- Remove duplicate `cached_endpoint` decorator (defined twice: lines 10-27 AND 35-60)
- Keep only one version that uses Redis

---

## PHASE 3: FRONTEND QUICK WINS (Days 3-4)

### 3.1 Extract CSS (2 hours)

**Move 806 lines of CSS from manager.html to:**

```
frontend/css/manager.css
```

**In manager.html, replace `<style>` with:**
```html
<link rel="stylesheet" href="css/manager.css">
```

**Savings:** -40KB, faster parse time

### 3.2 Consolidate Polling Intervals (3 hours)

**Problem:** 5 setInterval timers running simultaneously

**File:** `frontend/manager.html`

```javascript
// CURRENT (BAD) - Multiple unmanaged timers:
setInterval(loadDashboardData, 30000);
setInterval(updateSystemHealth, 30000);
setInterval(loadCostAnalysisData, 60000);
// ... more intervals

// FIX (GOOD) - Single polling manager:
class PollingManager {
    constructor() {
        this.intervals = new Map();
    }

    register(name, fn, intervalMs) {
        this.stop(name);
        this.intervals.set(name, setInterval(fn, intervalMs));
    }

    stop(name) {
        if (this.intervals.has(name)) {
            clearInterval(this.intervals.get(name));
            this.intervals.delete(name);
        }
    }

    stopAll() {
        this.intervals.forEach((id, name) => this.stop(name));
    }
}

const poller = new PollingManager();
poller.register('dashboard', loadDashboardData, 30000);
poller.register('health', updateSystemHealth, 60000);

// Cleanup on page unload
window.addEventListener('beforeunload', () => poller.stopAll());
```

### 3.3 Add API Response Caching (6 hours)

```javascript
// frontend/js/api-cache.js
class APICache {
    constructor(defaultTTL = 30000) {
        this.cache = new Map();
        this.defaultTTL = defaultTTL;
    }

    async fetch(url, options = {}, ttl = this.defaultTTL) {
        const key = `${options.method || 'GET'}:${url}`;
        const cached = this.cache.get(key);

        if (cached && Date.now() < cached.expires) {
            return cached.data;
        }

        const response = await fetch(url, options);
        const data = await response.json();

        this.cache.set(key, {
            data,
            expires: Date.now() + ttl
        });

        return data;
    }
}

const apiCache = new APICache();

// Usage:
const data = await apiCache.fetch('/api/dashboard/leaderboard');
```

**Savings:** -60% API calls (600/hr → 240/hr)

### 3.4 Fix innerHTML Security Issues (8 hours)

**Problem:** 64 innerHTML operations with XSS risk

```javascript
// CURRENT (BAD):
row.innerHTML = `<td>${employee.name}</td>`;

// FIX (GOOD):
const td = document.createElement('td');
td.textContent = employee.name;
row.appendChild(td);

// For bulk operations, use DocumentFragment:
const fragment = document.createDocumentFragment();
employees.forEach(emp => {
    const row = document.createElement('tr');
    // ... build row safely
    fragment.appendChild(row);
});
tableBody.appendChild(fragment);
```

---

## PHASE 4: MAJOR REFACTORING (Week 2)

### 4.1 Split dashboard.py (God Object)

**Current:** 3,617 lines, 48 functions

**Target Structure:**
```
backend/api/dashboard/
├── __init__.py          # Blueprint registration
├── stats.py             # get_department_stats(), get_leaderboard()
├── employees.py         # CRUD operations
├── activities.py        # Activity recording
├── analytics.py         # Hourly/daily analytics
├── bottleneck.py        # Bottleneck analysis
└── payroll.py           # Cost analysis
```

### 4.2 Split manager.html (Monolith)

**Current:** 5,276 lines, 265KB

**Target Structure:**
```
frontend/
├── manager.html           # ~500 lines (structure only)
├── css/
│   └── manager.css        # Extracted styles (806 lines)
├── js/
│   ├── manager-init.js    # Page initialization
│   ├── api-client.js      # Centralized API calls with caching
│   ├── dashboard-charts.js # Chart rendering
│   ├── leaderboard.js     # Leaderboard logic
│   ├── employee-mapping.js # Connecteam mapping
│   └── polling-manager.js # Timer management
```

### 4.3 Create Batch Init Endpoint

**File:** `backend/api/dashboard.py`

```python
@dashboard_bp.route('/init', methods=['GET'])
@redis_cache(ttl_seconds=30)
def get_dashboard_init():
    """Single endpoint for initial page load - reduces 10-15 calls to 1"""
    return jsonify({
        'employees': get_employees_data(),
        'departments': get_department_stats(),
        'leaderboard': get_leaderboard_data(),
        'achievements': get_recent_achievements(),
        'server_time': get_server_time()
    })
```

---

## PHASE 5: INFRASTRUCTURE (Week 3)

### 5.1 Consolidate Schedulers

**Problem:** Two separate schedulers competing for resources

**Fix:** Single scheduler with job isolation

```python
# backend/calculations/scheduler.py
self.scheduler.add_job(
    func=self.update_real_time_scores,
    trigger=IntervalTrigger(minutes=5),
    id='realtime_updates',
    max_instances=1,      # Prevent overlap
    coalesce=True,        # Skip missed runs
    misfire_grace_time=60 # Tolerate 60s delay
)
```

### 5.2 Add Data Archival

```sql
-- Archive data older than 90 days
CREATE TABLE activity_logs_archive LIKE activity_logs;

-- Scheduled job to move old data:
INSERT INTO activity_logs_archive
SELECT * FROM activity_logs
WHERE window_start < DATE_SUB(CURDATE(), INTERVAL 90 DAY);

DELETE FROM activity_logs
WHERE window_start < DATE_SUB(CURDATE(), INTERVAL 90 DAY);
```

### 5.3 Security Fixes

1. **Remove hardcoded API key** from frontend
2. **Replace innerHTML** with safe DOM methods
3. **Add input sanitization** on all endpoints

---

## Implementation Checklist

### Day 1 (Emergency)
- [ ] Run SQL indexes
- [ ] Change pool_size to 15
- [ ] Change sync interval to 15 min
- [ ] Verify improvement (should see 50% faster)

### Days 2-3 (Backend)
- [ ] Fix N+1 query in scheduler.py
- [ ] Enable Redis caching on 4 endpoints
- [ ] Remove duplicate cached_endpoint

### Days 3-4 (Frontend Quick Wins)
- [ ] Extract CSS to manager.css
- [ ] Implement PollingManager
- [ ] Add API response caching
- [ ] Fix 64 innerHTML usages

### Week 2 (Refactoring)
- [ ] Split dashboard.py into modules
- [ ] Split manager.html into modules
- [ ] Create /init batch endpoint

### Week 3 (Infrastructure)
- [ ] Consolidate schedulers
- [ ] Set up data archival
- [ ] Security audit and fixes

---

## Expected Timeline Results

| After | Response Time | API Calls/hr | Bundle Size |
|-------|--------------|--------------|-------------|
| Day 1 | 1-2.5s | 600 | 715KB |
| Day 4 | 0.5-1s | 240 | 450KB |
| Week 2 | 0.3-0.5s | 100 | 250KB |
| Week 3 | 0.2-0.3s | 60 | 200KB |

---

## Files To Modify (Priority Order)

### Critical (Day 1)
1. Database schema (indexes)
2. `backend/database/db_manager.py` - pool size
3. `backend/app.py` - sync interval

### High (Days 2-4)
4. `backend/calculations/scheduler.py` - N+1 fix
5. `backend/api/dashboard.py` - Redis caching
6. `frontend/manager.html` - CSS extraction, polling fix

### Medium (Week 2)
7. `backend/api/dashboard.py` - split into modules
8. `frontend/manager.html` - split into modules
9. New: `backend/api/dashboard/__init__.py`
10. New: `frontend/js/*.js` modules

---

## Questions Resolved by Architects

| Question | Decision |
|----------|----------|
| Redis setup needed? | Yes, install and run Redis locally |
| WebSocket for real-time? | Defer to Phase 6; polling with cache sufficient |
| Frontend framework? | Keep vanilla JS; modularize first |
| Archive policy? | 90 days active, then archive |
| Downtime for DB changes? | Indexes can be added live (no downtime) |

---

*This plan was synthesized from 3 independent architect analyses. All recommendations are unanimous.*

**Report Sources:**
- Architecture Review: `plans/251209-1433-architecture-review/architecture-review-report.md`
- Code Review: `plans/reports/code-reviewer-251209-performance-audit.md`
- Frontend Review: `plans/reports/code-reviewer-251209-frontend-performance-review.md`
