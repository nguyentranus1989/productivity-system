# Connecteam Sync Fix Plan

**Date:** 2025-12-12
**Status:** Ready for Implementation
**Priority:** Critical (data corruption + performance)

---

## Executive Summary

The `_sync_clock_time` method in `connecteam_sync.py` has three critical issues causing slow sync performance (O(n) queries per shift) and data corruption (false positive 6-hour timezone detection overwrites legitimate afternoon shifts). This plan proposes a batch-first approach that eliminates per-shift queries and uses unique constraint matching instead of fragile time-gap heuristics.

---

## 1. Root Cause Analysis

### Issue 1: O(n) Database Queries (Performance)

**Current behavior (lines 308-318):**
```python
existing_today = self.db.fetch_all(
    """
    SELECT id, clock_in, clock_out, ...
    FROM clock_times
    WHERE employee_id = %s
    AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
    ORDER BY ...
    """,
    (shift.clock_in, employee_id, clock_in_date, shift.clock_in)
)
```

**Problem:**
- For EVERY shift, executes a query to find all existing records for that employee on that day
- 500 shifts = 500 DB queries just for duplicate checking
- Each query uses `CONVERT_TZ` function - not indexable, requires full scan

**Root cause:** Per-shift processing pattern instead of batch pattern.

---

### Issue 2: False Positive 6hr Detection (Data Corruption)

**Current behavior (lines 326-327):**
```python
is_same_shift = seconds_diff < 300  # Within 5 minutes
is_tz_shifted = abs(seconds_diff - 21600) < 300  # 6 hours +/- 5 min
```

**Problem scenario:**
1. Employee works 8:00 AM - 12:00 PM (shift 1, saved correctly)
2. Employee works 2:00 PM - 6:00 PM (shift 2, new clock-in)
3. Gap between shift 1 clock_in (8:00 AM) and shift 2 clock_in (2:00 PM) = 6 hours
4. Code detects "6-hour offset" and OVERWRITES shift 1 with shift 2's data
5. **Result:** Morning shift completely lost, replaced by afternoon data

**Root cause:** Using time difference heuristic instead of unique identifiers. 6 hours happens to be:
- CDT-to-UTC offset (timezone bug), AND
- Normal lunch break gap (legitimate multi-shift day)

The code cannot distinguish between these cases.

---

### Issue 3: Complex Logic (Maintainability)

**Current code path complexity:**
```
_sync_clock_time()
├── Query existing records for employee+date
├── Loop through all existing records
│   ├── Calculate seconds_diff
│   ├── Check is_same_shift (< 5 min)
│   ├── Check is_tz_shifted (6 hrs +/- 5 min)
│   │   ├── If is_tz_shifted: UPDATE record
│   │   └── Else if is_same_shift: UPDATE or skip
│   └── If no match found:
│       ├── Check if latest_record has clock_out
│       ├── Check time_since_last_out > 300
│       │   ├── If true: Continue to create
│       │   └── If false: Skip as duplicate
│       └── If latest active: UPDATE or skip
└── If truly new: INSERT
```

**Problems:**
- 8+ conditional branches
- Stateful logic across loop iterations
- Side effects inside loop
- No clear separation between "match" and "upsert" phases

---

## 2. Approach Options

### Option A: Batch Fetch + Unique Key Match (RECOMMENDED)

**Concept:**
1. Fetch ALL existing clock_times for the date range in ONE query
2. Build in-memory lookup: `{(employee_id, clock_in_utc): record}`
3. For each incoming shift, match by exact clock_in timestamp
4. Use `INSERT ... ON DUPLICATE KEY UPDATE` with proper unique constraint

**Pros:**
- Reduces 500 queries to 1 query (99.8% reduction)
- No time-gap heuristics - exact timestamp matching
- Cannot overwrite wrong shift (different clock_in = different record)
- Simple logic: match exists? update : insert

**Cons:**
- Requires adding unique constraint on `(employee_id, clock_in)`
- One-time migration to add constraint + dedupe existing data

**Performance:** O(1) queries + O(n) in-memory operations

---

### Option B: Stored Procedure with MERGE Logic

**Concept:**
- Create MySQL stored procedure that handles upsert logic server-side
- Pass all shifts as JSON array in single call
- Procedure loops and performs INSERT/UPDATE

**Pros:**
- Single network round-trip
- All logic encapsulated in DB

**Cons:**
- MySQL stored procedures are hard to test/debug
- Logic duplicated (Python and SQL)
- Team unfamiliar with MySQL procedures

**Performance:** O(1) network calls, but procedure still does row-by-row internally

---

### Option C: Preserve Current Logic, Optimize Queries

**Concept:**
- Add composite index on `(employee_id, clock_in)`
- Batch-fetch existing records upfront (like Option A)
- Keep the 6-hour detection but make it smarter

**Pros:**
- Minimal code changes
- Preserves existing timezone-correction behavior

**Cons:**
- 6-hour detection is fundamentally flawed (cannot distinguish TZ bug from lunch break)
- Still complex conditional logic
- Technical debt remains

**Performance:** Improved, but still fragile

---

## 3. Recommended Solution: Option A

### Why Option A?

1. **Eliminates the root cause** - exact clock_in matching cannot confuse shifts
2. **Simple mental model** - "one clock_in = one record"
3. **Database enforced** - unique constraint prevents duplicates at storage layer
4. **Testable** - easy to write unit tests for exact matching
5. **Standard ETL pattern** - batch fetch + upsert is industry standard

---

## 4. Implementation Plan

### Phase 1: Database Preparation (15 min)

#### Step 1.1: Backup Current Data
```sql
CREATE TABLE clock_times_backup_20251212 AS
SELECT * FROM clock_times WHERE DATE(clock_in) >= '2024-12-01';
```

#### Step 1.2: Identify and Remove True Duplicates
```sql
-- Find records with identical (employee_id, clock_in)
SELECT employee_id, clock_in, COUNT(*) as cnt
FROM clock_times
GROUP BY employee_id, clock_in
HAVING cnt > 1;

-- Keep the record with most complete data (has clock_out)
DELETE ct1 FROM clock_times ct1
INNER JOIN clock_times ct2
  ON ct1.employee_id = ct2.employee_id
  AND ct1.clock_in = ct2.clock_in
  AND ct1.id > ct2.id
WHERE ct1.clock_out IS NULL OR ct2.clock_out IS NOT NULL;
```

#### Step 1.3: Add Unique Constraint
```sql
ALTER TABLE clock_times
ADD CONSTRAINT uq_employee_clock_in
UNIQUE (employee_id, clock_in);
```

---

### Phase 2: New Sync Implementation (45 min)

#### Step 2.1: Add Batch Fetch Method

```python
def _fetch_existing_clock_times(self, date: datetime.date) -> Dict[Tuple[int, datetime], Dict]:
    """Fetch all clock_times for a date as lookup dict.

    Returns:
        Dict[(employee_id, clock_in_utc)] -> record dict
    """
    query = """
        SELECT id, employee_id, clock_in, clock_out, total_minutes, is_active
        FROM clock_times
        WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
    """
    records = self.db.fetch_all(query, (date,))

    lookup = {}
    for r in records:
        key = (r['employee_id'], r['clock_in'])
        lookup[key] = r
    return lookup
```

#### Step 2.2: Rewrite _sync_clock_time (Simplified)

```python
def _sync_clock_time_v2(self, employee_id: int, shift: ConnecteamShift,
                        existing_lookup: Dict) -> str:
    """Sync single clock time using exact match.

    Returns: 'created', 'updated', or 'unchanged'
    """
    key = (employee_id, shift.clock_in)
    existing = existing_lookup.get(key)

    if existing:
        # Record exists - update if clock_out changed
        needs_update = (
            (shift.clock_out and not existing['clock_out']) or
            (shift.is_active and not existing['is_active'])
        )

        if needs_update:
            self.db.execute_query("""
                UPDATE clock_times
                SET clock_out = %s,
                    total_minutes = %s,
                    is_active = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (shift.clock_out, shift.total_minutes, shift.is_active, existing['id']))
            return 'updated'
        return 'unchanged'

    # New record - insert
    self.db.execute_query("""
        INSERT INTO clock_times
            (employee_id, clock_in, clock_out, total_minutes, is_active, source, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'connecteam', NOW(), NOW())
    """, (employee_id, shift.clock_in, shift.clock_out, shift.total_minutes, shift.is_active))
    return 'created'
```

#### Step 2.3: Update sync_todays_shifts to Use Batch Pattern

```python
def sync_todays_shifts(self) -> Dict[str, int]:
    """Sync today's shifts - batch optimized."""
    today = self.get_central_date()

    stats = {
        'total_shifts': 0,
        'created': 0,
        'updated': 0,
        'unchanged': 0,
        'errors': 0
    }

    # 1. Fetch all existing in ONE query
    existing_lookup = self._fetch_existing_clock_times(today)
    logger.info(f"Loaded {len(existing_lookup)} existing clock records for {today}")

    # 2. Get shifts from Connecteam
    shifts = self.client.get_todays_shifts()
    stats['total_shifts'] = len(shifts)

    # 3. Process each shift (no DB queries in loop)
    for shift in shifts:
        try:
            employee = self._get_employee_by_connecteam_id(shift.user_id)
            if not employee:
                continue

            result = self._sync_clock_time_v2(employee['id'], shift, existing_lookup)
            stats[result] += 1

        except Exception as e:
            logger.error(f"Error syncing shift: {e}")
            stats['errors'] += 1

    return stats
```

---

### Phase 3: Handle Edge Cases (30 min)

#### Edge Case 1: Connecteam Timezone Shift (Historical Data)

If Connecteam API returns timestamps with 6-hour offset (rare, but happened historically):

**Solution:** Normalize in `connecteam_client.py` at parse time, not during sync.
```python
# In _parse_shift(), already using UTC explicitly:
clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc).replace(tzinfo=None)
```

The client already stores UTC. No additional handling needed.

#### Edge Case 2: Clock-in Time Correction in Connecteam

If manager corrects clock-in time in Connecteam after sync:
- Old record has clock_in = 08:00:00
- Corrected record has clock_in = 08:15:00

**Solution:** This creates a new record (different clock_in).
- Add cleanup job to detect orphaned records (records where employee has no matching shift in Connecteam response for that day).

#### Edge Case 3: Multiple Shifts Same Day (Legitimate)

Employee works:
- 6:00 AM - 12:00 PM (shift 1)
- 2:00 PM - 6:00 PM (shift 2)

**Solution:** Works automatically - different clock_in timestamps = different records.

---

### Phase 4: Testing (30 min)

#### Test 1: Fresh Sync (No Existing Data)
```python
def test_fresh_sync():
    # Clear Dec 1 data
    # Run sync for Dec 1
    # Verify record count matches Connecteam shifts
    pass
```

#### Test 2: Incremental Update (Existing Data)
```python
def test_incremental_sync():
    # Create test record for employee X at 08:00
    # Run sync with shift showing clock_out at 12:00
    # Verify record updated (not duplicated)
    pass
```

#### Test 3: Multi-Shift Day
```python
def test_multi_shift():
    # Create morning shift record
    # Run sync with both morning and afternoon shifts
    # Verify 2 records exist, both correct
    pass
```

#### Test 4: Duplicate Prevention
```python
def test_duplicate_prevention():
    # Run sync twice in succession
    # Verify no duplicate records created
    pass
```

---

### Phase 5: Migration Script for Dec 1-11 (20 min)

```python
def resync_dec_1_to_11():
    """Clean resync of Dec 1-11 data."""
    sync = ConnecteamSync(API_KEY, CLOCK_ID)

    for day in range(1, 12):
        date = datetime(2025, 12, day).date()

        # Clear existing (corrupted) data
        sync.db.execute_query(
            "DELETE FROM clock_times WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s",
            (date,)
        )

        # Sync fresh
        stats = sync.sync_shifts_for_date(date)
        print(f"Dec {day}: {stats}")
```

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Unique constraint fails (existing duplicates) | Medium | Low | Pre-cleanup script identifies/removes duplicates |
| Connecteam API returns different timestamp format | Low | High | Client already normalizes to UTC; add validation |
| New code introduces regression | Medium | Medium | Keep old method as `_sync_clock_time_legacy`, feature flag |
| Performance worse with large existing_lookup | Low | Low | Dict lookup is O(1); even 10K records fits in memory |

---

## 6. Rollback Plan

1. Old method preserved as `_sync_clock_time_legacy()`
2. Feature flag `USE_BATCH_SYNC` (default: True)
3. If issues detected:
   ```python
   # In sync_todays_shifts:
   if not Config.USE_BATCH_SYNC:
       return self._sync_todays_shifts_legacy()
   ```
4. Database backup allows point-in-time recovery

---

## 7. Success Criteria

- [ ] Dec 1-11 synced with correct record counts matching Connecteam
- [ ] No duplicate clock_times records (verified by unique constraint)
- [ ] Multi-shift days preserved (2 records per day where applicable)
- [ ] Sync time < 5 seconds for 500 shifts (vs current ~30+ seconds)
- [ ] Zero false positive "6-hour offset" corrections

---

## 8. Files to Modify

| File | Changes |
|------|---------|
| `backend/integrations/connecteam_sync.py` | Add batch methods, rewrite `_sync_clock_time` |
| `backend/database/migrations/add_unique_constraint.sql` | New file - DDL for constraint |
| `backend/scripts/resync_dec_data.py` | New file - migration script |

---

## 9. Time Estimate

| Phase | Duration |
|-------|----------|
| Phase 1: DB Prep | 15 min |
| Phase 2: Implementation | 45 min |
| Phase 3: Edge Cases | 30 min |
| Phase 4: Testing | 30 min |
| Phase 5: Migration | 20 min |
| **Total** | **~2.5 hours** |

---

## Appendix A: Current _sync_clock_time Analysis

```
Lines 297-473 of connecteam_sync.py

PROBLEMS IDENTIFIED:
1. Line 308-318: Per-shift query (N queries problem)
2. Line 327: is_tz_shifted = abs(seconds_diff - 21600) < 300 (false positive bug)
3. Lines 320-430: 130+ lines of nested conditionals
4. Line 434-455: INSERT IGNORE - relies on missing unique constraint

LOGIC FLOW:
- fetch existing_today for employee+date
- loop existing_today:
    - if within 5min OR 6hr offset:
        - if 6hr offset: "correct" timezone (OVERWRITES!)
        - else: update clock_out if needed
    - if not matched after loop:
        - check if last shift closed
        - if gap > 5min: create new
        - else: skip as duplicate
- if no existing: INSERT
```

---

## Appendix B: Correct Data Model

```
clock_times table:
- employee_id: FK to employees
- clock_in: DATETIME (UTC, naive)
- clock_out: DATETIME (UTC, naive, nullable)
- total_minutes: INT
- is_active: BOOLEAN
- source: 'connecteam' | 'manual'

UNIQUE CONSTRAINT: (employee_id, clock_in)

Why clock_in as part of unique key:
- Each physical clock-in event has exactly one timestamp
- Same employee cannot clock in at exact same second twice
- Different clock_in = different shift (even same day)
```
