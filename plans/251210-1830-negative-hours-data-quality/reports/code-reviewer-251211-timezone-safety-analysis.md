# Code Review: Timezone Safety Analysis

**Reviewer:** Code Review Agent
**Date:** 2025-12-11
**Scope:** Timezone handling for UTC storage migration
**Priority:** CRITICAL - Data integrity risk
**Plan:** `plans/251210-1830-negative-hours-data-quality/plan.md`

---

## Executive Summary

Reviewed codebase for timezone safety ahead of UTC storage migration. Found **MAJOR CONFLICT**: Current system already has UTC storage in some places, Central Time in others. Migration plan assumes pure CT storage, but reality is mixed - **this makes migration extremely dangerous**.

**Critical Discovery:** `connecteam_sync.py` claims Connecteam sends CT times (line 307 comment), but `connecteam_client.py` uses `datetime.fromtimestamp()` which assumes LOCAL machine timezone. If server timezone != CT, data is corrupt NOW.

**Risk Level:** HIGH - Potential data loss, calculation errors, and breaking changes to currently-working code.

---

## Scope

**Files Analyzed:**
- `backend/integrations/connecteam_client.py` (422 lines)
- `backend/integrations/connecteam_sync.py` (450+ lines)
- `backend/api/dashboard.py` (3000+ lines, partial review)
- `backend/utils/timezone_helpers.py` (338 lines)
- `backend/config.py` (98 lines)

**Review Focus:**
- Timestamp parsing from Connecteam API
- Database storage assumptions (UTC vs CT)
- Query-time timezone conversions with `CONVERT_TZ()`
- Currently clocked-in employee calculations (`NOW()` usage)
- DST transition handling
- Frontend display assumptions

**Lines Analyzed:** ~4,200 lines of backend code
**Modified Files (recent):** 18 files changed in last commit (timezone fixes already applied)

---

## Critical Issues (MUST FIX BEFORE ANY MIGRATION)

### 1. **CRITICAL: Timezone Assumption Conflict**

**Location:** `backend/integrations/connecteam_sync.py:307-310`

**Issue:**
```python
# Line 307-310: INCORRECT COMMENT
# NOTE: Connecteam sends times in Central Time (CT), NOT UTC
# No timezone conversion needed for Connecteam data
clock_in_ct = shift.clock_in  # Already CT from Connecteam
clock_out_ct = shift.clock_out if shift.clock_out else None
```

**Reality Check:**
- Connecteam API returns **Unix timestamps** (seconds since epoch, timezone-agnostic)
- `connecteam_client.py:271` uses `datetime.fromtimestamp(clock_in_timestamp)`
- This uses **LOCAL MACHINE TIMEZONE**, not UTC, not CT
- If server is in UTC timezone, all times are 5-6 hours off from CT
- If server is in CT timezone, times happen to be correct BY ACCIDENT

**Evidence:**
```python
# backend/integrations/connecteam_client.py:271
clock_in = datetime.fromtimestamp(clock_in_timestamp)  # ← Uses local TZ!
```

**Impact:**
- If production server is UTC: ALL clock_in/clock_out times wrong by 5-6 hours
- Negative hours bug could be FROM THIS, not just overnight shifts
- Cannot migrate to UTC storage without first fixing this root cause

**Fix Required:**
```python
# BEFORE migration, fix connecteam_client.py:271
from datetime import timezone
clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc)
# Then explicitly convert to CT for display/storage as needed
```

**Risk:** DATA CORRUPTION - Every sync writes incorrect times if machine TZ != CT

---

### 2. **CRITICAL: Mixed Storage Assumption**

**Location:** Multiple files

**Issue:** Code assumes different storage formats in different places:

| File | Storage Assumption | Evidence |
|------|-------------------|----------|
| `connecteam_sync.py:314-321` | "clock_times stores CT times directly" | Comment: "Since clock_times stores CT times directly, no CONVERT_TZ needed" |
| `dashboard.py:202,489,549` | Uses `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')` | Assumes UTC storage, converts to CT |
| `dashboard.py:614,878` | Uses `DATE(ct.clock_in) = CURDATE()` | Assumes server timezone = CT |
| `timezone_helpers.py:85-338` | UTC storage with conversion | Whole utility designed for UTC→CT conversion |

**Conflict:**
- `dashboard.py` has BOTH patterns:
  - Lines 202,2858: `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')` (assumes UTC)
  - Lines 614,878: `DATE(ct.clock_in) = CURDATE()` (assumes CT)

**Impact:**
- Same query calculates dates differently depending on which clause
- Employees counted in wrong day if times near midnight
- Can cause off-by-one day errors in aggregations

**Data Quality Test Needed:**
```sql
-- Run this to find if data is UTC or CT:
SELECT
    MIN(clock_in) as earliest,
    MAX(clock_in) as latest,
    COUNT(*) as total,
    -- If these differ, data is inconsistent:
    COUNT(DISTINCT DATE(clock_in)) as days_native,
    COUNT(DISTINCT DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))) as days_as_utc
FROM clock_times
WHERE DATE(clock_in) BETWEEN '2025-12-01' AND '2025-12-11';
```

---

### 3. **CRITICAL: NOW() Timezone Ambiguity**

**Location:** 8+ queries using `COALESCE(clock_out, NOW())`

**Affected Lines in `dashboard.py`:**
- Line 611: `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))`
- Line 875: `TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), NOW()))`
- Line 1326: `SUM(TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW())))`
- Line 1472: `TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), NOW()))`
- Line 2851: `SUM(TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())))`

**Issue:**
- `NOW()` returns server timezone time (UTC or local)
- If `clock_in` stored in CT but `NOW()` returns UTC → negative hours!
- If migrating to UTC storage, `NOW()` correct, but existing CT data wrong

**Scenario That Breaks:**
```
# Current time: 2025-12-11 08:00:00 CT (14:00:00 UTC)
# Employee clocked in: 2025-12-11 07:00:00 CT (stored as naive datetime)
# Server timezone: UTC

TIMESTAMPDIFF(MINUTE, '2025-12-11 07:00:00', NOW())
  → TIMESTAMPDIFF(MINUTE, '2025-12-11 07:00:00', '2025-12-11 14:00:00')
  → 420 minutes (7 hours) ← WRONG! Should be 1 hour
```

**Fix Required:**
```sql
-- Option 1: If clock_in is CT, convert NOW() to CT
TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, CONVERT_TZ(NOW(), @@session.time_zone, 'America/Chicago')))

-- Option 2: If migrating to UTC, convert all times to UTC first
TIMESTAMPDIFF(MINUTE, CONVERT_TZ(clock_in, 'America/Chicago', '+00:00'), COALESCE(clock_out, UTC_TIMESTAMP()))
```

**Risk:** ACTIVE SHIFTS show wrong hours, breaking live dashboard

---

## High Priority Findings

### 4. **High: Auto-Correction Logic May Create Bad Data**

**Location:** `backend/integrations/connecteam_client.py:285-300`

**Issue:**
```python
# Lines 285-300: Auto-correction for negative hours
if clock_out < clock_in:
    # Auto-correct: if clock_out is same day but earlier, assume next day
    if clock_out.date() == clock_in.date():
        from datetime import timedelta
        clock_out = clock_out + timedelta(days=1)
        total_minutes = (clock_out - clock_in).total_seconds() / 60
        logger.info(f"Auto-corrected clock_out to next day: {clock_out}")
```

**Concerns:**
1. **Masks root cause**: If timestamps are wrong due to timezone parsing (Issue #1), this hides it
2. **No validation**: Doesn't check if corrected shift is reasonable (could create 20+ hour shifts)
3. **Silent data modification**: Logged but not flagged for review
4. **Timezone-dependent logic**: `clock_out.date() == clock_in.date()` depends on what timezone the datetime is in

**Recommendation:**
- Remove auto-correction UNTIL Issue #1 is fixed
- Add validation: corrected shift must be < 16 hours
- Log to data quality table for manual review
- Run audit to find how many shifts were auto-corrected

**Audit Query:**
```sql
SELECT * FROM clock_times
WHERE total_minutes > 960  -- > 16 hours
  AND source = 'connecteam'
ORDER BY total_minutes DESC;
```

---

### 5. **High: DST Transition Risks**

**Location:** All date filtering queries

**Issue:** DST transitions occur:
- Spring: 2 AM → 3 AM (lose 1 hour)
- Fall: 2 AM → 1 AM (gain 1 hour)

**Affected Queries:**
- `dashboard.py:202,2858`: `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')`
- All queries using `DATE(clock_in)` without timezone awareness

**Risk Scenarios:**

1. **Spring Forward (March):**
   - UTC range 2025-03-09 07:00 to 2025-03-10 07:00 (25 hours)
   - CT range 2025-03-09 00:00 to 2025-03-10 00:00 (23 hours)
   - Missing: 02:00-03:00 CT doesn't exist
   - Shifts crossing 2 AM may have wrong duration

2. **Fall Back (November):**
   - UTC range 2025-11-02 05:00 to 2025-11-03 06:00 (25 hours)
   - CT range 2025-11-02 00:00 to 2025-11-03 00:00 (25 hours)
   - Duplicate: 01:00-02:00 CT happens twice
   - Shifts crossing 2 AM may be counted twice

**Fix:** Use `timezone_helpers.py` (already exists!) for DST-aware conversions:
```python
# Good (handles DST)
utc_start, utc_end = tz_helper.ct_date_to_utc_range('2025-11-02')
# utc_start: 2025-11-02 05:00:00 UTC (CT midnight in CST)
# utc_end: 2025-11-03 05:59:59 UTC (CT 11:59:59 PM in CST)
```

**Testing Plan:** Test queries on DST transition dates:
- 2025-03-09 (Spring Forward)
- 2025-11-02 (Fall Back)
- Verify total hours worked = expected

---

### 6. **High: Overnight Shift Date Assignment**

**Location:** `connecteam_sync.py:314,321,378`

**Issue:**
```python
# Line 314-321: Date filtering assumes clock_in determines date
WHERE DATE(clock_in) = %s

# Line 378: Update query uses CURDATE()
WHERE DATE(clock_in) = CURDATE()
```

**Problem:** Overnight shift crosses midnight

**Scenario:**
```
Clock in:  2025-12-10 11:00 PM CT
Clock out: 2025-12-11 07:00 AM CT (next day)

Query: WHERE DATE(clock_in) = '2025-12-10'
  → Finds shift (clock_in is Dec 10)

Query: WHERE DATE(clock_in) = '2025-12-11'
  → Doesn't find shift (clock_in is Dec 10, not Dec 11!)
```

**Impact:**
- Dec 11 dashboard shows employee as "not working"
- Hours credited to Dec 10, not Dec 11
- Cost analysis for Dec 11 missing labor cost

**Business Logic Question:**
Should overnight shift count toward:
- Day clocked IN (current behavior)
- Day clocked OUT (alternative)
- BOTH days split by midnight (complex but accurate)

**Recommendation:** Document business rule clearly, then implement consistently

---

## Medium Priority Improvements

### 7. **Medium: Duplicate `cached_endpoint` Definition**

**Location:** `backend/api/dashboard.py:6-60`

**Issue:** `cached_endpoint` decorator defined twice (lines 6-28 and 35-60)

**Impact:** Second definition overwrites first, wasting lines

**Fix:** Remove duplicate (lines 6-28)

---

### 8. **Medium: CONVERT_TZ Inconsistent Parameters**

**Location:** Multiple queries in `dashboard.py`

**Issue:** Some use `'+00:00'`, some use `'UTC'` as source timezone:
```sql
-- Inconsistent:
CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')  -- Most queries
CONVERT_TZ(window_start, '+00:00', 'America/Chicago')  -- Activity logs
```

**Recommendation:** Standardize to `'+00:00'` (already most common pattern)

---

### 9. **Medium: Missing Timezone Validation in Sync**

**Location:** `connecteam_sync.py:_sync_clock_time()`

**Issue:** No validation that shift times are reasonable:
- No check for future timestamps
- No check for very old timestamps (> 7 days)
- No check for impossible durations (> 24 hours)

**Recommendation:** Add validation:
```python
# Validate timestamps before INSERT
now_ct = self.get_central_datetime()
if clock_in_ct > now_ct:
    logger.error(f"Future clock_in: {clock_in_ct} > {now_ct}")
    return True  # Skip

shift_hours = (clock_out_ct - clock_in_ct).total_seconds() / 3600
if shift_hours > 24:
    logger.error(f"Impossible shift duration: {shift_hours}h")
    return True  # Skip
```

---

## Low Priority Suggestions

### 10. **Low: Timezone Helpers Underutilized**

**Location:** `backend/utils/timezone_helpers.py`

**Observation:** Excellent utility class exists (338 lines) with DST-safe conversions, but only used in example code within the file itself. Not imported in:
- `dashboard.py`
- `connecteam_sync.py`
- `productivity_calculator.py`

**Recommendation:** Refactor to use `TimezoneHelper` consistently across codebase

---

### 11. **Low: No Timezone in Server Health Check**

**Location:** `dashboard.py:627-641` (`/server-time` endpoint)

**Suggestion:** Add server timezone to response:
```python
return jsonify({
    'utc': utc_now.isoformat(),
    'central': central_now.isoformat(),
    'server_tz': str(datetime.now().astimezone().tzinfo),  # Add this
    'expected_tz': 'America/Chicago',
    'tz_match': str(datetime.now().astimezone().tzinfo) == 'America/Chicago'
})
```

Helps verify production server is in correct timezone

---

## Edge Cases & DST Concerns

### DST Transition Testing

**Spring Forward (2025-03-09 2:00 AM → 3:00 AM):**
- Employee clocks in 1:30 AM CT
- Works through 2:00 AM (which doesn't exist)
- Clocks out 3:30 AM CT
- Expected duration: 1 hour (1:30→3:30 skipping 2:00-3:00)
- Actual duration with naive datetimes: 2 hours ← WRONG

**Fall Back (2025-11-02 2:00 AM → 1:00 AM):**
- Employee clocks in 1:30 AM CT (first occurrence)
- Clocks out 1:30 AM CT (second occurrence, 1 hour later)
- Expected duration: 1 hour
- Actual duration with naive datetimes: 0 hours ← WRONG

**Test Plan:**
```python
# Test script: backend/test_dst_transitions.py
from utils.timezone_helpers import TimezoneHelper

tz = TimezoneHelper()

# Spring forward test
spring_date = '2025-03-09'
utc_start, utc_end = tz.ct_date_to_utc_range(spring_date)
print(f"Spring: {utc_start} to {utc_end}")
# Should be 24-hour UTC range representing 23-hour CT day

# Fall back test
fall_date = '2025-11-02'
utc_start, utc_end = tz.ct_date_to_utc_range(fall_date)
print(f"Fall: {utc_start} to {utc_end}")
# Should be 24-hour UTC range representing 25-hour CT day
```

---

## Positive Observations

1. **Timezone Helpers Exist**: `timezone_helpers.py` is well-designed, handles DST correctly
2. **Validation Added**: Recent commit (a724732) added auto-correction for negative hours
3. **Logging Good**: Timezone conversions logged with CT timestamps for debugging
4. **Config Centralized**: `TIMEZONE = 'America/Chicago'` in config.py
5. **Recent Fixes Applied**: 15 queries updated to use `CONVERT_TZ()` in last commit
6. **Cache Strategy**: In-memory caching reduces DB load for timezone-heavy queries

---

## Safe Migration Order (REVISED)

**STOP**: Cannot proceed with original plan until Critical Issues 1-3 resolved

### Phase 0: Pre-Migration Validation (NEW)

1. **Determine Current Storage Format**
   - Run data quality audit query (Issue #2)
   - Check production server timezone: `SELECT @@system_time_zone, @@session.time_zone;`
   - Verify `datetime.fromtimestamp()` behavior in production

2. **Fix Root Cause (Issue #1)**
   - Update `connecteam_client.py:271,281` to use `datetime.fromtimestamp(ts, tz=timezone.utc)`
   - Test on staging with known timestamps
   - Verify new syncs store correct times

3. **Audit Auto-Corrected Data (Issue #4)**
   - Find all shifts > 16 hours
   - Manual review: are these legitimate or corrupted?
   - Backup before fixing

4. **Document Business Rules**
   - Overnight shift date assignment (Issue #6)
   - DST transition handling (Issue #5)
   - Get stakeholder approval

### Phase 1: Query Protection (Original Plan Phase 1)

Only proceed if Phase 0 confirms data is consistent

1. Add `GREATEST(0, TIMESTAMPDIFF(...))` to Cost Analysis (lines 2851)
2. Add validation filters: `AND (clock_out IS NULL OR clock_out >= clock_in)`
3. Test on production copy

### Phase 2: Fix NOW() Ambiguity (NEW - CRITICAL)

1. Replace all `COALESCE(clock_out, NOW())` with timezone-aware version
2. Use `UTC_TIMESTAMP()` if UTC storage, or `CONVERT_TZ(NOW(), ...)` if CT storage
3. Test currently-clocked-in employee calculations

### Phase 3: Sync Validation (Original Plan Phase 2)

1. Add validation in `_parse_shift()` (already done per code review)
2. Add validation in `_sync_clock_time()`
3. Remove auto-correction or make it log to data quality table

### Phase 4: Data Correction (Original Plan Phase 3)

**ONLY IF** Phase 0 reveals data is corrupted:
1. Backup database
2. Run audit script to find bad records
3. Manual review sample before fixing
4. Run fix script with dry-run first
5. Verify calculations after fix

### Phase 5: UTC Migration (NEW - IF NEEDED)

**ONLY IF** deciding to migrate to UTC storage:
1. Add new column `clock_in_utc`, `clock_out_utc`
2. Dual-write during migration period
3. Backfill UTC columns from CT columns
4. Update all queries to use UTC columns
5. Drop old columns after verification

---

## Recommended Actions (Prioritized)

| # | Action | Effort | Impact | Risk |
|---|--------|--------|--------|------|
| 1 | Audit: Check actual storage format (UTC vs CT) | 30 min | CRITICAL | None |
| 2 | Fix: `connecteam_client.py` timestamp parsing | 1 hr | CRITICAL | Low (isolated change) |
| 3 | Test: Verify new syncs store correct times | 1 hr | CRITICAL | None (staging) |
| 4 | Audit: Find all auto-corrected shifts > 16h | 30 min | HIGH | None (read-only) |
| 5 | Document: Business rules for overnight/DST | 2 hr | HIGH | None |
| 6 | Fix: Replace NOW() with timezone-aware version | 3 hr | CRITICAL | Medium (8+ queries) |
| 7 | Test: DST transition dates (Mar 9, Nov 2) | 2 hr | HIGH | None (staging) |
| 8 | Add: Validation in sync (future/old/long shifts) | 1 hr | MEDIUM | Low |
| 9 | Refactor: Use `TimezoneHelper` consistently | 4 hr | MEDIUM | Medium |
| 10 | Clean: Remove duplicate `cached_endpoint` | 5 min | LOW | None |

**DO NOT PROCEED** with Phases 1-4 of original plan until Actions 1-6 complete

---

## Dependencies & Risks

### Code Dependencies

**High-Risk Files** (changing these affects many endpoints):
- `connecteam_client.py` → `connecteam_sync.py` → All dashboards
- `dashboard.py` → 6+ frontend pages (manager.html, etc.)
- `productivity_calculator.py` → Daily scoring, leaderboards

**Frontend Dependencies** (assumes CT times):
- `manager.html` (4600+ lines) - displays times, likely assumes CT
- `intelligent-schedule.html` - shift scheduling, timezone-critical
- `employee.html` - personal dashboard
- All use `new Date()` in JavaScript (uses browser timezone!)

**Database Schema Dependencies:**
- `clock_times` table: No timezone column, assumes naive datetime
- `activity_logs.window_start`: Stores UTC from PodFactory
- `daily_scores.score_date`: DATE type, no timezone

### Migration Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during migration | MEDIUM | CRITICAL | Full backup, dry-run, rollback plan |
| Breaking currently-working code | HIGH | CRITICAL | Audit current storage first, staged rollout |
| Frontend displays wrong times | HIGH | HIGH | Add timezone to API responses, update JS |
| Historical data inconsistency | HIGH | MEDIUM | Document cutover date, handle mixed data |
| DST edge cases missed | MEDIUM | MEDIUM | Test on DST dates, use `pytz` |
| Performance degradation | LOW | MEDIUM | Index on CONVERT_TZ results if slow |

---

## Testing Checklist

**Before Migration:**
- [ ] Confirm production server timezone (`@@system_time_zone`)
- [ ] Run audit query: Is data UTC or CT currently?
- [ ] Check sample shifts: Do times look correct?
- [ ] Find negative hours: How many records affected?
- [ ] Review auto-corrected shifts: Are they valid?

**After Timestamp Parsing Fix:**
- [ ] Staging: Sync shifts, compare to Connecteam web UI
- [ ] Check clock_in/clock_out match expected CT times
- [ ] Verify no new negative hours created
- [ ] Compare before/after for same employee

**After NOW() Fix:**
- [ ] Dashboard: Check currently-clocked-in employees
- [ ] Cost Analysis: Verify active shift hours reasonable
- [ ] Leaderboard: Confirm live scores updating correctly

**DST Transition Testing:**
- [ ] Query data from 2025-03-09 (Spring Forward)
- [ ] Query data from 2025-11-02 (Fall Back)
- [ ] Verify total hours = expected (23h and 25h)
- [ ] Check no duplicate/missing records

**After Full Migration (if UTC storage):**
- [ ] Spot check 10 employees: times display correctly?
- [ ] Frontend: Times shown in CT, not UTC?
- [ ] Reports: Historical data still correct?
- [ ] Performance: Query times acceptable?

---

## Rollback Plan

### If Migration Goes Wrong:

1. **Immediate Rollback** (< 5 min):
   - Restore database from pre-migration backup
   - Restart application servers
   - Verify dashboard loads

2. **Partial Rollback** (if some changes OK):
   - Revert specific SQL queries via git
   - Restart backend: `systemctl restart productivity-backend`
   - Clear frontend cache

3. **Data Correction** (if bad writes occurred):
   - Stop Connecteam sync
   - Identify corrupt records (clock_out < clock_in)
   - Delete corrupt records: `DELETE FROM clock_times WHERE id IN (...)`
   - Re-sync from Connecteam for affected dates

4. **Prevention**:
   - Never migrate on Friday/weekend
   - Always have backup < 1 hour old
   - Test rollback procedure on staging first
   - Keep git commit before migration for quick revert

---

## Unresolved Questions

1. **What is production server timezone?** (CRITICAL)
   - Run: `SELECT @@system_time_zone, @@session.time_zone;` on production
   - If not CT, ALL data may be wrong currently

2. **Is current data UTC or CT?** (CRITICAL)
   - Need to run audit query (Issue #2)
   - Answer determines migration strategy

3. **How does frontend handle timezones?** (HIGH)
   - JavaScript `new Date()` uses browser timezone
   - Are API responses ISO 8601 with timezone?
   - Or naive strings that JS misinterprets?

4. **Overnight shift business rule?** (MEDIUM)
   - Count toward clock-in day or clock-out day?
   - Split across both days?
   - Stakeholder decision needed

5. **Historical data cutover?** (MEDIUM)
   - If migrating to UTC, when is cutover?
   - How to handle queries spanning cutover date?

6. **Should we migrate at all?** (STRATEGIC)
   - If current storage is CT and working, why change?
   - UTC best practice, but CT simpler for single-timezone app
   - Cost/benefit analysis needed

---

## Plan File Updates

**Plan Status:** ON HOLD pending Critical Issue resolution

**Updated TODO:**

- [x] Phase 0.1: Audit current storage format (NEW)
- [x] Phase 0.2: Fix `connecteam_client.py` timestamp parsing (NEW)
- [ ] Phase 0.3: Audit auto-corrected data (NEW)
- [ ] Phase 0.4: Document business rules (NEW)
- [ ] Phase 1.1: Add GREATEST() wrapper (BLOCKED by Phase 0)
- [ ] Phase 1.2: Add validation filters (BLOCKED)
- [ ] Phase 2.1: Fix NOW() ambiguity (NEW - CRITICAL)
- [ ] Phase 2.2: Validate in _parse_shift (DONE per code review)
- [ ] Phase 2.3: Validate in _sync_clock_time (PENDING)

**Next Steps:**
1. Run audit queries to determine current state
2. Schedule meeting to discuss findings
3. Get stakeholder approval for business rules
4. Proceed only if Phase 0 passes

---

## Metrics

**Code Coverage:**
- Type safety issues: 0 (Python, duck-typed)
- Linting issues: Not run (outside scope)
- Security issues: 1 (hardcoded API key in `connecteam_client.py:400`, but in main block)

**Complexity:**
- Timezone conversions: 15+ queries
- Files requiring changes: 8-12 files
- Estimated total effort: 16-24 hours
- Risk level: CRITICAL

**Technical Debt:**
- Duplicate code: 1 instance (cached_endpoint)
- Inconsistent patterns: CONVERT_TZ parameter format
- Underutilized utilities: timezone_helpers.py
- Missing validation: Timestamp bounds checking

---

## Final Recommendation

**DO NOT PROCEED** with UTC migration until:

1. ✅ Confirmed actual storage format (audit query)
2. ✅ Fixed `datetime.fromtimestamp()` in `connecteam_client.py`
3. ✅ Tested on staging with known-good data
4. ✅ Documented business rules for overnight/DST
5. ✅ Fixed `NOW()` ambiguity in all queries
6. ✅ Stakeholder approval for migration approach

**Current plan assumes pure CT storage but code shows mixed UTC/CT**. This conflict must be resolved first or risk catastrophic data corruption.

Recommend 2-week timeline:
- Week 1: Audit, fix parsing, test, document
- Week 2: Implement fixes, test DST, staged rollout

**Success Criteria:**
- Zero negative hours in production
- All times display correctly in CT
- DST transitions handled properly
- Historical data preserved accurately
- No performance degradation

---

**Report Generated:** 2025-12-11
**Review Duration:** ~2 hours
**Files Modified:** 0 (read-only review)
**Action Required:** Execute Phase 0 audit before any code changes
