# Data Recalculation System - Backend Plan

**Date:** 2025-12-12
**Status:** Draft
**Author:** Claude Planning Agent

---

## 1. Problem Analysis

### 1.1 Tables Requiring Recalculation

| Table | Row Count (Est.) | Derived From | Recalc Complexity |
|-------|------------------|--------------|-------------------|
| `daily_scores` | ~10K | activity_logs, clock_times | HIGH - complex aggregations |
| `idle_periods` | 701K | activity_logs gaps | HIGH - gap detection |
| `alerts` | ~5K | idle_periods, thresholds | MEDIUM - threshold checks |
| `employee_current_status` | ~50 | clock_times, activity_logs | LOW - current state |
| `employee_hourly_costs` | ~50 | daily_scores, pay rates | LOW - simple calc |
| `currently_working` (cache) | ~20 | clock_times | LOW - real-time |
| `today_clock_times` (cache) | ~50 | clock_times | LOW - today filter |
| `working_today` (cache) | ~50 | clock_times | LOW - today filter |
| `employee_primary_roles` | ~50 | activity_logs aggregation | MEDIUM - role detection |

### 1.2 Source Tables (Read-Only During Recalc)

- `activity_logs` (~241K rows) - PodFactory scan data
- `clock_times` - Connecteam time entries
- `employees` - Employee master data
- `role_configs` - Role multipliers & thresholds
- `pay_rates` - Hourly rates

### 1.3 Dependencies Graph

```
activity_logs + clock_times
        |
        v
  daily_scores  -->  employee_hourly_costs
        |
        v
  idle_periods  -->  alerts
        |
        v
employee_primary_roles
        |
        v
employee_current_status (depends on all above)
```

---

## 2. Technical Design

### 2.1 Real-Time Progress Updates - SSE (Server-Sent Events)

**Why SSE over WebSocket/Polling:**
- Simpler implementation (unidirectional)
- Native browser support
- Lower overhead than polling
- Flask has good SSE support via generators
- No need for bidirectional communication

**Implementation Pattern:**
```python
# Flask SSE endpoint
@bp.route('/api/recalculate/stream')
def recalculate_stream():
    def generate():
        yield f"data: {json.dumps({'stage': 'starting'})}\n\n"
        # ... progress updates ...
    return Response(generate(), mimetype='text/event-stream')
```

### 2.2 Recalculation Stages

| Stage | Description | Est. Duration | Rows Affected |
|-------|-------------|---------------|---------------|
| 1 | Clear derived data for date range | 5-10s | Varies |
| 2 | Recalculate daily_scores | 30-60s/day | ~50/day |
| 3 | Detect idle_periods | 20-40s/day | ~100-500/day |
| 4 | Generate alerts | 5-10s/day | ~10-50/day |
| 5 | Update employee_primary_roles | 2-5s | ~50 |
| 6 | Update employee_current_status | 2-5s | ~50 |
| 7 | Refresh Redis cache | 1-2s | N/A |

**Total: ~1-2 min per day of data**

### 2.3 API Design

#### Endpoint 1: Start Recalculation (POST)
```
POST /api/system/recalculate
Content-Type: application/json
X-API-Key: <admin-key>

{
  "start_date": "2025-12-01",
  "end_date": "2025-12-12",
  "tables": ["all"] | ["daily_scores", "idle_periods", ...],
  "clear_existing": true
}

Response: 201 Created
{
  "job_id": "recalc_20251212_164200",
  "status": "queued",
  "estimated_duration_seconds": 120,
  "stream_url": "/api/system/recalculate/stream/recalc_20251212_164200"
}
```

#### Endpoint 2: Progress Stream (SSE)
```
GET /api/system/recalculate/stream/<job_id>
Accept: text/event-stream
X-API-Key: <admin-key>

Response: SSE Stream
event: progress
data: {"stage": 1, "stage_name": "Clearing old data", "progress": 0.5, "message": "Clearing daily_scores..."}

event: progress
data: {"stage": 2, "stage_name": "Recalculating daily_scores", "progress": 0.15, "current": 3, "total": 20, "employee": "John Doe"}

event: complete
data: {"success": true, "duration_seconds": 95, "summary": {...}}

event: error
data: {"error": "Database connection failed", "stage": 2, "can_resume": true}
```

#### Endpoint 3: Job Status (GET)
```
GET /api/system/recalculate/status/<job_id>
X-API-Key: <admin-key>

Response: 200 OK
{
  "job_id": "recalc_20251212_164200",
  "status": "running" | "completed" | "failed" | "cancelled",
  "stage": 2,
  "stage_name": "Recalculating daily_scores",
  "progress": 0.45,
  "started_at": "2025-12-12T16:42:00Z",
  "elapsed_seconds": 45,
  "errors": []
}
```

#### Endpoint 4: Cancel Job (POST)
```
POST /api/system/recalculate/cancel/<job_id>
X-API-Key: <admin-key>

Response: 200 OK
{"cancelled": true, "stage_at_cancel": 2}
```

---

## 3. Implementation Details

### 3.1 New File: `backend/api/recalculate.py`

```python
"""
Data Recalculation API for derived tables
Location: backend/api/recalculate.py
"""

from flask import Blueprint, jsonify, request, Response
from datetime import datetime, date, timedelta
import json
import threading
import uuid
import time
import logging

from database.db_manager import get_db
from calculations.productivity_calculator import ProductivityCalculator
from calculations.idle_detector import IdleDetector
from api.system_control import require_admin_auth

logger = logging.getLogger(__name__)

recalculate_bp = Blueprint('recalculate', __name__)

# In-memory job tracking (consider Redis for production scale)
_active_jobs = {}

class RecalculationJob:
    """Manages a recalculation job with progress tracking"""

    STAGES = [
        ('clear', 'Clearing old data'),
        ('daily_scores', 'Recalculating daily scores'),
        ('idle_periods', 'Detecting idle periods'),
        ('alerts', 'Generating alerts'),
        ('primary_roles', 'Updating primary roles'),
        ('current_status', 'Updating current status'),
        ('cache', 'Refreshing cache')
    ]

    def __init__(self, job_id, start_date, end_date, tables='all', clear_existing=True):
        self.job_id = job_id
        self.start_date = start_date
        self.end_date = end_date
        self.tables = tables
        self.clear_existing = clear_existing

        self.status = 'queued'
        self.current_stage = 0
        self.stage_progress = 0.0
        self.started_at = None
        self.completed_at = None
        self.errors = []
        self.cancelled = False

        # Progress callbacks for SSE
        self._progress_queue = []

        self.db = get_db()
        self.calculator = ProductivityCalculator()
        self.idle_detector = IdleDetector()

    def _emit(self, event_type, data):
        """Emit event to progress queue"""
        self._progress_queue.append({
            'type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })

    def run(self):
        """Execute recalculation"""
        self.status = 'running'
        self.started_at = datetime.now()

        try:
            # Generate date range
            dates = self._get_date_range()
            total_days = len(dates)

            # Stage 1: Clear existing data
            if self.clear_existing:
                self._run_stage(0, self._clear_data, dates)

            # Stage 2: Recalculate daily_scores
            if self._should_recalc('daily_scores'):
                self._run_stage(1, self._recalc_daily_scores, dates)

            # Stage 3: Detect idle periods
            if self._should_recalc('idle_periods'):
                self._run_stage(2, self._recalc_idle_periods, dates)

            # Stage 4: Generate alerts
            if self._should_recalc('alerts'):
                self._run_stage(3, self._recalc_alerts, dates)

            # Stage 5: Update primary roles
            if self._should_recalc('employee_primary_roles'):
                self._run_stage(4, self._update_primary_roles)

            # Stage 6: Update current status
            if self._should_recalc('employee_current_status'):
                self._run_stage(5, self._update_current_status)

            # Stage 7: Refresh cache
            self._run_stage(6, self._refresh_cache)

            self.status = 'completed'
            self.completed_at = datetime.now()

            self._emit('complete', {
                'success': True,
                'duration_seconds': (self.completed_at - self.started_at).total_seconds(),
                'days_processed': total_days,
                'errors': self.errors
            })

        except Exception as e:
            self.status = 'failed'
            self.errors.append(str(e))
            logger.error(f"Recalculation failed: {e}")
            self._emit('error', {
                'error': str(e),
                'stage': self.current_stage,
                'can_resume': True
            })

    def _run_stage(self, stage_idx, func, *args):
        """Run a stage with progress tracking"""
        if self.cancelled:
            raise Exception("Job cancelled")

        self.current_stage = stage_idx
        self.stage_progress = 0.0
        stage_key, stage_name = self.STAGES[stage_idx]

        self._emit('progress', {
            'stage': stage_idx + 1,
            'stage_name': stage_name,
            'progress': 0.0,
            'message': f'Starting {stage_name}...'
        })

        func(*args) if args else func()

        self.stage_progress = 1.0
        self._emit('progress', {
            'stage': stage_idx + 1,
            'stage_name': stage_name,
            'progress': 1.0,
            'message': f'{stage_name} complete'
        })

    def _should_recalc(self, table):
        """Check if table should be recalculated"""
        if self.tables == 'all' or self.tables == ['all']:
            return True
        return table in self.tables

    def _get_date_range(self):
        """Generate list of dates to process"""
        dates = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    def _clear_data(self, dates):
        """Clear existing derived data for date range"""
        # ... implementation

    def _recalc_daily_scores(self, dates):
        """Recalculate daily scores for date range"""
        # ... implementation

    def _recalc_idle_periods(self, dates):
        """Recalculate idle periods for date range"""
        # ... implementation

    def _recalc_alerts(self, dates):
        """Regenerate alerts for date range"""
        # ... implementation

    def _update_primary_roles(self):
        """Update employee primary roles"""
        # ... implementation

    def _update_current_status(self):
        """Update employee current status"""
        # ... implementation

    def _refresh_cache(self):
        """Refresh Redis cache"""
        # ... implementation
```

### 3.2 Detailed Stage Implementations

#### Stage 1: Clear Data
```python
def _clear_data(self, dates):
    """Clear existing derived data for date range"""
    start_str = self.start_date.isoformat()
    end_str = self.end_date.isoformat()

    tables_to_clear = [
        ('daily_scores', 'score_date', 'DELETE FROM daily_scores WHERE score_date BETWEEN %s AND %s'),
        ('idle_periods', 'start_time', 'DELETE FROM idle_periods WHERE DATE(start_time) BETWEEN %s AND %s'),
        ('alerts', 'created_at', 'DELETE FROM alerts WHERE DATE(created_at) BETWEEN %s AND %s AND alert_type = "idle_detected"'),
    ]

    for i, (table, date_col, query) in enumerate(tables_to_clear):
        if not self._should_recalc(table):
            continue

        self._emit('progress', {
            'stage': 1,
            'stage_name': 'Clearing old data',
            'progress': i / len(tables_to_clear),
            'message': f'Clearing {table}...'
        })

        deleted = self.db.execute_update(query, (start_str, end_str))
        logger.info(f"Cleared {deleted} rows from {table}")
```

#### Stage 2: Daily Scores
```python
def _recalc_daily_scores(self, dates):
    """Recalculate daily scores for date range"""
    total = len(dates)

    for i, process_date in enumerate(dates):
        if self.cancelled:
            raise Exception("Job cancelled")

        # Get employees who worked this date
        employees = self.db.execute_query(
            """
            SELECT DISTINCT e.id, e.name
            FROM employees e
            JOIN clock_times ct ON ct.employee_id = e.id
            WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
            AND e.is_active = TRUE
            """,
            (process_date,)
        )

        for j, emp in enumerate(employees):
            try:
                result = self.calculator.process_employee_day(emp['id'], process_date)

                self._emit('progress', {
                    'stage': 2,
                    'stage_name': 'Recalculating daily scores',
                    'progress': (i * len(employees) + j) / (total * max(1, len(employees))),
                    'message': f"Processing {emp['name']} for {process_date}",
                    'current_date': str(process_date),
                    'employee': emp['name']
                })

            except Exception as e:
                self.errors.append(f"daily_scores: {emp['name']} {process_date}: {e}")
                logger.error(f"Error processing {emp['name']} for {process_date}: {e}")
```

#### Stage 3: Idle Periods
```python
def _recalc_idle_periods(self, dates):
    """Recalculate idle periods - leverages existing ProductivityCalculator logic"""
    # Note: idle_periods are already calculated in process_employee_day()
    # via detect_idle_periods(). This stage is mostly a verification/cleanup.

    for i, process_date in enumerate(dates):
        self._emit('progress', {
            'stage': 3,
            'stage_name': 'Detecting idle periods',
            'progress': i / len(dates),
            'message': f"Verifying idle periods for {process_date}"
        })

        # Idle periods are created during daily_scores calculation
        # This stage can do additional validation or gap-filling
```

#### Stage 5: Update Primary Roles
```python
def _update_primary_roles(self):
    """Update employee primary roles based on last 30 days activity"""
    self._emit('progress', {
        'stage': 5,
        'stage_name': 'Updating primary roles',
        'progress': 0.0,
        'message': 'Calculating primary roles from activity history...'
    })

    # Get primary role for each employee (most items by role in last 30 days)
    self.db.execute_update(
        """
        UPDATE employees e
        SET e.primary_role_id = (
            SELECT al.role_id
            FROM activity_logs al
            WHERE al.employee_id = e.id
            AND al.window_start >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY al.role_id
            ORDER BY SUM(al.items_count) DESC
            LIMIT 1
        )
        WHERE e.is_active = TRUE
        """
    )
```

### 3.3 SSE Stream Implementation

```python
@recalculate_bp.route('/api/system/recalculate/stream/<job_id>')
@require_admin_auth
def recalculate_stream(job_id):
    """SSE stream for recalculation progress"""
    if job_id not in _active_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = _active_jobs[job_id]

    def generate():
        last_idx = 0

        while True:
            # Send new events
            while last_idx < len(job._progress_queue):
                event = job._progress_queue[last_idx]
                yield f"event: {event['type']}\n"
                yield f"data: {json.dumps(event['data'])}\n\n"
                last_idx += 1

            # Check if job completed
            if job.status in ('completed', 'failed', 'cancelled'):
                break

            # Heartbeat every 15s to keep connection alive
            yield f": heartbeat\n\n"
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )
```

### 3.4 Blueprint Registration

Update `backend/app.py`:
```python
from api.recalculate import recalculate_bp

def register_blueprints(app):
    # ... existing blueprints ...
    app.register_blueprint(recalculate_bp)
```

---

## 4. Error Handling & Recovery

### 4.1 Error Categories

| Category | Handling | Recovery |
|----------|----------|----------|
| DB Connection | Retry 3x with backoff | Abort if persistent |
| Single Employee Fail | Log, continue to next | Report in summary |
| Stage Timeout | Cancel after 5min/stage | Allow manual resume |
| User Cancellation | Graceful stop | Data remains partial |

### 4.2 Transaction Strategy

- **Per-employee transactions**: Each employee's daily score update is atomic
- **Stage checkpointing**: Track last successful date/employee for resume
- **Rollback on failure**: Only affects current employee, not previous

### 4.3 Resume Capability

```python
@recalculate_bp.route('/api/system/recalculate/resume/<job_id>', methods=['POST'])
@require_admin_auth
def resume_recalculation(job_id):
    """Resume a failed/cancelled job from last checkpoint"""
    # Implementation: Start from last_successful_date + 1
```

---

## 5. Performance Considerations

### 5.1 Batch Processing

```python
# Instead of N individual queries, batch employees per date
employees_by_date = self.db.execute_query(
    """
    SELECT
        DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) as work_date,
        e.id, e.name
    FROM employees e
    JOIN clock_times ct ON ct.employee_id = e.id
    WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
    GROUP BY work_date, e.id, e.name
    """,
    (start_date, end_date)
)
```

### 5.2 Index Verification

Ensure these indexes exist:
```sql
-- activity_logs (most critical for performance)
CREATE INDEX idx_activity_logs_date ON activity_logs (window_start);
CREATE INDEX idx_activity_logs_emp_date ON activity_logs (employee_id, window_start);

-- clock_times
CREATE INDEX idx_clock_times_date ON clock_times (clock_in);
CREATE INDEX idx_clock_times_emp_date ON clock_times (employee_id, clock_in);

-- daily_scores
CREATE INDEX idx_daily_scores_date ON daily_scores (score_date);
```

### 5.3 Memory Management

For 12-day recalculation (~600 employee-days):
- Peak memory: ~50MB for activity logs
- Stream results instead of loading all at once
- Process one date at a time

---

## 6. File Structure Summary

```
backend/
├── api/
│   ├── recalculate.py          # NEW - Main recalculation API
│   └── system_control.py       # MODIFY - Add recalculate route group
├── calculations/
│   ├── productivity_calculator.py  # EXISTING - Core calculation logic
│   ├── idle_detector.py            # EXISTING - Idle detection
│   └── recalculation_engine.py     # NEW - Recalculation orchestration
└── database/
    └── db_manager.py               # EXISTING - No changes needed
```

---

## 7. Testing Plan

### 7.1 Unit Tests

```python
# tests/test_recalculation.py
def test_recalc_single_day():
    """Recalculate single day produces same results as original"""

def test_recalc_date_range():
    """Recalculate date range processes all days"""

def test_recalc_cancel():
    """Job can be cancelled mid-execution"""

def test_recalc_resume():
    """Failed job can resume from checkpoint"""
```

### 7.2 Integration Tests

- SSE stream delivers all events
- Progress percentages are accurate
- Errors don't crash the stream
- Multiple concurrent jobs are isolated

---

## 8. Implementation Checklist

- [ ] Create `backend/api/recalculate.py` with RecalculationJob class
- [ ] Implement SSE streaming endpoint
- [ ] Implement 7 recalculation stages
- [ ] Add error handling and recovery
- [ ] Register blueprint in `app.py`
- [ ] Add database indexes if missing
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update API documentation

---

## 9. Unresolved Questions

1. **Concurrent Jobs**: Should we allow multiple recalculation jobs simultaneously?
   - Recommendation: No, use a lock. One job at a time.

2. **Data Retention**: When clearing data for recalc, should we archive first?
   - Recommendation: No archive for MVP, add later if needed.

3. **Notification**: Should we email admin when recalc completes?
   - Recommendation: Not for MVP, frontend handles completion.

4. **Rate Limiting**: Should there be a cooldown between recalc requests?
   - Recommendation: Yes, 5-minute minimum between runs.

---

## 10. Dependencies

- Flask SSE support (built-in via generators)
- Existing `ProductivityCalculator` class
- Existing `IdleDetector` class
- Redis for cache refresh (optional, graceful fallback)
- MySQL 8.0+ for date functions

---

**Next Steps:**
1. Review plan with stakeholders
2. Frontend team can start UI design in parallel
3. Backend implementation in order: API skeleton -> SSE -> Stages -> Error handling
