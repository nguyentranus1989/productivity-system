# Timezone Fix Plan: "Keep CT, Fix Queries" Approach

**Date:** 2025-12-12
**Author:** Planner Agent
**Priority:** CRITICAL
**Approach:** Keep existing CT data in clock_times, fix all NOW() comparisons

---

## Executive Summary

The `clock_times` table stores timestamps in Central Time (CT) because:
- Connecteam API returns Unix timestamps
- `datetime.fromtimestamp()` converts to LOCAL time (CT on Windows/production server)
- Times are stored "as-is" without explicit UTC conversion

MySQL `NOW()` returns UTC (server timezone). When queries use `COALESCE(clock_out, NOW())` for currently clocked-in employees, it mixes CT data with UTC, causing a **6-hour calculation error**.

**This plan fixes queries without migrating data.**

---

## Current State Analysis

### 1.1 Data Storage Confirmation

| Table | Column | Timezone | Evidence |
|-------|--------|----------|----------|
| `clock_times` | `clock_in`, `clock_out` | CT | `datetime.fromtimestamp()` uses local TZ |
| `activity_logs` | `window_start`, `window_end` | UTC | PodFactory sync uses UTC |
| `daily_scores` | `score_date` | CT date | Local date calculation |

### 1.2 Problematic NOW() Usage in Active Codebase

**Critical Queries (directly affect calculations for clocked-in employees):**

| File | Line | Query Pattern | Impact |
|------|------|---------------|--------|
| `calculations/productivity_calculator.py` | 72-73 | `MAX(COALESCE(clock_out, NOW()))`, `TIMESTAMPDIFF(...NOW())` | Wrong active time |
| `api/dashboard.py` | 610 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))` | Wrong display hours |
| `api/dashboard.py` | 680, 686 | `COALESCE(MAX(clock_out), NOW())` | Wrong leaderboard data |
| `api/dashboard.py` | 1473 | `TIMESTAMPDIFF(...COALESCE(MAX(clock_out), NOW()))` | Wrong summary |
| `api/dashboard.py` | 3485 | `TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW()))` | Wrong cost analysis |
| `api/dashboard.py` | 3617 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))` | Wrong timeline |
| `integrations/connecteam_sync.py` | 352 | `SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW())` | Wrong during-shift updates |
| `utils/timezone_helpers.py` | 213, 269, 274 | `COALESCE(ct.clock_out, NOW())` | Template queries affected |

**Secondary Queries (historical/audit purposes - less critical):**

| File | Line | Pattern |
|------|------|---------|
| `calculations/team_metrics_engine.py` | 269, 347 | `DATE_SUB(NOW(), INTERVAL X DAY)` - OK for range filtering |
| `api/system_control.py` | 88, 92, 118, 122 | `TIMESTAMPDIFF(...NOW())` for audit |
| `api/flags.py` | 106, 118, 136 | `DATE_SUB(NOW(), INTERVAL X DAY)` - OK |
| `calculations/enhanced_idle_detector.py` | 264, 282, 322, 340 | `DATE_SUB(NOW(), INTERVAL X DAY)` - OK |

---

## Fix Strategy

### Option A: Convert NOW() to CT in SQL (Recommended)

Replace `NOW()` with `CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')` in all queries comparing with clock_times data.

**Pros:**
- No data migration needed
- Minimal code changes
- Backwards compatible

**Cons:**
- Slightly more verbose SQL
- Must remember pattern for new code
- CONVERT_TZ has minor performance overhead (negligible)

### Option B: Use Application-Level CT Time

Pass Python-calculated CT time as parameter instead of using SQL NOW().

**Pros:**
- Clear separation: Python handles TZ, SQL handles data
- Easier testing

**Cons:**
- More Python changes required
- Requires passing extra parameter

### Recommended: Hybrid Approach

- Use **Option A** for inline `COALESCE(clock_out, NOW())` patterns
- Use **Option B** via `TimezoneHelper.get_current_ct_datetime()` for date filtering

---

## Detailed Fix Specifications

### 3.1 productivity_calculator.py

**Location:** Lines 68-80

**Current:**
```sql
SELECT
    MIN(clock_in) as first_clock_in,
    MAX(COALESCE(clock_out, NOW())) as last_clock_out,
    TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, NOW()))) as total_minutes
FROM clock_times
```

**Fixed:**
```sql
SELECT
    MIN(clock_in) as first_clock_in,
    MAX(COALESCE(clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))) as last_clock_out,
    TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')))) as total_minutes
FROM clock_times
```

**Also fix:** Lines 255-260 (similar pattern)

---

### 3.2 api/dashboard.py

**Location 1:** Line 610 (get_today_clock_times)

**Current:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))) as total_minutes
```

**Fixed:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')))) as total_minutes
```

---

**Location 2:** Lines 677-690 (leaderboard)

**Current:**
```sql
ROUND(
    TIMESTAMPDIFF(MINUTE,
        MIN(clock_in),
        COALESCE(MAX(clock_out), NOW())
    ) / 60.0,
    1
) as hours_worked,
TIMESTAMPDIFF(MINUTE,
    MIN(clock_in),
    COALESCE(MAX(clock_out), NOW())
) as clock_minutes
```

**Fixed:**
```sql
ROUND(
    TIMESTAMPDIFF(MINUTE,
        MIN(clock_in),
        COALESCE(MAX(clock_out), CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
    ) / 60.0,
    1
) as hours_worked,
TIMESTAMPDIFF(MINUTE,
    MIN(clock_in),
    COALESCE(MAX(clock_out), CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
) as clock_minutes
```

---

**Location 3:** Line 1473 (summary stats)

**Current:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), NOW()))) as clock_minutes
```

**Fixed:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')))) as clock_minutes
```

---

**Location 4:** Line 3485 (cost analysis)

**Current:**
```sql
SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())))) / 60.0 as clocked_hours
```

**Fixed:**
```sql
SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))))) / 60.0 as clocked_hours
```

---

**Location 5:** Line 3617 (employee timeline)

**Current:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))) as minutes
```

**Fixed:**
```sql
GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')))) as minutes
```

---

### 3.3 integrations/connecteam_sync.py

**Location:** Line 352

**Current:**
```sql
SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW()),
```

**Fixed:**
```sql
SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')),
```

---

### 3.4 utils/timezone_helpers.py

**Location:** Lines 213, 269, 274

Update the template queries in the helper class to use the correct pattern:

**Current (Line 213):**
```sql
AND al.window_start <= COALESCE(ct.clock_out, NOW())
```

**Fixed:**
```sql
AND al.window_start <= COALESCE(ct.clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
```

**Current (Lines 269, 274):**
```sql
MAX(COALESCE(ct.clock_out, NOW())) as last_clock_out,
```

**Fixed:**
```sql
MAX(COALESCE(ct.clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))) as last_clock_out,
```

---

## Files Summary

| File | Changes Required | Priority |
|------|------------------|----------|
| `calculations/productivity_calculator.py` | 2 locations | P1 - Critical |
| `api/dashboard.py` | 5 locations | P1 - Critical |
| `integrations/connecteam_sync.py` | 1 location | P1 - Critical |
| `utils/timezone_helpers.py` | 3 locations | P2 - Template fix |

**Total: 11 code changes across 4 files**

---

## Testing Strategy

### 5.1 Pre-Change Verification

Run audit script to capture current state:
```bash
cd backend && python scripts/audit_timezone_state.py
```

Record:
- Current clocked-in employees
- Their calculated minutes with NOW() (broken)
- Expected minutes based on CT clock_in to CT now

### 5.2 Post-Change Verification

1. **Clocked-In Employee Test:**
   - Employee clocks in at 7:00 AM CT
   - At 1:00 PM CT, check dashboard shows ~6 hours (not 12)

2. **Boundary Test:**
   - Test at 11:00 PM CT (next day in UTC)
   - Ensure calculations remain correct

3. **Historical Data Test:**
   - Check completed shifts (with clock_out)
   - Should be unaffected (no NOW() involved)

### 5.3 Regression Test

- Verify all dashboard tabs load
- Check leaderboard shows reasonable hours
- Check cost analysis calculations
- Verify productivity scores update correctly

---

## Pros and Cons

### Pros of "Keep CT, Fix Queries" Approach

1. **No Data Migration** - Zero risk of data corruption
2. **Immediate Fix** - Can deploy same day
3. **Minimal Code Changes** - Only 11 specific locations
4. **Backwards Compatible** - Historical queries unaffected
5. **Reversible** - Easy to rollback if issues found
6. **Clear Pattern** - `CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')` is self-documenting

### Cons of "Keep CT, Fix Queries" Approach

1. **Inconsistent Storage** - clock_times (CT) vs activity_logs (UTC)
2. **Pattern Maintenance** - Must remember CT pattern for future code
3. **DST Handled by MySQL** - Relies on MySQL's timezone database being current
4. **Verbose SQL** - Longer query strings
5. **Future Complexity** - Cross-table joins between CT and UTC data require care

---

## Alternative: Full UTC Migration (Future)

If business requirements change, consider migrating to full UTC storage:

1. **Modify Connecteam client** - Use `datetime.utcfromtimestamp()`
2. **Migrate existing data** - `CONVERT_TZ(clock_in, 'America/Chicago', '+00:00')`
3. **Update all queries** - Remove CT-specific conversions
4. **Update display layer** - Convert to CT only for UI

**Estimated effort:** 3-5 days vs 1 day for current approach

---

## Implementation Checklist

- [ ] Run pre-change audit and record baseline
- [ ] Create backup of affected files
- [ ] Apply fixes to productivity_calculator.py (2 changes)
- [ ] Apply fixes to dashboard.py (5 changes)
- [ ] Apply fixes to connecteam_sync.py (1 change)
- [ ] Apply fixes to timezone_helpers.py (3 changes)
- [ ] Run post-change audit
- [ ] Test with currently clocked-in employee
- [ ] Test dashboard tabs
- [ ] Test leaderboard
- [ ] Test cost analysis
- [ ] Deploy to production
- [ ] Monitor for 24 hours

---

## Unresolved Questions

1. **MySQL Timezone Tables:** Is `mysql.time_zone_name` table populated on production? Required for `CONVERT_TZ()` with named timezones.
   - Test: `SELECT CONVERT_TZ(NOW(), '+00:00', 'America/Chicago');`
   - If NULL, need to load timezone tables or use offset `'-06:00'` / `'-05:00'`

2. **DST Handling:** Does MySQL automatically handle DST for `America/Chicago`?
   - Yes, if timezone tables are loaded
   - No, if using hardcoded offset

3. **Performance Impact:** Negligible, but monitor query times post-deployment.

4. **connecteam_reconciliation.py:** Line 186 uses `TIMESTAMPDIFF(HOUR, ct.clock_in, NOW())` for stale shift detection. Should this also be fixed?
   - Likely yes, for consistency

---

## Appendix: Search Commands Used

```bash
# Find NOW() usage with clock_times
grep -rn "NOW()" backend/*.py backend/api/*.py backend/calculations/*.py | grep -v archive | grep -v backup

# Find COALESCE patterns
grep -rn "COALESCE.*clock_out.*NOW" backend/*.py

# Find TIMESTAMPDIFF patterns
grep -rn "TIMESTAMPDIFF.*clock_in.*NOW" backend/*.py
```

---

**Document End**
