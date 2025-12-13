# Backend Refactoring Plan - Productivity Hub System

**Author:** Senior Backend Architect
**Date:** 2025-12-09
**Status:** Draft for Review

---

## Executive Summary

The Productivity Hub backend requires significant refactoring to address critical issues:
- **dashboard.py**: 3,617 lines, 48+ routes (God Object anti-pattern)
- **Connection pool bypass**: 41+ `get_db_connection()` calls create NEW connections, ignoring the pool
- **Pool size inadequate**: 3 connections vs 15+ needed for concurrent operations
- **N+1 queries**: Leaderboard makes 101+ queries vs optimal 1-2
- **Redis unused**: Cache infrastructure exists but not leveraged
- **Dual schedulers**: ProductivityScheduler + BackgroundScheduler running concurrently

---

## 1. API Restructuring - Split dashboard.py

### 1.1 Current State Analysis

`dashboard.py` contains 48 routes spanning 6 distinct domains:
1. **Leaderboard/Rankings** (5 routes) - Lines 236-747
2. **Analytics/Statistics** (8 routes) - Lines 423-1070
3. **Employee Management** (12 routes) - Lines 1414-3081
4. **Clock/Time Tracking** (4 routes) - Lines 566-741
5. **Bottleneck Detection** (4 routes) - Lines 1883-2545
6. **Cost Analysis** (1 route) - Lines 3284-3617

### 1.2 Target Structure

```
backend/api/
├── __init__.py                  # Blueprint registration
├── dashboard/                   # NEW: dashboard package
│   ├── __init__.py             # Blueprint factory + common utilities
│   ├── leaderboard.py          # 5 routes, ~500 lines
│   ├── analytics.py            # 8 routes, ~650 lines
│   ├── employees.py            # 12 routes, ~700 lines
│   ├── clock_times.py          # 4 routes, ~200 lines
│   ├── bottleneck.py           # 4 routes, ~400 lines
│   └── cost_analysis.py        # 1 route, ~350 lines
├── activities.py               # KEEP (already separated)
├── gamification.py             # KEEP (already separated)
├── team_metrics.py             # KEEP (already separated)
└── connecteam.py               # KEEP (already separated)
```

### 1.3 Migration Strategy (Zero Downtime)

**Phase 1: Extract without breaking** (Priority: HIGH)
```python
# backend/api/dashboard/__init__.py
from flask import Blueprint
from .leaderboard import leaderboard_routes
from .analytics import analytics_routes
from .employees import employees_routes
from .clock_times import clock_routes
from .bottleneck import bottleneck_routes
from .cost_analysis import cost_routes

dashboard_bp = Blueprint('dashboard', __name__)

# Register all sub-routes
dashboard_bp.register_blueprint(leaderboard_routes)
dashboard_bp.register_blueprint(analytics_routes)
dashboard_bp.register_blueprint(employees_routes)
dashboard_bp.register_blueprint(clock_routes)
dashboard_bp.register_blueprint(bottleneck_routes)
dashboard_bp.register_blueprint(cost_routes)
```

**Phase 2: Move shared utilities**
```python
# backend/api/dashboard/utils.py
import pytz
from datetime import datetime
from functools import wraps
from flask import request, jsonify

def get_central_date():
    """Get current date in Central Time"""
    return datetime.now(pytz.timezone('America/Chicago')).date()

def get_central_datetime():
    """Get current datetime in Central Time"""
    return datetime.now(pytz.timezone('America/Chicago'))

def cached_endpoint(ttl_seconds=10):
    """Simple cache decorator - MIGRATE TO REDIS LATER"""
    # ... existing implementation ...
    pass

def require_api_key(f):
    """API key validation decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != 'dev-api-key-123':
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated
```

### 1.4 Route Extraction Mapping

| Current Location | New File | Routes |
|-----------------|----------|--------|
| Lines 136-232 | leaderboard.py | `/departments/stats` |
| Lines 236-420 | leaderboard.py | `/leaderboard` |
| Lines 615-747 | leaderboard.py | `/leaderboard/live` |
| Lines 749-808 | analytics.py | `/analytics/streak-leaders` |
| Lines 809-942 | analytics.py | `/analytics/achievement-ticker` |
| Lines 943-997 | analytics.py | `/analytics/hourly-heatmap` |
| Lines 1278-1413 | analytics.py | `/analytics/team-metrics` |
| Lines 1414-1551 | employees.py | `/employees/<id>/stats` |
| Lines 2351-2428 | employees.py | `/employees`, `/employees/<id>/mapping` |
| Lines 1883-2275 | bottleneck.py | `/bottleneck/current` |
| Lines 2276-2350 | bottleneck.py | `/bottleneck/history` |
| Lines 3284-3617 | cost_analysis.py | `/cost-analysis` |

---

## 2. Database Layer Fixes

### 2.1 Critical Issue: Connection Pool Bypass

**Problem:** `dashboard.py` defines its own `get_db_connection()`:
```python
# Line 121-123 of dashboard.py - BYPASSES THE POOL!
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
```

This creates 41+ NEW connections per request cycle instead of using the pool.

**Solution:** Remove local `get_db_connection()` and use `db_manager`:

```python
# In each new module (e.g., leaderboard.py)
from database.db_manager import get_db

db = get_db()

# Instead of:
#   conn = get_db_connection()
#   cursor = conn.cursor(dictionary=True)
#   cursor.execute(query, params)
#   results = cursor.fetchall()
#   cursor.close()
#   conn.close()

# Use:
results = db.execute_query(query, params)
```

### 2.2 Increase Pool Size

**Current:** `pool_size=3` (db_manager.py line 15)

**Required:** Minimum 15 for production:
- 5 concurrent API requests
- 2 scheduler jobs
- 3 background syncs
- 5 buffer for spikes

```python
# backend/database/db_manager.py
class DatabaseManager:
    def __init__(self, pool_size: int = None):
        self.pool_size = pool_size or int(os.getenv('DB_POOL_SIZE', 15))
```

### 2.3 Repository Pattern Implementation

Create domain-specific repositories:

```python
# backend/database/repositories/employee_repository.py
from database.db_manager import get_db
from typing import List, Optional, Dict

class EmployeeRepository:
    def __init__(self):
        self.db = get_db()

    def get_by_id(self, employee_id: int) -> Optional[Dict]:
        return self.db.execute_one(
            "SELECT * FROM employees WHERE id = %s",
            (employee_id,)
        )

    def get_active_employees(self) -> List[Dict]:
        return self.db.execute_query(
            "SELECT * FROM employees WHERE is_active = 1"
        )

    def get_with_clock_times(self, date: str, utc_start: str, utc_end: str) -> List[Dict]:
        """Optimized query - replaces N+1 pattern"""
        return self.db.execute_query("""
            SELECT
                e.id, e.name, e.current_streak,
                ds.items_processed, ds.points_earned,
                ct.total_minutes, ct.is_clocked_in
            FROM employees e
            LEFT JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = %s
            LEFT JOIN (
                SELECT employee_id,
                    SUM(total_minutes) as total_minutes,
                    MAX(CASE WHEN clock_out IS NULL THEN 1 ELSE 0 END) as is_clocked_in
                FROM clock_times
                WHERE clock_in >= %s AND clock_in <= %s
                GROUP BY employee_id
            ) ct ON ct.employee_id = e.id
            WHERE e.is_active = 1
        """, (date, utc_start, utc_end))
```

### 2.4 Required Database Indexes

Add these indexes to improve query performance:

```sql
-- Missing indexes identified from query analysis

-- For leaderboard queries
CREATE INDEX idx_daily_scores_date_points
ON daily_scores(score_date, points_earned DESC);

CREATE INDEX idx_activity_logs_window_employee
ON activity_logs(window_start, employee_id, activity_type);

-- For clock time lookups
CREATE INDEX idx_clock_times_clock_in_employee
ON clock_times(clock_in, employee_id);

CREATE INDEX idx_clock_times_employee_date
ON clock_times(employee_id, DATE(clock_in));

-- For bottleneck detection
CREATE INDEX idx_activity_logs_type_date
ON activity_logs(activity_type, window_start, items_count);

-- For cost analysis
CREATE INDEX idx_employee_payrates_employee
ON employee_payrates(employee_id);
```

---

## 3. Caching Strategy - Redis Implementation

### 3.1 Current State

- `CacheManager` exists in `database/cache_manager.py`
- Has `get()`, `set()`, `delete()`, `get_json()`, `set_json()` methods
- Gracefully degrades if Redis unavailable
- **NOT USED** by dashboard.py (uses local `_endpoint_cache` dict instead)

### 3.2 Target Cache Architecture

```
Cache Layer Strategy:
┌─────────────────────────────────────────────────────┐
│                    API Request                       │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│           L1: In-Process Cache (TTL: 5s)            │
│   - Hot path data (leaderboard, department stats)   │
│   - Low latency, high hit rate                      │
└─────────────────────────────────────────────────────┘
                          │ MISS
                          ▼
┌─────────────────────────────────────────────────────┐
│              L2: Redis (TTL: 30-300s)               │
│   - Computed results, aggregations                  │
│   - Shared across workers                           │
└─────────────────────────────────────────────────────┘
                          │ MISS
                          ▼
┌─────────────────────────────────────────────────────┐
│                   L3: MySQL                          │
│   - Source of truth                                 │
│   - Invalidation triggers cache updates             │
└─────────────────────────────────────────────────────┘
```

### 3.3 Cache Key Strategy

```python
# backend/database/cache_keys.py

class CacheKeys:
    """Standardized cache key patterns"""

    # Leaderboard caches (TTL: 15s)
    LEADERBOARD_DAILY = "leaderboard:daily:{date}"
    LEADERBOARD_LIVE = "leaderboard:live:{date}"
    DEPARTMENT_STATS = "departments:stats:{date}"

    # Employee caches (TTL: 60s)
    EMPLOYEE_STATS = "employee:{id}:stats:{date}"
    EMPLOYEE_CLOCK = "employee:{id}:clock:{date}"

    # Analytics caches (TTL: 300s)
    HOURLY_HEATMAP = "analytics:heatmap:{date}"
    DATE_RANGE_STATS = "analytics:range:{start}:{end}"
    COST_ANALYSIS = "cost:analysis:{start}:{end}"

    # Aggregation caches (TTL: 60s)
    ACTIVE_EMPLOYEES = "active_employees:{date}"
    WORKING_TODAY = "working_today"
    CURRENTLY_CLOCKED = "currently_clocked"
```

### 3.4 Cache Decorator Implementation

```python
# backend/database/cache_decorator.py

from functools import wraps
from flask import request
from database.cache_manager import get_cache_manager
import json
import hashlib

def redis_cached(key_pattern: str, ttl: int = 60):
    """
    Redis cache decorator with automatic key generation.

    Usage:
        @redis_cached("leaderboard:daily:{date}", ttl=15)
        def get_leaderboard(date):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Build cache key from pattern and request params
            key_params = {**kwargs}
            for param in request.args:
                key_params[param] = request.args.get(param)

            cache_key = key_pattern.format(**key_params)

            # Try cache first
            cached = cache.get_json(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache (only cache successful responses)
            if isinstance(result, tuple):
                data, status = result
                if status == 200:
                    cache.set_json(cache_key, data, ttl)
            else:
                cache.set_json(cache_key, result, ttl)

            return result
        return wrapper
    return decorator

def invalidate_pattern(pattern: str):
    """Invalidate all keys matching pattern"""
    cache = get_cache_manager()
    cache.clear_pattern(pattern)
```

### 3.5 Recommended Cache TTLs

| Data Type | TTL | Reason |
|-----------|-----|--------|
| Live leaderboard | 5-15s | Near real-time needed |
| Department stats | 15-30s | Updates frequently |
| Employee clock status | 30-60s | Balance freshness/load |
| Daily analytics | 300s | Stable within day |
| Historical analytics | 3600s | Rarely changes |
| Cost analysis | 300s | Computation heavy |

---

## 4. Scheduler Consolidation

### 4.1 Current Dual Scheduler Problem

**app.py** runs TWO schedulers:
1. `ProductivityScheduler` (calculations/scheduler.py) - 6 jobs
2. `BackgroundScheduler` (APScheduler) - 2 Connecteam jobs

This causes:
- Race conditions on data updates
- Double resource consumption
- Conflicting job executions

### 4.2 Target: Single Unified Scheduler

```python
# backend/calculations/unified_scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.redis import RedisJobStore
import pytz
import logging

logger = logging.getLogger(__name__)

class UnifiedScheduler:
    """Single scheduler managing all background jobs"""

    def __init__(self, timezone='America/Chicago'):
        self.tz = pytz.timezone(timezone)

        # Use Redis for job persistence (survives restarts)
        jobstores = {
            'default': RedisJobStore(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=1  # Separate DB for jobs
            )
        }

        # Thread pool for concurrent jobs
        executors = {
            'default': ThreadPoolExecutor(max_workers=5)
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine missed executions
            'max_instances': 1,  # Prevent overlap
            'misfire_grace_time': 300
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.tz
        )

    def configure_jobs(self, app):
        """Configure all scheduled jobs"""
        from calculations.productivity_calculator import ProductivityCalculator
        from calculations.idle_detector import IdleDetector
        from integrations.connecteam_sync import ConnecteamSync

        # PRODUCTIVITY JOBS

        # Process activities every 10 minutes
        self.scheduler.add_job(
            func=self._process_activities,
            trigger=IntervalTrigger(minutes=10),
            id='process_activities',
            name='Process Recent Activities',
            replace_existing=True
        )

        # Check idle employees every 5 minutes
        self.scheduler.add_job(
            func=self._check_idle,
            trigger=IntervalTrigger(minutes=5),
            id='check_idle',
            name='Check Idle Employees',
            replace_existing=True
        )

        # Real-time score updates every 5 minutes
        self.scheduler.add_job(
            func=self._update_scores,
            trigger=IntervalTrigger(minutes=5),
            id='realtime_scores',
            name='Update Real-time Scores',
            replace_existing=True
        )

        # CONNECTEAM JOBS (if enabled)
        if app.config.get('ENABLE_AUTO_SYNC'):
            self.scheduler.add_job(
                func=self._sync_connecteam_shifts,
                trigger=IntervalTrigger(minutes=5),
                id='connecteam_shifts',
                name='Sync Connecteam Shifts',
                replace_existing=True
            )

            self.scheduler.add_job(
                func=self._sync_connecteam_employees,
                trigger=CronTrigger(hour=2, minute=0),
                id='connecteam_employees',
                name='Sync Connecteam Employees',
                replace_existing=True
            )

        # DAILY JOBS

        # Finalize daily scores at 6 PM
        self.scheduler.add_job(
            func=self._finalize_daily,
            trigger=CronTrigger(hour=18, minute=0),
            id='finalize_daily',
            name='Finalize Daily Scores',
            replace_existing=True
        )

        # Daily reports at 6:30 PM
        self.scheduler.add_job(
            func=self._generate_reports,
            trigger=CronTrigger(hour=18, minute=30),
            id='daily_reports',
            name='Generate Daily Reports',
            replace_existing=True
        )

        # Cache warm-up at 5:30 AM
        self.scheduler.add_job(
            func=self._warm_cache,
            trigger=CronTrigger(hour=5, minute=30),
            id='cache_warmup',
            name='Warm Up Cache',
            replace_existing=True
        )

    def start(self):
        self.scheduler.start()
        logger.info("Unified scheduler started")

    def shutdown(self):
        self.scheduler.shutdown(wait=True)
        logger.info("Unified scheduler stopped")
```

### 4.3 Migration Steps

1. **Create `unified_scheduler.py`** with all jobs
2. **Update `app.py`** to use single scheduler:
   ```python
   from calculations.unified_scheduler import UnifiedScheduler

   scheduler = None

   def init_scheduler(app):
       global scheduler
       scheduler = UnifiedScheduler()
       scheduler.configure_jobs(app)
       scheduler.start()
   ```
3. **Remove** `init_schedulers()` function
4. **Delete** old scheduler imports
5. **Test** job execution in staging

---

## 5. Query Optimization

### 5.1 N+1 Query Problem - Leaderboard

**Current:** Lines 267-348 of dashboard.py execute correlated subqueries:
- Main query returns N employees
- Each employee triggers subquery for activity_breakdown
- Each employee triggers subquery for primary_department
- Result: 1 + 2N queries (101 queries for 50 employees)

**Solution:** Single query with window functions

```python
# backend/database/queries/leaderboard_queries.py

LEADERBOARD_OPTIMIZED = """
WITH activity_aggregates AS (
    SELECT
        employee_id,
        activity_type,
        SUM(items_count) as total_items,
        ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY SUM(items_count) DESC) as rn
    FROM activity_logs
    WHERE window_start >= %(utc_start)s AND window_start <= %(utc_end)s
    AND source = 'podfactory'
    GROUP BY employee_id, activity_type
),
employee_activities AS (
    SELECT
        employee_id,
        GROUP_CONCAT(
            CONCAT(activity_type, ':', total_items)
            ORDER BY total_items DESC SEPARATOR '|'
        ) as activity_breakdown,
        MAX(CASE WHEN rn = 1 THEN activity_type END) as primary_activity
    FROM activity_aggregates
    GROUP BY employee_id
),
clock_aggregates AS (
    SELECT
        employee_id,
        SUM(total_minutes) as total_minutes,
        MAX(CASE WHEN clock_out IS NULL THEN 1 ELSE 0 END) as is_clocked_in
    FROM clock_times
    WHERE clock_in >= %(utc_start)s AND clock_in <= %(utc_end)s
    GROUP BY employee_id
)
SELECT
    e.id,
    e.name,
    e.current_streak,
    COALESCE(ds.items_processed, 0) as items_today,
    COALESCE(ds.points_earned, 0) as score,
    COALESCE(ct.total_minutes, 0) as total_minutes,
    COALESCE(ct.is_clocked_in, 0) as is_clocked_in,
    ea.activity_breakdown,
    COALESCE(rc.role_name, 'Unknown') as primary_department
FROM employees e
LEFT JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = %(date)s
LEFT JOIN clock_aggregates ct ON ct.employee_id = e.id
LEFT JOIN employee_activities ea ON ea.employee_id = e.id
LEFT JOIN role_configs rc ON rc.id = (
    SELECT role_id FROM activity_logs
    WHERE employee_id = e.id
    AND window_start >= %(utc_start)s AND window_start <= %(utc_end)s
    GROUP BY role_id ORDER BY SUM(items_count) DESC LIMIT 1
)
WHERE e.is_active = 1
AND (ct.employee_id IS NOT NULL OR ds.items_processed > 0)
ORDER BY COALESCE(ds.points_earned, 0) DESC
"""
```

### 5.2 Batch Endpoints

Create batch endpoints to reduce HTTP round trips:

```python
# backend/api/dashboard/batch.py

@dashboard_bp.route('/batch', methods=['POST'])
@require_api_key
def batch_request():
    """
    Execute multiple dashboard queries in one request.

    Request body:
    {
        "requests": [
            {"endpoint": "leaderboard", "params": {"date": "2025-12-09"}},
            {"endpoint": "department_stats", "params": {"date": "2025-12-09"}},
            {"endpoint": "active_employees", "params": {}}
        ]
    }
    """
    data = request.get_json()
    results = {}

    endpoint_handlers = {
        'leaderboard': _get_leaderboard,
        'department_stats': _get_department_stats,
        'active_employees': _get_active_employees,
        'cost_analysis': _get_cost_analysis,
        'hourly_heatmap': _get_hourly_heatmap
    }

    for req in data.get('requests', []):
        endpoint = req.get('endpoint')
        params = req.get('params', {})

        if endpoint in endpoint_handlers:
            try:
                results[endpoint] = endpoint_handlers[endpoint](**params)
            except Exception as e:
                results[endpoint] = {'error': str(e)}
        else:
            results[endpoint] = {'error': 'Unknown endpoint'}

    return jsonify(results)
```

### 5.3 Dashboard Summary Endpoint

Single endpoint for all dashboard data:

```python
@dashboard_bp.route('/summary', methods=['GET'])
@require_api_key
@redis_cached("dashboard:summary:{date}", ttl=15)
def get_dashboard_summary():
    """
    Get all dashboard data in one request.
    Replaces 5+ separate API calls from frontend.
    """
    date = request.args.get('date', get_central_date().strftime('%Y-%m-%d'))

    # Execute all queries in parallel using ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            'leaderboard': executor.submit(_get_leaderboard, date),
            'departments': executor.submit(_get_department_stats, date),
            'active_count': executor.submit(_get_active_count, date),
            'metrics': executor.submit(_get_daily_metrics, date),
            'alerts': executor.submit(_get_active_alerts, date)
        }

        results = {key: future.result() for key, future in futures.items()}

    return jsonify({
        'date': date,
        'generated_at': datetime.now().isoformat(),
        **results
    })
```

---

## 6. Implementation Priority Order

### Phase 1: Critical Fixes (Week 1)
| Priority | Task | Impact | Risk |
|----------|------|--------|------|
| P0 | Fix connection pool bypass | High | Low |
| P0 | Increase pool size to 15 | High | Low |
| P1 | Add missing database indexes | High | Low |
| P1 | Enable Redis caching for leaderboard | Medium | Low |

### Phase 2: API Restructuring (Week 2-3)
| Priority | Task | Impact | Risk |
|----------|------|--------|------|
| P1 | Extract leaderboard.py from dashboard.py | Medium | Medium |
| P1 | Extract employees.py from dashboard.py | Medium | Medium |
| P2 | Extract analytics.py from dashboard.py | Medium | Medium |
| P2 | Create dashboard package structure | Medium | Low |

### Phase 3: Performance Optimization (Week 3-4)
| Priority | Task | Impact | Risk |
|----------|------|--------|------|
| P1 | Optimize N+1 leaderboard query | High | Medium |
| P2 | Implement batch endpoints | Medium | Low |
| P2 | Add dashboard summary endpoint | Medium | Low |
| P2 | Implement repository pattern | Medium | Medium |

### Phase 4: Scheduler Consolidation (Week 4-5)
| Priority | Task | Impact | Risk |
|----------|------|--------|------|
| P1 | Create unified scheduler | Medium | High |
| P1 | Migrate existing jobs | Medium | High |
| P2 | Add Redis job store | Low | Medium |
| P2 | Remove old scheduler code | Low | Low |

---

## 7. Testing Strategy

### 7.1 Pre-Migration Tests

```python
# tests/test_dashboard_parity.py

def test_leaderboard_parity():
    """Ensure new implementation matches old output"""
    old_result = old_get_leaderboard(date='2025-12-09')
    new_result = new_get_leaderboard(date='2025-12-09')

    assert len(old_result) == len(new_result)
    for old, new in zip(old_result, new_result):
        assert old['id'] == new['id']
        assert old['name'] == new['name']
        assert abs(old['score'] - new['score']) < 0.01
```

### 7.2 Performance Benchmarks

```python
# tests/benchmarks/test_query_performance.py

def test_leaderboard_query_count():
    """Verify N+1 fix - should be 1-2 queries"""
    with query_counter() as counter:
        get_leaderboard(date='2025-12-09')

    assert counter.count <= 2, f"Expected 1-2 queries, got {counter.count}"

def test_leaderboard_response_time():
    """Leaderboard should respond in <200ms"""
    start = time.time()
    get_leaderboard(date='2025-12-09')
    elapsed = (time.time() - start) * 1000

    assert elapsed < 200, f"Expected <200ms, got {elapsed}ms"
```

---

## 8. Rollback Strategy

Each phase includes rollback procedures:

### Connection Pool Fix Rollback
```python
# If issues arise, revert to direct connections temporarily
# Add environment variable toggle:
USE_POOLED_CONNECTIONS = os.getenv('USE_POOLED_CONNECTIONS', 'true') == 'true'
```

### API Split Rollback
```python
# Keep original dashboard.py during migration
# Route requests through compatibility layer
if os.getenv('USE_NEW_DASHBOARD', 'false') == 'true':
    from api.dashboard import dashboard_bp
else:
    from api.dashboard_legacy import dashboard_bp
```

---

## Points for Discussion

The following items need input from other architects before implementation:

1. **Frontend Compatibility**
   - Will batch endpoints require frontend changes?
   - Can we add `/api/dashboard/v2/` prefix during transition?
   - What is acceptable latency increase during migration?

2. **Database Schema Changes**
   - Should we add indexes during business hours or maintenance window?
   - Is there budget for MySQL read replica for analytics queries?
   - Should we partition `activity_logs` table (currently large)?

3. **Redis Architecture**
   - Should Redis be clustered for high availability?
   - What is acceptable cache miss rate during startup?
   - Should we use separate Redis instance for job store vs cache?

4. **Scheduler Migration Risk**
   - Can we run both schedulers in parallel during testing?
   - What monitoring should be in place for job failures?
   - How to handle in-flight jobs during deployment?

5. **Security Considerations**
   - API key `dev-api-key-123` hardcoded in decorator - needs rotation strategy
   - Should batch endpoint have different rate limiting?
   - How to audit/log cache hits vs misses for security?

6. **Infrastructure Team Input**
   - Current server specs - can it handle 15-connection pool?
   - Is there load balancer in front of Flask?
   - PM2 process manager - how many workers currently?

7. **Async Processing Consideration**
   - Should we consider async framework (FastAPI, async Flask)?
   - Would message queue (Celery/RQ) be better for heavy calculations?
   - Is real-time WebSocket needed for live leaderboard?

---

## Appendix A: File Change Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `backend/api/dashboard.py` | SPLIT | -3617 |
| `backend/api/dashboard/__init__.py` | CREATE | +50 |
| `backend/api/dashboard/leaderboard.py` | CREATE | +500 |
| `backend/api/dashboard/analytics.py` | CREATE | +650 |
| `backend/api/dashboard/employees.py` | CREATE | +700 |
| `backend/api/dashboard/clock_times.py` | CREATE | +200 |
| `backend/api/dashboard/bottleneck.py` | CREATE | +400 |
| `backend/api/dashboard/cost_analysis.py` | CREATE | +350 |
| `backend/api/dashboard/utils.py` | CREATE | +100 |
| `backend/database/db_manager.py` | MODIFY | +10 |
| `backend/database/cache_decorator.py` | CREATE | +80 |
| `backend/database/cache_keys.py` | CREATE | +40 |
| `backend/database/repositories/` | CREATE | +500 |
| `backend/calculations/unified_scheduler.py` | CREATE | +250 |
| `backend/app.py` | MODIFY | +20, -40 |

---

## Appendix B: Estimated Impact

| Metric | Current | After Phase 4 |
|--------|---------|---------------|
| dashboard.py lines | 3,617 | 0 (split) |
| Max modules per file | 48 routes | 12 routes |
| DB connections per request | 5-10 | 1 |
| Leaderboard queries | 101 | 1-2 |
| Leaderboard response time | ~800ms | ~150ms |
| Cache hit rate | 0% | 70-80% |
| Scheduler instances | 2 | 1 |
| Job overlap risk | High | None |

---

*Document ends. Please review and provide feedback on discussion points.*
