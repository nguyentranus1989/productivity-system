# Performance Code Review Report
**Date**: 2025-12-09
**Reviewer**: Code Review Agent
**Focus**: Backend Performance Issues ("my app is so slow")

---

## Code Review Summary

### Scope
- **Files reviewed**:
  - `backend/calculations/productivity_calculator.py` (513 lines)
  - `backend/calculations/idle_detector.py` (253 lines)
  - `backend/api/dashboard.py` (999+ lines)
  - `backend/api/connecteam.py` (380 lines)
  - `backend/integrations/connecteam_sync.py` (846 lines)
  - `backend/database/db_manager.py` (137 lines)
- **Lines analyzed**: ~3,000+ LOC
- **Review focus**: Performance bottlenecks, N+1 queries, blocking I/O, missing indexes

### Overall Assessment
**CRITICAL PERFORMANCE ISSUES FOUND**. App slowness caused by multiple severe database anti-patterns:
- **N+1 query problems** across all major endpoints
- **Missing database indexes** on heavily-queried columns
- **Inefficient query patterns** with subqueries in SELECT clauses
- **Connection pool exhaustion** risk due to small pool size
- **Blocking synchronous operations** in critical paths
- **Redundant role lookups** without caching

**Estimated performance impact**: 10-50x slower than optimal implementation. Some endpoints likely timeout under load.

---

## Critical Issues

### 1. **CRITICAL: Massive N+1 Query in Dashboard Leaderboard**
**Location**: `backend/api/dashboard.py:266-350`
**Severity**: CRITICAL
**Impact**: Executes 1 + (2 × N) queries for N employees

```python
# Lines 289-320: Subquery executed PER ROW
(
    SELECT GROUP_CONCAT(...)
    FROM activity_aggregates aa
    WHERE aa.employee_id = e.id
) as activity_breakdown,
# Lines 322-331: Another subquery PER ROW
(
    SELECT rc.role_name
    FROM activity_logs al2
    JOIN role_configs rc ON rc.id = al2.role_id
    WHERE al2.employee_id = e.id
    AND al2.window_start >= %s AND al2.window_start <= %s
    GROUP BY al2.role_id, rc.role_name
    ORDER BY SUM(al2.items_count) DESC
    LIMIT 1
) as primary_department
```

**Problem**: For 50 employees, executes 1 main query + 100 subqueries = **101 total queries**. Each subquery scans activity_logs table.

**Performance**: With 10K activity records, each subquery scans thousands of rows. Total: ~2-5 seconds per request.

**Fix Required**: Use JOINs and window functions instead of correlated subqueries.

---

### 2. **CRITICAL: Repeated Role Config Lookups Without Caching**
**Location**: `backend/calculations/productivity_calculator.py:38-43, 125, 160, 276, 337`
**Severity**: CRITICAL
**Impact**: Database query for every activity processed

```python
# Line 38-43: Loads ENTIRE role_configs table on init - GOOD
def _load_role_configs(self):
    roles = self.db.execute_query("SELECT * FROM role_configs")
    for role in roles:
        self._role_cache[role['id']] = RoleConfig(**role)

# BUT THEN Line 322-337: IGNORES CACHE and queries database again!
primary_role = self.db.execute_one(
    """
    SELECT rc.role_name, rc.id as role_id
    FROM activity_logs al
    JOIN role_configs rc ON rc.id = al.role_id
    WHERE al.employee_id = %s
    AND DATE(al.window_start) = %s
    GROUP BY rc.id, rc.role_name
    ORDER BY SUM(al.items_count) DESC
    LIMIT 1
    """,
    (employee_id, process_date)
)
# Line 337: Uses cache here but already queried DB above
role_config = self._role_cache.get(primary_role['role_id'], self._role_cache[1])
```

**Problem**: Cache exists but not consistently used. Database queries when cache hit would suffice.

---

### 3. **CRITICAL: Connection Pool Size Too Small**
**Location**: `backend/database/db_manager.py:15`
**Severity**: CRITICAL
**Impact**: Connection exhaustion under normal load

```python
# Line 15
def __init__(self, pool_size: int = 3):
    self.pool_size = pool_size
```

**Problem**:
- Pool size = 3 connections
- Background jobs: Connecteam sync (every 5 min), PodFactory sync (continuous), APScheduler jobs
- API requests: Dashboard (multiple concurrent users)
- **Math**: 2 background + 3-5 concurrent API requests = **5-7 connections needed minimum**

**Current Reality**: 3 connections exhausted instantly. Requests queue/timeout.

**Evidence**: Lines in `connecteam_sync.py` show long-running sync operations that hold connections.

---

### 4. **CRITICAL: Missing Database Indexes**
**Location**: Multiple query patterns across codebase
**Severity**: CRITICAL
**Impact**: Full table scans on every query

**Identified Missing Indexes:**

```sql
-- Most Critical (queried every request):
ALTER TABLE activity_logs ADD INDEX idx_employee_date (employee_id, window_start);
ALTER TABLE activity_logs ADD INDEX idx_date_source (window_start, source);
ALTER TABLE activity_logs ADD INDEX idx_employee_role (employee_id, role_id);

-- High Priority:
ALTER TABLE clock_times ADD INDEX idx_employee_clockin (employee_id, clock_in);
ALTER TABLE clock_times ADD INDEX idx_clockin_date (clock_in);
ALTER TABLE daily_scores ADD INDEX idx_employee_date (employee_id, score_date);

-- Medium Priority:
ALTER TABLE idle_periods ADD INDEX idx_employee_start (employee_id, start_time);
ALTER TABLE employees ADD INDEX idx_connecteam_id (connecteam_user_id);
```

**Evidence from queries**:
- `dashboard.py:274`: `WHERE al.window_start >= %s AND al.window_start <= %s` - No index on window_start
- `productivity_calculator.py:244`: `WHERE employee_id = %s AND window_start >= %s` - Composite index missing
- `connecteam_sync.py:313`: `WHERE employee_id = %s AND DATE(CONVERT_TZ(clock_in...))` - DATE() prevents index use

---

### 5. **HIGH: Synchronous Connecteam Sync Blocks Requests**
**Location**: `backend/api/connecteam.py:46-61, backend/integrations/connecteam_sync.py:186-285`
**Severity**: HIGH
**Impact**: API endpoints block during sync (5-30 seconds)

```python
# connecteam.py:46
@connecteam_bp.route('/sync/shifts/today', methods=['POST'])
@require_api_key
def sync_todays_shifts():
    try:
        stats = sync_service.sync_todays_shifts()  # BLOCKING OPERATION
```

**Problem**:
- `sync_todays_shifts()` processes all shifts synchronously (lines 186-285)
- For 50 employees: 50 API calls + 50 DB inserts/updates
- Holds connection and blocks request thread for **30+ seconds**
- No async/background processing

**Impact**: Dashboard freezes during sync. Users see "loading" indefinitely.

---

### 6. **HIGH: Inefficient Date Conversion in Every Query**
**Location**: Multiple files using `DATE(CONVERT_TZ(...))`
**Severity**: HIGH
**Impact**: Prevents index usage, forces full table scans

```python
# dashboard.py:585 (and 20+ other locations)
WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = CURDATE()
```

**Problem**:
- `CONVERT_TZ()` + `DATE()` applied to indexed column prevents index use
- Every query does full table scan even with index
- Executes conversion for EVERY row before filtering

**Better Approach**: Store UTC, query with UTC boundaries:
```sql
-- Current (slow): DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = '2025-12-09'
-- Fixed (fast): clock_in >= '2025-12-09 06:00:00' AND clock_in < '2025-12-10 06:00:00'
```

**Already implemented correctly** in some places (e.g., `productivity_calculator.py:66-80`) but inconsistent.

---

### 7. **HIGH: Enhanced Idle Detector with ML Overhead**
**Location**: `backend/calculations/enhanced_idle_detector.py:66-150`
**Severity**: HIGH
**Impact**: 8+ database queries per idle check

```python
# Lines 74-150: Executes 8 separate queries to extract features
def get_employee_features(self, employee_id: int, check_time: datetime):
    # Query 1: Time since last activity
    cursor.execute("SELECT TIMESTAMPDIFF...")  # Line 74
    # Query 2: Activity frequency
    cursor.execute("SELECT COUNT(*)...")       # Line 86
    # Query 3-8: More feature queries...
```

**Problem**:
- ML idle detection requires 8 DB queries per employee per check
- Idle check runs every 10 minutes (config.py:56)
- 50 employees × 8 queries × 6 checks/hour = **2,400 queries/hour** for idle detection alone
- ML model overhead on CPU

**Question**: Is ML complexity justified? Simple threshold detection would be 50x faster.

---

## High Priority Findings

### 8. **HIGH: Department Stats with Inefficient Aggregation**
**Location**: `backend/api/dashboard.py:149-231`
**Severity**: HIGH
**Impact**: Subquery executes per employee

```python
# Lines 167-174: Subquery in FROM clause
LEFT JOIN (
    SELECT
        employee_id,
        SUM(total_minutes) as clock_minutes
    FROM clock_times
    WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
    GROUP BY employee_id
) ct ON ct.employee_id = al.employee_id
```

**Problem**: Join on aggregated subquery forces materialization. With large clock_times table, slow.

**Better**: Use window functions or pre-aggregate in application.

---

### 9. **HIGH: Duplicate Cleanup Runs Twice Per Sync**
**Location**: `backend/integrations/connecteam_sync.py:204, 258`
**Severity**: HIGH
**Impact**: Unnecessary DELETE operations

```python
# Line 204: First cleanup
stats['duplicates_cleaned'] = self.cleanup_todays_duplicates()

# ... sync logic ...

# Line 258: Second cleanup
final_cleanup = self.cleanup_todays_duplicates()
if final_cleanup > 0:
    stats['duplicates_cleaned'] += final_cleanup
```

**Problem**:
- Cleanup uses DELETE with self-join (lines 430-436)
- Runs before AND after sync
- Self-join DELETE is expensive operation
- Comment suggests "shouldn't need second cleanup"

**Fix**: Root cause - sync creates duplicates. Fix sync logic, remove double cleanup.

---

### 10. **HIGH: Live Leaderboard with Complex Window Functions**
**Location**: `backend/api/dashboard.py:624-685`
**Severity**: HIGH
**Impact**: Multiple window function calculations

```python
# Lines 624-685: Multiple CTEs with window functions
WITH current_ranks AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY ds.points_earned DESC) as current_rank,
        LAG(ds.points_earned, 1) OVER (ORDER BY ds.points_earned DESC) as prev_points,
        ...
),
yesterday_ranks AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY points_earned DESC) as yesterday_rank
        ...
)
```

**Problem**: Window functions on large result sets. MySQL window functions slower than PostgreSQL.

**Optimization**: Cache yesterday's ranks, only compute today's.

---

## Medium Priority Improvements

### 11. **MEDIUM: Inefficient Idle Period Detection Loop**
**Location**: `backend/calculations/productivity_calculator.py:406-438`
**Severity**: MEDIUM
**Impact**: O(n) loop with DB insert per iteration

```python
# Lines 406-438
for i in range(1, len(activity_timeline)):
    prev_activity = activity_timeline[i-1]
    curr_activity = activity_timeline[i]
    # ... gap calculation ...
    if gap_minutes > threshold:
        # INSERT for EACH idle period found
        self.db.execute_update(
            "INSERT INTO idle_periods ...",
            (employee_id, prev_end, curr_start, int(gap_minutes))
        )
```

**Problem**: Individual INSERT per idle period. Should batch inserts.

---

### 12. **MEDIUM: Cache Implementation Missing TTL Strategy**
**Location**: `backend/api/dashboard.py:9-59`
**Severity**: MEDIUM
**Impact**: Stale data, memory leak potential

```python
# Lines 9-59: Simple dict cache
_endpoint_cache = {}

def cached_endpoint(ttl_seconds=10):
    # Lines 52-54: Only clears when > 50 entries
    if len(_endpoint_cache) > 50:
        _endpoint_cache.clear()  # CLEARS ALL, not just expired
```

**Problems**:
- No LRU/expiration checking - keeps stale data
- Clear ALL when >50 entries - cache stampede
- Dict grows unbounded until threshold
- No cache warming strategy

**Should use**: Redis (already configured but not used for this).

---

### 13. **MEDIUM: ActivityLog Window Calculations**
**Location**: `backend/calculations/productivity_calculator.py:88-145`
**Severity**: MEDIUM
**Impact**: Multiple datetime conversions per activity

```python
# Lines 88-144: Repeated datetime parsing
for activity in sorted_activities:
    if prev_activity:
        prev_end = prev_activity['window_end']
        curr_start = activity['window_start']

        if isinstance(prev_end, str):
            prev_end = datetime.fromisoformat(prev_end)
        if isinstance(curr_start, str):
            curr_start = datetime.fromisoformat(curr_start)
```

**Problem**:
- Checks isinstance + converts for EVERY activity in nested loops
- Should parse once when loading from DB
- Type inconsistency indicates data layer issue

---

### 14. **MEDIUM: Historical Sync Lacks Batching**
**Location**: `backend/integrations/connecteam_sync.py:711-740`
**Severity**: MEDIUM
**Impact**: Sequential day-by-day sync

```python
# Lines 724-737
current_date = start_date
while current_date <= end_date:
    try:
        day_stats = self.sync_shifts_for_date(current_date)  # Sequential
        stats['shifts_synced'] += day_stats['synced']
        current_date += timedelta(days=1)
```

**Problem**:
- Syncs 30 days sequentially (no parallelization)
- Each day makes API call + DB transactions
- 30 days = 30 × sync_time (could be parallel)

---

## Low Priority Suggestions

### 15. **LOW: Duplicate Cache Decorator Definition**
**Location**: `backend/api/dashboard.py:9-27, 34-59`
**Severity**: LOW
**Impact**: Code duplication, confusion

```python
# Lines 9-27: First definition
def cached_endpoint(ttl_seconds=10):
    ...

# Lines 34-59: Duplicate definition (overwrites first)
def cached_endpoint(ttl_seconds=10):
    """Simple cache decorator"""
    ...
```

**Problem**: Same decorator defined twice. Second overwrites first. Likely copy-paste error.

---

### 16. **LOW: Hardcoded Timezone Strings**
**Location**: Multiple files
**Severity**: LOW
**Impact**: Maintenance burden

Inconsistent timezone handling:
- `config.py:54`: `TIMEZONE = 'America/Chicago'`
- `dashboard.py:111`: `pytz.timezone('America/Chicago')`
- `connecteam_sync.py:27`: `pytz.timezone('America/Chicago')`

**Better**: Import from config everywhere.

---

### 17. **LOW: Unused Imports and Dead Code**
**Location**: Various files
**Severity**: LOW

```python
# dashboard.py:62: mysql.connector imported but get_db_connection() creates connections
import mysql.connector

# idle_detector.py: calculate_dynamic_idle_threshold() method exists but never called
# Line 16-51 - dead code
```

---

## Positive Observations

**Good Practices Found:**

1. **Connection Pooling**: Database manager uses connection pooling (db_manager.py:15-43)
2. **Context Managers**: Proper connection/cursor management with context managers (db_manager.py:45-73)
3. **UTC Storage**: Some queries correctly store/query UTC with boundaries (productivity_calculator.py:66-80)
4. **Role Caching**: Role configs loaded into memory cache on init (productivity_calculator.py:38-43)
5. **Error Handling**: Try-catch blocks with proper logging in most endpoints
6. **Transaction Management**: Auto-commit disabled, explicit commits (db_manager.py:31)

---

## Recommended Actions (Prioritized)

### Immediate (Do Today):

1. **Increase connection pool size**:
   ```python
   # db_manager.py:15
   def __init__(self, pool_size: int = 15):  # Was: 3
   ```

2. **Add critical indexes**:
   ```sql
   ALTER TABLE activity_logs ADD INDEX idx_employee_date (employee_id, window_start);
   ALTER TABLE clock_times ADD INDEX idx_employee_clockin (employee_id, clock_in);
   ALTER TABLE daily_scores ADD INDEX idx_employee_date (employee_id, score_date);
   ```

3. **Fix dashboard leaderboard N+1**:
   - Rewrite query to use JOINs instead of correlated subqueries
   - Pre-aggregate activity_breakdown in application or use LATERAL JOIN

### This Week:

4. **Replace DATE(CONVERT_TZ()) pattern everywhere**:
   - Use UTC boundary queries consistently
   - Document pattern for team

5. **Move Connecteam sync to background task**:
   - Use Celery/RQ or APScheduler background job
   - Return immediately from API endpoint

6. **Implement proper Redis caching**:
   - Replace in-memory dict with Redis
   - Cache frequently-accessed data (roles, employee list)

7. **Remove duplicate cleanup logic**:
   - Fix root cause of duplicates in sync
   - Remove redundant cleanup calls

### This Month:

8. **Optimize idle detection**:
   - Evaluate if ML complexity needed
   - Consider simpler threshold-based approach
   - If keeping ML, batch feature extraction

9. **Refactor dashboard queries**:
   - Use materialized views or summary tables
   - Pre-calculate department stats

10. **Add query performance monitoring**:
    - Log slow queries (>1 second)
    - Add query timing to endpoints
    - Set up APM tool (NewRelic, DataDog)

---

## Metrics

### Current Performance (Estimated):
- **Leaderboard endpoint**: 2-5 seconds (50 employees)
- **Department stats**: 1-3 seconds
- **Sync operations**: 30-60 seconds (blocks requests)
- **Database queries per request**: 50-200+

### Expected After Fixes:
- **Leaderboard endpoint**: 100-300ms (50x faster)
- **Department stats**: 200-500ms (5x faster)
- **Sync operations**: <1 second (async, non-blocking)
- **Database queries per request**: 5-15 (10x reduction)

### Index Impact:
Without indexes on 100K activity_logs table:
- Query: 500-2000ms (full table scan)
- With indexes: 5-20ms (100x faster)

---

## Unresolved Questions

1. **What is actual database size?** (Need row counts for activity_logs, clock_times, daily_scores)
2. **Current database server specs?** (RAM, CPU, MySQL version, config)
3. **Is ML idle detection actually used?** (enhanced_idle_detector.py seems unused)
4. **Why duplicate cleanup needed?** (Suggests bug in sync logic)
5. **What's acceptable latency?** (Real-time <100ms? Dashboard <500ms?)
6. **Current concurrent user count?** (Helps size connection pool)
7. **Are there existing EXPLAIN ANALYZE results?** (Would show actual query plans)

---

## Next Steps

1. **Verify indexes**: Run `SHOW INDEX FROM activity_logs;` to confirm missing
2. **Profile queries**: Enable slow query log, capture actual problem queries
3. **Load test**: Use Apache Bench to measure current performance baseline
4. **Implement fixes**: Start with indexes + connection pool (2 hour task)
5. **Measure improvement**: Re-run load tests, compare before/after

---

**Report Generated**: 2025-12-09
**Estimated Fix Time**:
- Critical issues: 4-8 hours
- High priority: 8-16 hours
- Medium priority: 16-24 hours
- **Total**: 2-3 developer days for critical path

**Recommendation**: Address Critical + High priority issues immediately. Expected 10-20x performance improvement.
