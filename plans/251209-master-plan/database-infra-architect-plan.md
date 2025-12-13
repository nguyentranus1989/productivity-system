# Database & Infrastructure Architecture Plan

**Author:** Database & Infrastructure Architect
**Date:** 2025-12-09
**System:** Productivity Hub
**Status:** REVIEW DRAFT

---

## Executive Summary

Critical performance issues stem from missing indexes, inefficient timezone conversions in queries, undersized connection pools, and unutilized Redis cache. This plan provides specific SQL migrations, implementation priorities, and risk assessments for each recommendation.

**Impact Estimates:**
- Query performance: 60-80% improvement
- API response times: 40-50% reduction
- Database load: 30-40% reduction via caching

---

## 1. Index Strategy

### 1.1 Critical Missing Indexes (Priority: IMMEDIATE)

**Current State:** No indexes beyond primary keys detected. Full table scans on every query.

```sql
-- Migration: 001_add_critical_indexes.sql
-- Estimated execution time: 2-5 minutes per table (depends on row count)
-- Risk: LOW (online DDL in MySQL 8.0+)

-- Activity Logs: Primary query table (most impacted)
ALTER TABLE activity_logs
  ADD INDEX idx_activity_employee_window (employee_id, window_start),
  ADD INDEX idx_activity_window_start (window_start),
  ADD INDEX idx_activity_role (role_id),
  ADD INDEX idx_activity_report_id (report_id);

-- Clock Times: Second most queried table
ALTER TABLE clock_times
  ADD INDEX idx_clock_employee_in (employee_id, clock_in),
  ADD INDEX idx_clock_in_date (clock_in),
  ADD INDEX idx_clock_source (source);

-- Daily Scores: Frequently joined and filtered
ALTER TABLE daily_scores
  ADD INDEX idx_daily_employee_date (employee_id, score_date),
  ADD INDEX idx_daily_date (score_date);

-- Supporting tables
ALTER TABLE idle_periods
  ADD INDEX idx_idle_employee_start (employee_id, start_time);

ALTER TABLE employees
  ADD INDEX idx_employee_connecteam (connecteam_user_id),
  ADD INDEX idx_employee_active (is_active);

ALTER TABLE achievements
  ADD INDEX idx_achievement_employee (employee_id, earned_date),
  ADD INDEX idx_achievement_key (achievement_key);
```

**Performance Impact:**
| Table | Current Query Time | Expected After | Improvement |
|-------|-------------------|----------------|-------------|
| activity_logs | ~500ms | ~50ms | 90% |
| clock_times | ~300ms | ~30ms | 90% |
| daily_scores | ~200ms | ~20ms | 90% |

**Risk Assessment:** LOW
- MySQL 8.0 supports online DDL for index creation
- No table locks required
- Run during low-traffic hours as precaution
- Rollback: `DROP INDEX idx_name ON table_name;`

### 1.2 Covering Indexes for Hot Queries

```sql
-- Migration: 002_covering_indexes.sql
-- These indexes include all columns needed by specific queries

-- Dashboard main query: avoids table lookup
ALTER TABLE activity_logs
  ADD INDEX idx_activity_covering
    (employee_id, window_start, items_count, role_id);

-- Leaderboard query optimization
ALTER TABLE daily_scores
  ADD INDEX idx_daily_covering
    (employee_id, score_date, points_earned, items_processed);

-- Clock time lookups with all needed fields
ALTER TABLE clock_times
  ADD INDEX idx_clock_covering
    (employee_id, clock_in, clock_out, total_minutes, is_active);
```

**Performance Impact:** Additional 20-30% improvement for covered queries.

---

## 2. Query Optimization

### 2.1 UTC Boundary Pre-calculation (Priority: HIGH)

**Problem:** `CONVERT_TZ()` and `DATE()` on columns prevents index usage.

**Current Pattern (found 100+ occurrences):**
```sql
-- BAD: Function on column = no index
WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = CURDATE()
```

**Solution: Pre-calculate UTC boundaries in application code.**

```python
# backend/utils/timezone_helpers.py - ADD METHOD
class TimezoneHelper:
    def ct_date_to_utc_range(self, ct_date: date) -> Tuple[datetime, datetime]:
        """Convert Central Time date to UTC datetime range for queries"""
        ct_tz = pytz.timezone('America/Chicago')

        # Start of day in CT
        start_ct = ct_tz.localize(datetime.combine(ct_date, time.min))
        # End of day in CT (actually start of next day)
        end_ct = ct_tz.localize(datetime.combine(ct_date + timedelta(days=1), time.min))

        # Convert to UTC
        utc_start = start_ct.astimezone(pytz.UTC)
        utc_end = end_ct.astimezone(pytz.UTC)

        return utc_start, utc_end
```

**Refactored Query Pattern:**
```sql
-- GOOD: Range query uses index
WHERE clock_in >= %s AND clock_in < %s
-- Parameters: (utc_start, utc_end)
```

### 2.2 Specific Query Refactoring

**File: backend/api/dashboard.py (Primary Target)**

```python
# BEFORE (Line ~173)
"""
WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
"""

# AFTER
utc_start, utc_end = tz_helper.ct_date_to_utc_range(target_date)
"""
WHERE clock_in >= %s AND clock_in < %s
"""
params = (utc_start, utc_end)
```

**Queries requiring refactoring (by file):**
| File | Count | Priority |
|------|-------|----------|
| api/dashboard.py | 45+ | HIGH |
| integrations/connecteam_sync.py | 12+ | HIGH |
| calculations/productivity_calculator.py | 8 | MEDIUM |
| calculations/activity_processor.py | 6 | MEDIUM |
| auto_reconciliation.py | 4 | LOW |

### 2.3 Denormalization for Dashboard

**Problem:** Dashboard makes 8+ queries per page load.

**Solution:** Add materialized summary columns.

```sql
-- Migration: 003_dashboard_optimization.sql

-- Add pre-calculated fields to daily_scores
ALTER TABLE daily_scores
  ADD COLUMN first_activity_time TIME NULL,
  ADD COLUMN last_activity_time TIME NULL,
  ADD COLUMN activity_count INT DEFAULT 0,
  ADD COLUMN idle_count INT DEFAULT 0;

-- Trigger to maintain on insert/update
DELIMITER //
CREATE TRIGGER trg_daily_scores_update
BEFORE UPDATE ON daily_scores
FOR EACH ROW
BEGIN
  -- Auto-update from related tables during calculation job
  SET NEW.updated_at = CURRENT_TIMESTAMP;
END//
DELIMITER ;
```

**Application Code Update:**
```python
# In productivity_calculator.py process_employee_day()
# Add to the UPDATE statement:
first_activity_time = activities[0]['window_start'].time() if activities else None
last_activity_time = activities[-1]['window_end'].time() if activities else None
```

---

## 3. Caching Layer (Redis Implementation)

### 3.1 Current State Analysis

Redis is configured but barely used:
- `cache_manager.py` exists with basic get/set
- Only used for `working_today` and `currently_working` in Connecteam sync
- 99% of cacheable data bypasses Redis

### 3.2 Caching Strategy

**Tier 1: Hot Data (TTL: 60 seconds)**
```python
# Add to api/dashboard.py
CACHE_KEYS = {
    'dashboard_summary': 'dashboard:summary:{date}',        # TTL: 60s
    'working_today': 'workers:today:{date}',                # TTL: 60s
    'currently_working': 'workers:active',                  # TTL: 30s
}
```

**Tier 2: Warm Data (TTL: 5 minutes)**
```python
CACHE_KEYS.update({
    'employee_daily': 'employee:{id}:daily:{date}',         # TTL: 300s
    'leaderboard_daily': 'leaderboard:daily:{date}',        # TTL: 300s
    'team_metrics': 'metrics:team:{date}',                  # TTL: 300s
})
```

**Tier 3: Cold Data (TTL: 1 hour)**
```python
CACHE_KEYS.update({
    'employee_trends': 'employee:{id}:trends',              # TTL: 3600s
    'role_configs': 'config:roles',                         # TTL: 3600s
    'historical_summary': 'summary:historical:{period}',    # TTL: 3600s
})
```

### 3.3 Implementation

```python
# backend/api/cache_decorator.py - NEW FILE
from functools import wraps
from database.cache_manager import get_cache_manager
import json
import hashlib

def cached(key_template: str, ttl: int = 300):
    """Decorator for caching API responses"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()

            # Build cache key from template and args
            cache_key = key_template.format(**kwargs)

            # Try cache first
            cached_value = cache.get_json(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache.set_json(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

# Usage example in dashboard.py:
@cached('dashboard:summary:{date}', ttl=60)
def get_dashboard_summary(date):
    # ... existing query logic
    pass
```

### 3.4 Cache Invalidation Strategy

```python
# backend/database/cache_invalidator.py - NEW FILE
class CacheInvalidator:
    """Centralized cache invalidation"""

    INVALIDATION_MAP = {
        'activity_logs': ['dashboard:*', 'employee:*:daily:*'],
        'clock_times': ['workers:*', 'employee:*:daily:*'],
        'daily_scores': ['leaderboard:*', 'employee:*:trends'],
        'employees': ['config:*', 'workers:*'],
    }

    def invalidate_for_table(self, table_name: str):
        """Invalidate all caches affected by table changes"""
        cache = get_cache_manager()
        patterns = self.INVALIDATION_MAP.get(table_name, [])
        for pattern in patterns:
            cache.clear_pattern(pattern)
```

### 3.5 Performance Impact

| Endpoint | Current | With Cache | Improvement |
|----------|---------|------------|-------------|
| GET /api/dashboard | 800ms | 50ms | 94% |
| GET /api/gamification/leaderboard | 400ms | 30ms | 92% |
| GET /api/activities | 500ms | 80ms | 84% |

---

## 4. Data Archiving

### 4.1 Problem Statement

Tables grow unbounded:
- `activity_logs`: ~10K rows/day = 3.6M rows/year
- `clock_times`: ~100 rows/day = 36K rows/year
- `idle_periods`: ~200 rows/day = 73K rows/year

### 4.2 Archive Schema

```sql
-- Migration: 004_archive_tables.sql

-- Archive table for activity_logs
CREATE TABLE activity_logs_archive (
  id BIGINT NOT NULL,
  report_id VARCHAR(50),
  employee_id INT,
  role_id INT,
  items_count INT,
  window_start DATETIME,
  window_end DATETIME,
  source VARCHAR(50),
  created_at DATETIME,
  archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  archive_batch_id VARCHAR(36),
  PRIMARY KEY (id, window_start),  -- Partitioned by window_start
  KEY idx_archive_date (window_start),
  KEY idx_archive_employee (employee_id)
) ENGINE=InnoDB
PARTITION BY RANGE (YEAR(window_start) * 100 + MONTH(window_start)) (
  PARTITION p202401 VALUES LESS THAN (202402),
  PARTITION p202402 VALUES LESS THAN (202403),
  -- ... add partitions as needed
  PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- Archive table for clock_times
CREATE TABLE clock_times_archive LIKE clock_times;
ALTER TABLE clock_times_archive
  ADD COLUMN archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN archive_batch_id VARCHAR(36);

-- Archive table for idle_periods
CREATE TABLE idle_periods_archive LIKE idle_periods;
ALTER TABLE idle_periods_archive
  ADD COLUMN archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN archive_batch_id VARCHAR(36);

-- Archive table for daily_scores (optional - smaller table)
CREATE TABLE daily_scores_archive LIKE daily_scores;
ALTER TABLE daily_scores_archive
  ADD COLUMN archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN archive_batch_id VARCHAR(36);
```

### 4.3 Archive Procedure

```sql
-- Migration: 005_archive_procedure.sql

DELIMITER //

CREATE PROCEDURE archive_old_data(IN retention_days INT)
BEGIN
  DECLARE batch_id VARCHAR(36);
  DECLARE rows_archived INT DEFAULT 0;

  SET batch_id = UUID();

  -- Start transaction
  START TRANSACTION;

  -- Archive activity_logs older than retention_days
  INSERT INTO activity_logs_archive
    (id, report_id, employee_id, role_id, items_count,
     window_start, window_end, source, created_at, archive_batch_id)
  SELECT id, report_id, employee_id, role_id, items_count,
         window_start, window_end, source, created_at, batch_id
  FROM activity_logs
  WHERE window_start < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  SET rows_archived = ROW_COUNT();

  -- Delete archived rows
  DELETE FROM activity_logs
  WHERE window_start < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  -- Archive clock_times
  INSERT INTO clock_times_archive
    (id, employee_id, clock_in, clock_out, total_minutes, break_minutes,
     is_active, source, created_at, updated_at, archive_batch_id)
  SELECT id, employee_id, clock_in, clock_out, total_minutes, break_minutes,
         is_active, source, created_at, updated_at, batch_id
  FROM clock_times
  WHERE clock_in < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  DELETE FROM clock_times
  WHERE clock_in < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  -- Archive idle_periods
  INSERT INTO idle_periods_archive
  SELECT *, NOW(), batch_id FROM idle_periods
  WHERE start_time < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  DELETE FROM idle_periods
  WHERE start_time < DATE_SUB(CURDATE(), INTERVAL retention_days DAY);

  COMMIT;

  -- Log archive operation
  INSERT INTO archive_log (batch_id, rows_archived, retention_days, archived_at)
  VALUES (batch_id, rows_archived, retention_days, NOW());

  SELECT batch_id, rows_archived;
END//

DELIMITER ;
```

### 4.4 Scheduled Archive Job

```python
# backend/jobs/archive_job.py - NEW FILE
from apscheduler.schedulers.background import BackgroundScheduler
from database.db_manager import get_db

def run_archive():
    """Run weekly archive job"""
    db = get_db()
    retention_days = 90  # Keep 90 days in active tables

    result = db.execute_one(
        "CALL archive_old_data(%s)",
        (retention_days,)
    )

    logger.info(f"Archive complete: batch={result['batch_id']}, rows={result['rows_archived']}")

# Schedule: Every Sunday at 2 AM
scheduler = BackgroundScheduler()
scheduler.add_job(run_archive, 'cron', day_of_week='sun', hour=2)
```

### 4.5 Retention Policy

| Data Type | Active Table | Archive | Total Retention |
|-----------|-------------|---------|-----------------|
| activity_logs | 90 days | 2 years | 2+ years |
| clock_times | 90 days | 2 years | 2+ years |
| daily_scores | 365 days | 5 years | 5+ years |
| idle_periods | 30 days | 1 year | 1+ year |

---

## 5. Connection Management

### 5.1 Current State

```python
# db_manager.py line 15
pool_size: int = 3  # TOO SMALL
```

**Problems:**
- Pool exhaustion during sync jobs
- Connection timeout errors during peak usage
- No connection reuse optimization

### 5.2 Recommended Configuration

```python
# backend/database/db_manager.py - MODIFY

class DatabaseManager:
    def __init__(self, pool_size: int = None):
        # Calculate pool size based on environment
        if pool_size is None:
            if Config.IS_PRODUCTION:
                self.pool_size = 10  # Production: more connections
            else:
                self.pool_size = 5   # Development: fewer
        else:
            self.pool_size = pool_size

        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._initialize_pool()

    def _initialize_pool(self):
        config = {
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'database': Config.DB_NAME,
            'pool_size': self.pool_size,
            'pool_reset_session': True,
            'autocommit': False,
            'raise_on_warnings': False,  # Changed: avoid warnings blocking
            'connection_timeout': 30,     # New: 30 second timeout
            'buffered': True,             # New: fetch all results
        }

        self._pool = pooling.MySQLConnectionPool(
            pool_name="productivity_pool",
            **config
        )
```

### 5.3 Connection Pool Monitoring

```python
# backend/database/pool_monitor.py - NEW FILE
class PoolMonitor:
    """Monitor connection pool health"""

    @staticmethod
    def get_pool_stats():
        """Get current pool statistics"""
        pool = db_manager._pool
        return {
            'pool_size': pool.pool_size,
            'pool_name': pool.pool_name,
            # MySQL connector doesn't expose active connections
            # Use application-level tracking
        }

    @staticmethod
    def health_check():
        """Verify pool is healthy"""
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return {'status': 'healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
```

### 5.4 Separate Pool for Sync Jobs

```python
# backend/database/sync_pool.py - NEW FILE
"""Dedicated connection pool for sync operations"""

sync_pool = DatabaseManager(pool_size=3)

# Use in connecteam_sync.py:
class ConnecteamSync:
    def __init__(self, api_key: str, clock_id: int):
        from database.sync_pool import sync_pool
        self.db = sync_pool  # Separate from main pool
```

---

## 6. Sync Optimization

### 6.1 Current Problems

1. **Blocking syncs**: Sync jobs block each other via `sync_locks` table
2. **Full table scans**: Each sync reads all today's records
3. **Duplicate detection**: Expensive `DELETE ... INNER JOIN` queries
4. **No batching**: Processes one shift at a time

### 6.2 Non-Blocking Sync Architecture

```python
# backend/integrations/async_sync_manager.py - NEW FILE
import threading
from queue import Queue
from typing import Dict, List

class AsyncSyncManager:
    """Non-blocking sync with queue-based processing"""

    def __init__(self):
        self.shift_queue = Queue()
        self.processing = False
        self._start_worker()

    def _start_worker(self):
        """Start background worker thread"""
        worker = threading.Thread(target=self._process_queue, daemon=True)
        worker.start()

    def enqueue_shifts(self, shifts: List[Dict]):
        """Add shifts to processing queue"""
        for shift in shifts:
            self.shift_queue.put(shift)

    def _process_queue(self):
        """Process shifts from queue"""
        while True:
            batch = []
            # Collect batch of 50 shifts or wait 5 seconds
            while len(batch) < 50:
                try:
                    shift = self.shift_queue.get(timeout=5)
                    batch.append(shift)
                except:
                    break

            if batch:
                self._process_batch(batch)

    def _process_batch(self, shifts: List[Dict]):
        """Process batch of shifts efficiently"""
        # Group by employee
        by_employee = {}
        for shift in shifts:
            emp_id = shift['employee_id']
            if emp_id not in by_employee:
                by_employee[emp_id] = []
            by_employee[emp_id].append(shift)

        # Batch insert/update
        for emp_id, emp_shifts in by_employee.items():
            self._upsert_clock_times(emp_id, emp_shifts)
```

### 6.3 Batch Insert/Update

```sql
-- Optimized upsert for clock_times
INSERT INTO clock_times
  (employee_id, clock_in, clock_out, total_minutes, is_active, source)
VALUES
  (%s, %s, %s, %s, %s, 'connecteam'),
  (%s, %s, %s, %s, %s, 'connecteam'),
  -- ... batch values
ON DUPLICATE KEY UPDATE
  clock_out = VALUES(clock_out),
  total_minutes = VALUES(total_minutes),
  is_active = VALUES(is_active),
  updated_at = NOW();
```

### 6.4 Incremental Sync with Watermarks

```python
# backend/integrations/incremental_sync.py - NEW FILE
class IncrementalSync:
    """Sync only changed records since last sync"""

    def __init__(self, db):
        self.db = db

    def get_last_sync_time(self, sync_type: str) -> datetime:
        """Get last successful sync timestamp"""
        result = self.db.execute_one(
            "SELECT MAX(synced_at) as last_sync FROM connecteam_sync_log "
            "WHERE sync_type = %s AND status = 'success'",
            (sync_type,)
        )
        return result['last_sync'] if result else None

    def sync_changes_since(self, sync_type: str, since: datetime):
        """Only sync records modified since timestamp"""
        # Query Connecteam API with modified_since parameter
        # Process only changed records
        pass
```

### 6.5 Duplicate Prevention

```sql
-- Add unique constraint instead of runtime duplicate checking
ALTER TABLE clock_times
  ADD UNIQUE KEY uk_employee_clock_in (employee_id, clock_in);

-- Then use INSERT IGNORE or ON DUPLICATE KEY UPDATE
INSERT IGNORE INTO clock_times (...) VALUES (...);
```

---

## 7. Future Scaling

### 7.1 Read Replica Setup (Phase 2)

**When to implement:** When daily_scores > 1M rows OR concurrent users > 50

```
                    ┌─────────────┐
                    │   Primary   │ (Writes)
                    │    MySQL    │
                    └──────┬──────┘
                           │ Replication
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌────▼────┐ ┌────▼────┐
        │  Replica  │ │ Replica │ │ Replica │ (Reads)
        │     1     │ │    2    │ │    3    │
        └───────────┘ └─────────┘ └─────────┘
```

**Application changes:**
```python
# backend/database/read_replica.py
class ReplicaManager:
    def __init__(self):
        self.primary = DatabaseManager()
        self.replica = DatabaseManager(host=Config.DB_REPLICA_HOST)

    def read(self, query, params=None):
        """Route reads to replica"""
        return self.replica.execute_query(query, params)

    def write(self, query, params=None):
        """Route writes to primary"""
        return self.primary.execute_update(query, params)
```

### 7.2 Sharding Strategy (Phase 3)

**When to implement:** When activity_logs > 100M rows

**Sharding key:** `employee_id`

```
┌─────────────────┐
│  Shard Router   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌───▼───┐
│Shard 1│ │Shard 2│
│emp 1-X│ │emp X+1│
└───────┘ └───────┘
```

### 7.3 Time-Series Optimization (Phase 3)

For activity_logs, consider TimescaleDB extension:
```sql
-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('activity_logs', 'window_start');

-- Automatic partitioning by time
-- Built-in compression for old data
-- Optimized time-range queries
```

---

## 8. Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
| Task | Risk | Effort | Impact |
|------|------|--------|--------|
| Add critical indexes | LOW | 2h | HIGH |
| Increase pool size | LOW | 30m | MEDIUM |
| Add unique constraint on clock_times | LOW | 1h | MEDIUM |

### Phase 2: Query Optimization (Week 2-3)
| Task | Risk | Effort | Impact |
|------|------|--------|--------|
| Refactor CONVERT_TZ queries | MEDIUM | 8h | HIGH |
| Implement Redis caching | LOW | 4h | HIGH |
| Add covering indexes | LOW | 1h | MEDIUM |

### Phase 3: Architecture (Week 4-6)
| Task | Risk | Effort | Impact |
|------|------|--------|--------|
| Implement data archiving | MEDIUM | 8h | MEDIUM |
| Non-blocking sync | MEDIUM | 16h | HIGH |
| Batch processing | LOW | 8h | MEDIUM |

### Phase 4: Future Scale (When Needed)
| Task | Risk | Effort | Impact |
|------|------|--------|--------|
| Read replica setup | HIGH | 40h | HIGH |
| Sharding implementation | HIGH | 80h | HIGH |

---

## 9. Monitoring & Alerting

### 9.1 Key Metrics to Track

```sql
-- Query for slow query monitoring
SELECT * FROM mysql.slow_log
WHERE start_time > DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY query_time DESC LIMIT 10;

-- Connection pool status
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Threads_running';

-- Table sizes
SELECT
  table_name,
  table_rows,
  ROUND(data_length/1024/1024, 2) as data_mb,
  ROUND(index_length/1024/1024, 2) as index_mb
FROM information_schema.tables
WHERE table_schema = 'productivity_tracker'
ORDER BY data_length DESC;
```

### 9.2 Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Query time avg | > 500ms | > 2000ms |
| Connection usage | > 70% | > 90% |
| Table size (activity_logs) | > 5M rows | > 10M rows |
| Replication lag | > 5s | > 30s |

---

## 10. Risk Assessment Summary

| Change | Risk Level | Mitigation |
|--------|-----------|------------|
| Add indexes | LOW | Online DDL, can drop if issues |
| Query refactoring | MEDIUM | Thorough testing, gradual rollout |
| Connection pool changes | LOW | Easy rollback via config |
| Redis caching | LOW | Graceful degradation if Redis fails |
| Data archiving | MEDIUM | Test with backup, verify restoration |
| Sync optimization | MEDIUM | Feature flags, A/B testing |
| Read replicas | HIGH | Extensive testing, replication monitoring |

---

## Points for Discussion

1. **Archive retention policy**: Currently proposed 90 days active, 2 years archive. Business requirements may differ. Need input from stakeholders on compliance/audit needs.

2. **Redis failover strategy**: Current code silently continues if Redis fails. Should we:
   - Log and alert?
   - Queue requests for retry?
   - Fall back to shorter DB caching?

3. **Sync frequency trade-offs**:
   - Current: Every 5 minutes
   - Proposed async: Near real-time
   - Impact on Connecteam API rate limits?

4. **Index maintenance window**: Need to coordinate with operations for initial index creation if tables are large. What's the acceptable maintenance window?

5. **Read replica budget**: DigitalOcean read replica adds ~$15-30/month. Is this approved for Phase 4?

6. **Historical data access**: After archiving, how should API handle requests for data older than 90 days? Separate endpoint? Automatic query routing?

7. **Cache warming strategy**: On application restart, cache is cold. Should we implement cache warming on startup for critical endpoints?

8. **Monitoring tooling**: Current system lacks APM. Consider:
   - New Relic / Datadog for query analysis
   - Prometheus + Grafana for metrics
   - Budget implications?
