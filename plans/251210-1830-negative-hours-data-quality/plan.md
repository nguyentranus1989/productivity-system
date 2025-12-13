# Negative Hours Data Quality Fix Plan

**Created:** 2025-12-10
**Updated:** 2025-12-11 (Code Review Completed)
**Status:** ON HOLD - Critical issues found in code review
**Priority:** CRITICAL

## Problem Statement

Cost Analysis shows negative hours for some employees (e.g., -1.88h, -0.80h, -1.98h) due to **bad data** in `clock_times` table where `clock_out < clock_in` (impossible shifts).

**Root Cause:** Connecteam API returns Unix timestamps; `datetime.fromtimestamp()` uses local machine timezone. If Connecteam stores UTC but local machine is Central, clock_out timestamp appears BEFORE clock_in when shift crosses midnight or timezone boundaries.

**Example:**
- Employee clocks in at 22:13 UTC (5:13 PM CT)
- clock_out shows 13:00 UTC same day (8:00 AM CT) - but this is actually NEXT day
- `TIMESTAMPDIFF(MINUTE, clock_in, clock_out)` returns negative value

## Solution Strategy

Multi-layer defense: validate at sync time, protect at query time, clean existing bad data.

---

## Phase 1: Query-Time Protection (Immediate Safety)

### 1.1 Add GREATEST() wrapper to Cost Analysis query

**File:** `backend/api/dashboard.py`
**Function:** `get_cost_analysis()` (line 3440)

**Current:**
```sql
SUM(TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW()))) / 60.0
```

**Fix:**
```sql
SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())))) / 60.0
```

**Locations to update in Cost Analysis query:**
1. Line 3441 - `employee_hours` CTE clocked_hours calculation
2. Any other `TIMESTAMPDIFF` using clock_in/clock_out

### 1.2 Add validation filter to exclude impossible shifts

**Alternative approach:** Exclude bad records entirely

```sql
AND (clock_out IS NULL OR clock_out >= clock_in)
```

Add to WHERE clauses that calculate hours from `clock_times`.

### 1.3 Update other affected endpoints

Search for other TIMESTAMPDIFF usages on clock_times:

| Line | Context | Action |
|------|---------|--------|
| 318 | Leaderboard clock times | Add GREATEST(0, ...) |
| 558-561 | Working today query | Add validation |
| 626-634 | Activity aggregates | Add GREATEST(0, ...) |
| 825 | Clock minutes calculation | Add GREATEST(0, ...) |
| 1275 | Dashboard stats | Add GREATEST(0, ...) |
| 1421 | Clock minutes | Add GREATEST(0, ...) |

---

## Phase 2: Sync-Time Validation (Prevention)

### 2.1 Validate timestamps in `_parse_shift()`

**File:** `backend/integrations/connecteam_client.py`
**Function:** `_parse_shift()` (line 260)

**Add after line 282:**
```python
# Validate: clock_out must be after clock_in
if clock_out and clock_out < clock_in:
    logger.warning(
        f"Invalid shift for {employee_name}: clock_out ({clock_out}) before clock_in ({clock_in}). "
        f"Raw timestamps: start={clock_in_timestamp}, end={clock_out_timestamp}"
    )
    # Attempt fix: if clock_out is same day but earlier, assume it's next day
    if clock_out.date() == clock_in.date():
        clock_out = clock_out + timedelta(days=1)
        total_minutes = (clock_out - clock_in).total_seconds() / 60
        logger.info(f"Auto-corrected clock_out to next day: {clock_out}")
    else:
        # Can't auto-fix, skip this shift or log for manual review
        logger.error(f"Cannot auto-correct shift - dates differ. Skipping.")
        return None
```

### 2.2 Add timezone awareness to timestamp parsing

**Current (line 271):**
```python
clock_in = datetime.fromtimestamp(clock_in_timestamp)
```

**Issue:** Uses local timezone, not UTC.

**Fix:**
```python
import pytz

# Parse as UTC (Connecteam timestamps are UTC)
clock_in = datetime.utcfromtimestamp(clock_in_timestamp).replace(tzinfo=pytz.UTC)
# ... same for clock_out
clock_out = datetime.utcfromtimestamp(clock_out_timestamp).replace(tzinfo=pytz.UTC)
```

**Note:** This requires checking how times are stored/used downstream. Currently stored naive in Central Time.

### 2.3 Add validation in `_sync_clock_time()`

**File:** `backend/integrations/connecteam_sync.py`
**Function:** `_sync_clock_time()` (line 297)

**Add validation before INSERT:**
```python
# Validate before writing
if shift.clock_out and shift.clock_out < shift.clock_in:
    logger.error(f"Refusing to sync invalid shift for employee {employee_id}: "
                 f"clock_out {shift.clock_out} < clock_in {shift.clock_in}")
    return True  # Pretend we updated to avoid retries
```

---

## Phase 3: Data Correction (Fix Existing Bad Data)

### 3.1 Create data audit script

**New File:** `backend/scripts/audit_clock_times.py`

```python
"""Audit and report invalid clock_times records"""

def find_invalid_shifts():
    """Find all records where clock_out < clock_in"""
    query = """
    SELECT
        ct.id,
        ct.employee_id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, ct.clock_out) as minutes_diff,
        ct.source
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE ct.clock_out IS NOT NULL
      AND ct.clock_out < ct.clock_in
    ORDER BY ct.clock_in DESC
    """
    # Execute and report

def fix_invalid_shifts(dry_run=True):
    """
    Attempt to fix invalid shifts:
    1. If clock_out is same day but earlier hour, add 1 day
    2. If clock_out is previous day, add 1 day
    3. If unfixable, mark as invalid (set flag or delete)
    """
    pass
```

### 3.2 Create migration/fix script

**New File:** `backend/scripts/fix_negative_hours.py`

```python
"""One-time script to fix negative hours in clock_times"""

def fix_records():
    # Find problematic records
    invalid_records = """
    SELECT id, employee_id, clock_in, clock_out
    FROM clock_times
    WHERE clock_out < clock_in
    """

    for record in records:
        clock_in = record['clock_in']
        clock_out = record['clock_out']

        # Most likely fix: clock_out is next day
        fixed_clock_out = clock_out + timedelta(days=1)

        # Sanity check: shift should be < 16 hours
        shift_hours = (fixed_clock_out - clock_in).total_seconds() / 3600
        if 0 < shift_hours <= 16:
            # Apply fix
            UPDATE clock_times SET clock_out = %s WHERE id = %s
        else:
            # Log for manual review
            logger.warning(f"Cannot auto-fix record {record['id']}, shift would be {shift_hours}h")
```

### 3.3 Add data quality table

**Schema addition:**
```sql
CREATE TABLE IF NOT EXISTS data_quality_issues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INT NOT NULL,
    issue_type VARCHAR(50) NOT NULL,
    issue_details JSON,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    resolution_type VARCHAR(50),
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_issue_type (issue_type)
);
```

---

## Phase 4: Monitoring & Alerts

### 4.1 Add health check for data quality

**File:** `backend/api/dashboard.py` or new `backend/api/health.py`

```python
@bp.route('/health/data-quality', methods=['GET'])
def data_quality_check():
    """Check for data quality issues"""
    issues = []

    # Check for negative hours
    negative_hours = db.execute_query("""
        SELECT COUNT(*) as count
        FROM clock_times
        WHERE clock_out < clock_in
    """)
    if negative_hours[0]['count'] > 0:
        issues.append({
            'type': 'negative_hours',
            'count': negative_hours[0]['count'],
            'severity': 'high'
        })

    return jsonify({
        'status': 'warning' if issues else 'healthy',
        'issues': issues
    })
```

### 4.2 Add sync-time monitoring

Log stats after each sync showing:
- Total shifts synced
- Invalid shifts detected
- Invalid shifts auto-corrected
- Invalid shifts skipped

---

## Implementation Order

| Phase | Task | Effort | Impact |
|-------|------|--------|--------|
| 1.1 | GREATEST() in Cost Analysis | 15 min | Immediate fix |
| 1.2 | Validation WHERE clauses | 30 min | Prevents display issues |
| 2.1 | Validate in _parse_shift | 30 min | Prevents future bad data |
| 2.3 | Validate in _sync_clock_time | 15 min | Second layer prevention |
| 3.1 | Audit script | 45 min | Find scope of problem |
| 3.2 | Fix script | 1 hr | Clean existing data |
| 2.2 | Timezone awareness | 2 hr | Root cause fix (risky) |
| 4.x | Monitoring | 1 hr | Long-term health |

**Recommended order:** 1.1 -> 2.1 -> 2.3 -> 3.1 -> 3.2 -> 1.2 -> 4.x -> 2.2

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/api/dashboard.py` | Add GREATEST(0, ...) wrappers, WHERE filters |
| `backend/integrations/connecteam_client.py` | Validate in _parse_shift() |
| `backend/integrations/connecteam_sync.py` | Validate in _sync_clock_time() |

## New Files

| File | Purpose |
|------|---------|
| `backend/scripts/audit_clock_times.py` | Find invalid records |
| `backend/scripts/fix_negative_hours.py` | Fix existing bad data |

---

## Testing Plan

1. **Before fix:** Query for negative hours, document count
2. **After Phase 1:** Cost Analysis shows 0 for previously negative
3. **After Phase 2:** New syncs don't create invalid records
4. **After Phase 3:** No records with clock_out < clock_in

```sql
-- Test query for validation
SELECT
    COUNT(*) as invalid_count,
    SUM(TIMESTAMPDIFF(MINUTE, clock_in, clock_out)) as total_negative_minutes
FROM clock_times
WHERE clock_out < clock_in;
```

---

## Rollback Plan

1. Phase 1: Revert SQL changes (simple)
2. Phase 2: Revert validation code (simple)
3. Phase 3: Keep backup before running fix script

---

## Code Review Findings (2025-12-11)

**Review Report:** `reports/code-reviewer-251211-timezone-safety-analysis.md`

### CRITICAL ISSUES BLOCKING IMPLEMENTATION:

1. **Timezone Parsing Bug** - `connecteam_client.py:271` uses `datetime.fromtimestamp()` which assumes LOCAL machine timezone, not UTC. If production server timezone != CT, all data is wrong NOW.

2. **Mixed Storage Assumption** - Code assumes BOTH UTC and CT storage in different places. Must audit actual storage format before proceeding.

3. **NOW() Timezone Ambiguity** - 8+ queries use `COALESCE(clock_out, NOW())` without timezone awareness. Breaks for currently-clocked-in employees.

### REVISED IMPLEMENTATION REQUIRED:

**Phase 0 (NEW - MUST COMPLETE FIRST):**
- [x] Code review completed (2025-12-11)
- [ ] Audit: Determine actual storage format (UTC vs CT)
- [ ] Fix: `connecteam_client.py` timestamp parsing to use explicit timezone
- [ ] Test: Verify new syncs store correct times
- [ ] Audit: Find all auto-corrected shifts > 16 hours
- [ ] Document: Business rules for overnight shifts and DST

**DO NOT PROCEED** with Phases 1-4 until Phase 0 complete.

See detailed findings, safe migration order, and rollback plan in code review report.

---

## Unresolved Questions (UPDATED)

1. **[CRITICAL] Production server timezone?** - Must check `@@system_time_zone` on production DB
2. **[CRITICAL] Current data format?** - Is clock_times storing UTC or CT currently?
3. **Timezone storage:** Currently storing naive datetimes. Should we migrate to UTC storage with explicit conversion at display?
4. **Connecteam API timezone:** Confirm if timestamps are always UTC or local to business. (LIKELY UTC based on code review)
5. **Historical data scope:** How far back should we fix? All-time or just recent?
6. **Manual review process:** What to do with unfixable records?
7. **Overnight shift business rule:** Count toward clock-in day, clock-out day, or split?
