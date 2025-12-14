# Intelligent Scheduling Performance Analysis

**Date:** 2025-12-13
**Scope:** `frontend/intelligent-schedule.html` + `backend/api/schedule.py`
**Focus:** Save/Draft operations, API performance, Frontend JS, Network requests

---

## Executive Summary

Primary bottleneck: **`publish_schedule()` endpoint uses N+1 INSERT pattern** (lines 85-100) vs `save_draft()` which correctly uses batch insert. Secondary issues include sequential API calls on page load and full DOM rebuilds on minor changes.

**Estimated Total Improvement:** 60-75% faster save operations, 40-50% faster page load.

---

## Priority 1: CRITICAL - Backend N+1 Query (HIGH IMPACT)

### Issue: publish_schedule() uses individual INSERTs

**Location:** `backend/api/schedule.py:85-100`

```python
# CURRENT (SLOW) - One INSERT per shift
for station_id, dates in schedule_data.items():
    for date_str, shifts in dates.items():
        for shift in shifts:
            db.execute_query("""
                INSERT INTO published_shifts
                (schedule_id, employee_id, shift_date, station, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (...))
```

**Problem:** With 50 shifts = 50 separate DB roundtrips. Each roundtrip ~5-15ms = 250-750ms total.

**Fix:** Use `execute_many()` like `save_draft()` already does (lines 182-202).

```python
# RECOMMENDED - Batch INSERT (already used in save_draft)
shift_values = []
for station_id, dates in schedule_data.items():
    for date_str, shifts in dates.items():
        for shift in shifts:
            shift_values.append((
                schedule_id, shift.get('employee_id'), date_str,
                station_id, shift.get('start_time', '06:00'),
                shift.get('end_time', '14:30')
            ))

if shift_values:
    db.execute_many("""
        INSERT INTO published_shifts
        (schedule_id, employee_id, shift_date, station, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, shift_values)
```

**Impact:** HIGH - 50 queries -> 1 query = ~95% reduction in DB time
**Effort:** LOW - Copy pattern from save_draft() (10 lines change)

---

## Priority 2: HIGH - Sequential API Calls on Init (MEDIUM-HIGH IMPACT)

### Issue: Frontend loads data sequentially

**Location:** `frontend/intelligent-schedule.html:3184-3199`

```javascript
// CURRENT - Sequential (blocking)
await loadEmployees();         // ~100-200ms
await loadApprovedTimeOff();   // ~100-200ms (calls 2 endpoints internally)
await loadPublishedSchedule(); // ~150-300ms
// Total: 350-700ms serial wait
```

**Fix:** Parallelize independent calls:

```javascript
// RECOMMENDED - Parallel
await Promise.all([
    loadEmployees(),
    loadApprovedTimeOff()
]);
await loadPublishedSchedule(); // Must wait for time-off data for filtering
```

**Additional Optimization in `loadApprovedTimeOff()` (lines 1904-1935):**

```javascript
// CURRENT - Sequential
const approvedRes = await fetch(`${API_BASE}/manager/time-off/approved`);
// ... process
const pendingRes = await fetch(`${API_BASE}/manager/time-off/pending`);

// RECOMMENDED - Parallel
const [approvedRes, pendingRes] = await Promise.all([
    fetch(`${API_BASE}/manager/time-off/approved`),
    fetch(`${API_BASE}/manager/time-off/pending`)
]);
```

**Impact:** MEDIUM-HIGH - ~40-50% faster page load
**Effort:** LOW - Simple Promise.all() wrap

---

## Priority 3: MEDIUM - Full DOM Rebuild on Minor Changes

### Issue: `buildScheduleGrid()` rebuilds entire grid

**Location:** `frontend/intelligent-schedule.html:1613-1697`

Called on every:
- `addShift()` (not direct, but after drop)
- `removeShift()` (line 1968)
- `saveShiftEdit()` (line 2021)
- `loadPublishedSchedule()` (line 3146)

**Current Pattern:**
```javascript
function buildScheduleGrid() {
    let html = '';
    // ... builds ~500+ lines of HTML
    grid.innerHTML = html;  // Full DOM replacement
}
```

**Fix:** Implement targeted cell updates:

```javascript
function updateCell(stationId, dateStr) {
    const cell = document.querySelector(
        `.day-cell[data-station="${stationId}"][data-date="${dateStr}"]`
    );
    if (!cell) return;

    const shifts = getShiftsForCell(stationId, dateStr);
    cell.innerHTML = renderShiftCards(shifts, stationId, dateStr);
}

function removeShift(stationId, dateStr, employeeId) {
    if (schedule[stationId]?.[dateStr]) {
        schedule[stationId][dateStr] = schedule[stationId][dateStr].filter(
            s => s.employee_id !== employeeId
        );
        updateCell(stationId, dateStr);  // Instead of buildScheduleGrid()
        showToast('Shift removed');
        scheduleStatus = 'unsaved';
        updateStatusIndicator();
    }
}
```

**Impact:** MEDIUM - Noticeable UI responsiveness improvement
**Effort:** MEDIUM - Requires refactoring grid rendering

---

## Priority 4: MEDIUM - Missing Composite Index

### Issue: Query on `published_shifts` uses multiple columns

**Location:** `backend/api/schedule.py:230-244`

```sql
SELECT ps.*, e.name
FROM published_shifts ps
JOIN published_schedules pub ON ps.schedule_id = pub.id
JOIN employees e ON ps.employee_id = e.id
WHERE pub.week_start_date = %s
ORDER BY ps.shift_date, ps.station, e.name
```

**Current Indexes (from create script):**
- `idx_schedule (schedule_id)`
- `idx_employee (employee_id)`
- `idx_date (shift_date)`

**Recommended Additional Index:**

```sql
CREATE INDEX idx_schedule_date_station
ON published_shifts (schedule_id, shift_date, station);
```

**Impact:** MEDIUM - Faster ORDER BY, better query planning
**Effort:** LOW - Single migration script

---

## Priority 5: LOW - Redundant Shift Count Iterations

### Issue: Multiple full traversals of schedule object

**Location:** `frontend/intelligent-schedule.html`

`saveDraft()` (lines 2701-2706) and `publishSchedule()` (lines 2739-2744) both iterate all shifts just to count:

```javascript
let totalShifts = 0;
Object.values(schedule).forEach(dates => {
    Object.values(dates).forEach(shifts => {
        totalShifts += shifts.length;
    });
});
```

**Fix:** Cache shift count or compute lazily:

```javascript
function getShiftCount() {
    return Object.values(schedule).reduce((total, dates) =>
        total + Object.values(dates).reduce((t, shifts) => t + shifts.length, 0), 0
    );
}
// Or maintain a counter updated on add/remove
```

**Impact:** LOW - Micro-optimization
**Effort:** LOW

---

## Priority 6: LOW - Transaction Handling in publish_schedule

### Issue: Multiple queries without explicit transaction

**Location:** `backend/api/schedule.py:15-111`

Multiple UPDATE/DELETE/INSERT operations without transaction boundary. If error occurs mid-operation, partial state saved.

**Current Flow:**
1. Check existing (SELECT)
2. Delete old shifts (DELETE)
3. Update status (UPDATE)
4. Validate employees (SELECT)
5. Insert shifts (N inserts)

Each uses auto-commit (from db_manager context manager).

**Fix:** Wrap in explicit transaction or use single cursor context.

**Impact:** LOW for performance, MEDIUM for data integrity
**Effort:** MEDIUM

---

## Priority 7: LOW - Unnecessary Re-renders

### Issue: `renderEmployeeList()` called after time-off load

**Location:** `frontend/intelligent-schedule.html:1931`

After loading time-off data, the entire employee list is re-rendered even though `loadEmployees()` already rendered it.

**Fix:** Only update badges on existing elements instead of full re-render.

**Impact:** LOW
**Effort:** LOW

---

## Summary Table

| Priority | Issue | Location | Impact | Effort | Time Est. |
|----------|-------|----------|--------|--------|-----------|
| P1 | N+1 INSERT in publish_schedule | schedule.py:85-100 | HIGH | LOW | 30 min |
| P2 | Sequential API calls on init | intelligent-schedule.html:3184 | MEDIUM-HIGH | LOW | 20 min |
| P2b | Sequential time-off fetch | intelligent-schedule.html:1907-1927 | MEDIUM | LOW | 10 min |
| P3 | Full DOM rebuild | intelligent-schedule.html:1613+ | MEDIUM | MEDIUM | 2 hrs |
| P4 | Missing composite index | Database | MEDIUM | LOW | 15 min |
| P5 | Redundant count iterations | intelligent-schedule.html | LOW | LOW | 10 min |
| P6 | Transaction handling | schedule.py:15-111 | LOW/MEDIUM | MEDIUM | 1 hr |
| P7 | Unnecessary re-render | intelligent-schedule.html:1931 | LOW | LOW | 10 min |

---

## Recommended Implementation Order

1. **Immediate (P1):** Fix N+1 INSERT in `publish_schedule()` - copy pattern from `save_draft()`
2. **Same day (P2):** Parallelize frontend API calls with Promise.all()
3. **Next sprint (P3):** Implement targeted DOM updates
4. **When convenient (P4-P7):** Minor optimizations

---

## Unresolved Questions

1. **Actual shift count per save:** Need production metrics to quantify N+1 impact
2. **Connection pool saturation:** With 50 rapid queries, is pool (size=10) causing waits?
3. **Browser:** Is target Chrome/Edge? May affect DOM optimization strategy
