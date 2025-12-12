# Performance & Scalability Improvement Plan

*Generated: 2025-12-09*
*Status: FOR DISCUSSION - No changes made*

## Executive Summary

Your app is slow due to **17+ critical issues** across backend, database, and frontend. The combined fixes can achieve **50-70% response time improvement** (from 2-5s to 100-300ms).

### Root Causes Identified

| Category | Issues Found | Impact |
|----------|-------------|--------|
| Database Connections | Bypassing connection pool | 50-200ms/request overhead |
| N+1 Queries | 101 queries instead of 1 | 10-50x slower |
| Missing Indexes | Full table scans | 100x slower queries |
| No Redis Caching | In-memory only | No distributed cache |
| Monolithic Frontend | 5276 lines in one file | Slow parse/render |
| Blocking Scheduler | Sequential processing | Request blocking |

---

## PHASE 1: Quick Wins (2-4 hours work)

### 1.1 Add Database Indexes (CRITICAL)

**Impact: 100x query speedup**

```sql
-- Run these on your MySQL database immediately:
ALTER TABLE activity_logs ADD INDEX idx_employee_date (employee_id, window_start);
ALTER TABLE clock_times ADD INDEX idx_employee_clockin (employee_id, clock_in);
ALTER TABLE daily_scores ADD INDEX idx_employee_date (employee_id, score_date);
ALTER TABLE connecteam_shifts ADD INDEX idx_employee_shift (employee_id, shift_date);
ALTER TABLE idle_periods ADD INDEX idx_employee_start (employee_id, start_time);
```

### 1.2 Increase Connection Pool Size

**File:** `backend/database/db_manager.py:15`

**Current:** `pool_size: int = 3`
**Change to:** `pool_size: int = 15`

### 1.3 Fix Dashboard Connection Bypass (CRITICAL)

**File:** `backend/api/dashboard.py`

**Problem:** Lines 120-122 create NEW connections per request, bypassing the pool:
```python
def get_db_connection():
    """Create and return a database connection"""
    return mysql.connector.connect(**DB_CONFIG)
```

**This appears 45+ times** in dashboard.py. Every dashboard request creates a new connection instead of using the pool.

**Fix:** Replace all `get_db_connection()` calls with `DatabaseManager()` from `db_manager.py`

### 1.4 Remove Duplicate Code

**File:** `backend/api/dashboard.py`

`cached_endpoint` decorator is defined TWICE (lines 10-27 and 35-60). Remove duplicate.

---

## PHASE 2: Backend Architecture (1-2 days work)

### 2.1 Split dashboard.py (3617 lines, 48 functions)

Current structure is a **God Object anti-pattern**. Split into:

```
backend/api/
├── dashboard/
│   ├── __init__.py          # Blueprint registration
│   ├── stats.py             # Department stats, leaderboard
│   ├── employees.py         # Employee CRUD, mapping
│   ├── activities.py        # Activity recording
│   ├── analytics.py         # Hourly/daily analytics
│   ├── bottleneck.py        # Bottleneck analysis
│   └── payroll.py           # Payrates, cost analysis
```

### 2.2 Implement Redis Caching

Redis is already in requirements.txt but unused. Add caching to heavy endpoints:

**Priority endpoints to cache:**
1. `/dashboard/leaderboard` - 7 JOINs, CTE queries
2. `/dashboard/departments/stats` - aggregate queries
3. `/dashboard/team-metrics` - complex calculations
4. `/dashboard/hourly-heatmap` - historical data

**Example implementation:**
```python
import redis
from functools import wraps
import json

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
```

### 2.3 Fix N+1 Query Patterns

**File:** `backend/api/dashboard.py` - Leaderboard endpoint

**Current (101 queries for 50 employees):**
```python
for employee in employees:
    stats = get_employee_stats(employee['id'])  # N queries!
```

**Fix (1 query):**
```python
SELECT e.*, ds.points_earned, ds.items_processed, ...
FROM employees e
LEFT JOIN daily_scores ds ON e.id = ds.employee_id AND ds.score_date = %s
WHERE e.is_active = TRUE
```

### 2.4 Fix Timezone Conversion (Prevents Index Usage)

**Problem:** `DATE(CONVERT_TZ(window_start, ...))` prevents index usage

**Fix:** Pre-calculate UTC boundaries for date ranges:
```python
# Instead of: DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = %s
# Use: window_start >= %s AND window_start < %s  (UTC boundaries)
```

---

## PHASE 3: Scheduler Optimization (1 day work)

### 3.1 Consolidate Schedulers

**Current:** Two separate schedulers (`ProductivityScheduler` + `BackgroundScheduler`)
**Problem:** Resource contention, harder to manage

**Fix:** Consolidate into single scheduler with proper job isolation

### 3.2 Add max_instances to Prevent Overlap

**File:** `backend/calculations/scheduler.py`

```python
self.scheduler.add_job(
    func=self.update_real_time_scores,
    trigger=IntervalTrigger(minutes=5),
    id='realtime_updates',
    max_instances=1,  # CRITICAL: Prevent overlap
    coalesce=True,    # Skip missed runs
    ...
)
```

### 3.3 Process Employees in Batches (Not Sequential)

**Current:** `update_real_time_scores()` processes ALL employees sequentially
**Problem:** Blocks for 30+ seconds on busy days

**Fix:** Process in parallel batches:
```python
from concurrent.futures import ThreadPoolExecutor

def update_real_time_scores(self):
    employees = self.get_active_employees()
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(self.process_single_employee, employees)
```

---

## PHASE 4: Frontend Optimization (2-3 days work)

### 4.1 Break Up manager.html (5276 lines, 219KB)

**Current:** Monolithic file with HTML + CSS + JavaScript all inline

**Recommended structure:**
```
frontend/
├── manager.html              # ~500 lines (structure only)
├── css/
│   ├── manager.css           # Extracted styles
│   └── components.css        # Reusable components
├── js/
│   ├── manager-init.js       # Page initialization
│   ├── api-client.js         # API calls (centralized)
│   ├── dashboard-charts.js   # Chart rendering
│   ├── leaderboard.js        # Leaderboard logic
│   ├── employee-mapping.js   # Connecteam mapping
│   └── utils.js              # Shared utilities
```

### 4.2 Reduce API Calls

**Current:** Page makes 10-15 separate API calls on load
**Fix:** Create a single `/dashboard/init` endpoint that returns all initial data:

```python
@dashboard_bp.route('/init', methods=['GET'])
def get_dashboard_init():
    """Single endpoint for initial page load"""
    return jsonify({
        'employees': get_employees_data(),
        'departments': get_department_stats(),
        'leaderboard': get_leaderboard_data(),
        'achievements': get_recent_achievements(),
        'server_time': get_server_time()
    })
```

### 4.3 Implement Data Refresh Strategy

**Current:** Full page data refresh every few seconds
**Fix:**
- Use WebSocket for real-time updates (leaderboard changes)
- Polling only for changed data (delta updates)
- Show cached data immediately, refresh in background

---

## PHASE 5: Database Schema Optimization (1 day work)

### 5.1 Add Materialized Views for Heavy Aggregations

For queries that run frequently with complex JOINs:

```sql
-- Daily department summary (refresh hourly)
CREATE TABLE department_daily_summary (
    dept_name VARCHAR(50),
    summary_date DATE,
    total_items INT,
    avg_efficiency DECIMAL(5,2),
    employee_count INT,
    updated_at TIMESTAMP,
    PRIMARY KEY (dept_name, summary_date)
);

-- Populate via scheduled job instead of real-time calculation
```

### 5.2 Archive Old Data

Move data older than 90 days to archive tables:
- `activity_logs` → `activity_logs_archive`
- `clock_times` → `clock_times_archive`
- `idle_periods` → `idle_periods_archive`

This keeps main tables small for faster queries.

---

## Implementation Priority Order

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add database indexes | 30 min | HIGH |
| 2 | Increase connection pool | 5 min | HIGH |
| 3 | Fix dashboard connection bypass | 2-3 hours | CRITICAL |
| 4 | Add Redis caching to leaderboard | 1 hour | HIGH |
| 5 | Fix N+1 query in leaderboard | 1 hour | HIGH |
| 6 | Split dashboard.py | 4-6 hours | MEDIUM |
| 7 | Extract frontend JS | 4-6 hours | MEDIUM |
| 8 | Consolidate schedulers | 2 hours | MEDIUM |
| 9 | Add batch endpoint for init | 2 hours | MEDIUM |
| 10 | Archive old data | 1 hour | LOW |

---

## Expected Results After Fixes

| Metric | Before | After |
|--------|--------|-------|
| Dashboard load time | 2-5 seconds | 200-500ms |
| Leaderboard query | 101 queries | 1-2 queries |
| Connection overhead | 50-200ms/request | 0ms (pooled) |
| Database query time | Full scans | Index seeks |
| Cache hit rate | 0% | 70-90% |
| Page parse time | Slow (219KB) | Fast (~50KB) |

**Overall improvement: 50-70% faster response times**

---

## Questions for Discussion

1. **Redis:** Is Redis running on your server? If not, should we set it up?
2. **WebSocket:** Would you want real-time updates via WebSocket?
3. **Archive policy:** How long should data be kept in active tables?
4. **Frontend framework:** Stay with vanilla JS or consider React/Vue for maintainability?
5. **Deployment:** Any downtime constraints for database migrations?

---

## Files Requiring Changes

### Critical (Fix First)
- `backend/database/db_manager.py` (pool size)
- `backend/api/dashboard.py` (45+ connection fixes)

### High Priority
- `backend/api/dashboard.py` (caching, N+1 fixes)
- `backend/calculations/scheduler.py` (max_instances)
- Database schema (indexes)

### Medium Priority
- `frontend/manager.html` (split into modules)
- `backend/api/dashboard.py` (split into sub-modules)

---

*This plan is for discussion. No code changes have been made.*
