# Timezone Handling Analysis Report

**Date:** 2025-12-11
**System:** Productivity Tracker
**Timezone:** America/Chicago (CT - Central Time)

---

## Executive Summary

The system has a **CRITICAL TIMEZONE INCONSISTENCY** between data sources:

| Source | Storage Format | Issue |
|--------|---------------|-------|
| Connecteam API | Unix timestamps (UTC) | `datetime.fromtimestamp()` converts to **LOCAL** time (CT on Windows) |
| `clock_times` table | CT directly | **NOT** UTC |
| `activity_logs` table | UTC | Stores UTC correctly |
| MySQL `NOW()` | Server time | Likely **UTC** on cloud servers |
| `COALESCE(clock_out, NOW())` | Mixed | **BUG**: Compares CT with UTC |

**Root Cause:** When `COALESCE(clock_out, NOW())` is used for currently clocked-in employees, it mixes CT stored times with UTC `NOW()`, causing calculations to be off by **5-6 hours**.

---

## Part 1: Data Flow Documentation

### 1.1 Connecteam Data Flow

```
Connecteam API (Unix timestamp UTC)
        |
        v
connecteam_client.py Line 271: datetime.fromtimestamp(clock_in_timestamp)
        |
        v (Converts to LOCAL timezone - CT on this Windows machine)
        |
        v
connecteam_sync.py: _sync_clock_time()
        |
        v
clock_times table (stores CT directly, NOT UTC)
```

### 1.2 PodFactory Data Flow

```
PodFactory Database (UTC)
        |
        v
podfactory_sync.py: fetch_new_activities()
        |
        v
activity_logs table (stores UTC)
        |
        v
Dashboard queries with CONVERT_TZ for display
```

### 1.3 Current Mixed State

- **clock_times**: Stores CT (via Connecteam's local conversion)
- **activity_logs**: Stores UTC (via PodFactory)
- **daily_scores.score_date**: CT date
- **podfactory_sync_log**: UTC via `UTC_TIMESTAMP()`

---

## Part 2: Timezone Conversion Locations

### 2.1 connecteam_client.py

| Line | Code | Issue |
|------|------|-------|
| 271 | `clock_in = datetime.fromtimestamp(clock_in_timestamp)` | **BUG**: Converts to LOCAL time, not UTC |
| 281 | `clock_out = datetime.fromtimestamp(clock_out_timestamp)` | **BUG**: Same issue |
| 303 | `current_time = datetime.now().timestamp()` | Uses local time |
| 314 | `datetime.fromtimestamp(break_start)` | **BUG**: Same issue |
| 315 | `datetime.fromtimestamp(break_end)` | **BUG**: Same issue |

### 2.2 connecteam_sync.py

| Line | Code | Issue |
|------|------|-------|
| 27-28 | `self.central_tz = pytz.timezone('America/Chicago')` | Correct setup |
| 30-36 | `get_central_date()`, `get_central_datetime()` | Correct helpers |
| 38-44 | `convert_to_central(utc_dt)` | **UNUSED** - assumes input is UTC, but Connecteam gives CT |
| 234-237 | Comments say "Already UTC from Connecteam" | **WRONG**: It's actually CT from `fromtimestamp()` |
| 307-310 | `# NOTE: Connecteam sends times in CT, NOT UTC` | **CORRECT** comment - but contradicts earlier comments |
| 340-341 | `total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW())` | **BUG**: clock_in is CT, NOW() is UTC |
| 350-355 | Same UPDATE with `NOW()` | **BUG**: Same issue |
| 378 | `DATE(ct.clock_in) = CURDATE()` | **BUG**: CURDATE() is server time (UTC) |

### 2.3 dashboard.py

| Line | Code | Issue |
|------|------|-------|
| 134-142 | `get_central_date()`, `get_central_datetime()` | Correct Python helpers |
| 202 | `DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))` | **WRONG**: clock_in is already CT, not UTC |
| 489 | `DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))` | **CORRECT**: activity_logs is UTC |
| 549 | `DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))` | **CORRECT** |
| 611 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))` | **BUG**: Mixes CT with UTC |
| 677-678 | `COALESCE(MAX(clock_out), NOW())` | **BUG**: Mixes CT with UTC |
| 874-876 | Similar COALESCE pattern | **BUG** |
| 914 | `DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = CURDATE()` | **CORRECT** for activity_logs |
| 1326 | `COALESCE(ROUND(SUM(TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))))` | **BUG** |
| 1471-1473 | `COALESCE(MAX(clock_out), NOW())` | **BUG** |
| 1942-1945 | `UTC_TIMESTAMP()` | Correct for activity_logs comparison |

### 2.4 podfactory_sync.py

| Line | Code | Issue |
|------|------|-------|
| 86-87 | `self.utc`, `self.central` | Correct timezone setup |
| 292-293 | `UTC_TIMESTAMP()` for sync_log | Correct |
| 600-608 | Keeps times in UTC, localizes if naive | Correct approach |
| 705 | `DATE(al.window_start) = CURDATE()` | **POTENTIAL BUG**: Should use UTC_TIMESTAMP or CONVERT_TZ |

### 2.5 productivity_calculator.py

| Line | Code | Issue |
|------|------|-------|
| 65-77 | `DATE_ADD(MIN(clock_in), INTERVAL 6 HOUR)` | **WORKAROUND**: Manual CT to UTC conversion (ignores DST!) |
| 73-76 | `MAX(COALESCE(clock_out, NOW()))` | **BUG**: NOW() is UTC, clock_out is CT |
| 257-258 | Same pattern | **BUG** |
| 298-300 | `CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')` | Correct for activity_logs |
| 330 | Same CONVERT_TZ | Correct |
| 451 | `convert_utc_to_central(clock_in)` | **WRONG**: clock_in is already CT |

### 2.6 timezone_helpers.py

| Line | Code | Status |
|------|------|--------|
| 13-42 | `ct_date_to_utc_range()` | **CORRECT** - properly handles DST |
| 44-50 | `utc_to_ct()` | **CORRECT** |
| 52-58 | `ct_to_utc()` | **CORRECT** |
| 71-82 | `is_dst()` | **CORRECT** |

---

## Part 3: Bug Catalog

### BUG 1: `fromtimestamp()` Local Conversion [CRITICAL]

**Location:** `connecteam_client.py` lines 271, 281, 314, 315

**Problem:** `datetime.fromtimestamp()` converts Unix timestamps to the **local** system timezone. On this Windows machine, that's CT. On a Linux server, it might be UTC.

**Impact:** Inconsistent data depending on server timezone.

**Evidence:**
```python
# Line 271
clock_in = datetime.fromtimestamp(clock_in_timestamp)  # Converts to LOCAL time!
```

### BUG 2: `COALESCE(clock_out, NOW())` Timezone Mixing [CRITICAL]

**Location:** Multiple files - dashboard.py (611, 677, 874, 1326, 1471), productivity_calculator.py (73, 257), connecteam_sync.py (340, 350)

**Problem:** `clock_times.clock_out` is stored in CT. `NOW()` returns server time (usually UTC). When an employee is currently clocked in, the calculation is **off by 5-6 hours**.

**Impact:** For active employees, hours worked shows incorrectly (could show 12+ hours when they've only worked 6).

**Evidence:**
```sql
-- dashboard.py line 611
TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))
-- clock_in = 7:00 AM CT
-- NOW() = 1:00 PM UTC (which is 7:00 AM CT, so this is correct IF it's currently 7am CT)
-- But if NOW() is 7:00 PM UTC (1:00 PM CT) and clock_in is 7:00 AM CT
-- TIMESTAMPDIFF would calculate: 7:00 PM - 7:00 AM = 12 hours
-- Actual worked: 6 hours (7am to 1pm CT)
-- Error: +6 hours
```

### BUG 3: `CURDATE()` Server Timezone [MEDIUM]

**Location:** connecteam_sync.py (378), dashboard.py (614, 687, 877), productivity_calculator.py (263, 478)

**Problem:** `CURDATE()` returns the date in server timezone. If server is UTC and it's 11 PM CT (5 AM UTC next day), `CURDATE()` returns the wrong date.

**Impact:** Data filtering returns wrong day's data near midnight CT.

### BUG 4: Wrong `CONVERT_TZ` on Already-CT Data [MEDIUM]

**Location:** dashboard.py (202)

**Problem:** Applying `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')` to `clock_times.clock_in` which is already in CT.

**Impact:** Double-converts, showing times 5-6 hours off.

### BUG 5: Hardcoded 6-hour Offset [LOW]

**Location:** productivity_calculator.py (69-74)

**Problem:** Uses `DATE_ADD(MIN(clock_in), INTERVAL 6 HOUR)` instead of proper timezone conversion.

**Impact:** During Daylight Saving Time (CDT = UTC-5), calculations are off by 1 hour.

---

## Part 4: Comprehensive Fix Plan

### Phase 1: Standardize Data Storage (HIGH PRIORITY)

**Goal:** Store ALL times in UTC in database.

#### Step 1.1: Fix Connecteam Client

**File:** `backend/integrations/connecteam_client.py`

**Changes:**
```python
# Line 271 - Change:
clock_in = datetime.fromtimestamp(clock_in_timestamp)
# To:
clock_in = datetime.utcfromtimestamp(clock_in_timestamp)

# Line 281 - Change:
clock_out = datetime.fromtimestamp(clock_out_timestamp)
# To:
clock_out = datetime.utcfromtimestamp(clock_out_timestamp)

# Line 303 - Change:
current_time = datetime.now().timestamp()
# To:
current_time = datetime.utcnow().timestamp()

# Lines 314-315 - Similar changes for break times
```

#### Step 1.2: Fix Connecteam Sync NOW() Usage

**File:** `backend/integrations/connecteam_sync.py`

**Changes:**
```python
# Line 340 - Change:
total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW())
# To:
total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, UTC_TIMESTAMP())

# Line 355 - Similar change
# Line 378 - Change CURDATE() to UTC date calculation
```

### Phase 2: Migrate Existing Data

**Goal:** Convert existing `clock_times` data from CT to UTC.

#### Step 2.1: Create Migration Script

```sql
-- Backup first!
CREATE TABLE clock_times_backup AS SELECT * FROM clock_times;

-- Migrate clock_in (CT -> UTC)
-- During CST (Nov-Mar): Add 6 hours
-- During CDT (Mar-Nov): Add 5 hours
UPDATE clock_times
SET
    clock_in = CONVERT_TZ(clock_in, 'America/Chicago', '+00:00'),
    clock_out = CASE
        WHEN clock_out IS NOT NULL
        THEN CONVERT_TZ(clock_out, 'America/Chicago', '+00:00')
        ELSE NULL
    END,
    updated_at = NOW();
```

#### Step 2.2: Verify Migration

```sql
-- Check a sample
SELECT
    id,
    employee_id,
    clock_in AS new_utc,
    (SELECT clock_in FROM clock_times_backup WHERE id = ct.id) AS old_ct,
    TIMESTAMPDIFF(HOUR,
        (SELECT clock_in FROM clock_times_backup WHERE id = ct.id),
        clock_in
    ) AS hours_diff
FROM clock_times ct
LIMIT 10;
-- Should show 5-6 hours difference
```

### Phase 3: Fix All Queries

**Goal:** Update all SQL queries to use UTC consistently.

#### Step 3.1: Fix Dashboard Queries

**File:** `backend/api/dashboard.py`

**Pattern Changes:**

```sql
-- OLD (BUG):
WHERE DATE(ct.clock_in) = CURDATE()

-- NEW (CORRECT):
WHERE ct.clock_in >= %s AND ct.clock_in < %s
-- Pass UTC start/end from Python using TimezoneHelper.ct_date_to_utc_range()
```

```sql
-- OLD (BUG):
TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))

-- NEW (CORRECT):
TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, UTC_TIMESTAMP()))
```

#### Step 3.2: Update Python Query Calls

```python
# Example fix pattern
from utils.timezone_helpers import TimezoneHelper
tz = TimezoneHelper()

# Get date parameter
date_str = request.args.get('date', tz.get_current_ct_date().strftime('%Y-%m-%d'))

# Convert to UTC range
utc_start, utc_end = tz.ct_date_to_utc_range(date_str)

# Use in query
cursor.execute("""
    SELECT * FROM clock_times
    WHERE clock_in >= %s AND clock_in < %s
""", (utc_start, utc_end))
```

### Phase 4: Update Display Logic

**Goal:** Convert to CT only for display.

#### Step 4.1: Add Display Conversion

```python
# In API responses
def format_clock_time_for_display(utc_dt):
    if utc_dt is None:
        return None
    tz = TimezoneHelper()
    ct_dt = tz.utc_to_ct(utc_dt)
    return ct_dt.strftime('%I:%M %p')  # e.g., "7:00 AM"
```

#### Step 4.2: Update Frontend

Ensure frontend receives and displays CT times correctly. Add timezone indicator where needed.

### Phase 5: Handle DST

**Goal:** Ensure DST transitions don't break calculations.

#### Step 5.1: Use pytz for All Conversions

```python
# Always use pytz, never manual hour offsets
import pytz

central = pytz.timezone('America/Chicago')
utc = pytz.UTC

# Correct conversion
ct_time = utc_time.astimezone(central)
```

#### Step 5.2: Test DST Boundaries

- Test March DST transition (clock forward)
- Test November DST transition (clock back)
- Ensure no duplicate or missing hours

---

## Part 5: Implementation Order

### Priority 1: Stop the Bleeding (Day 1)
1. Fix `connecteam_client.py` `fromtimestamp()` calls
2. Fix `NOW()` to `UTC_TIMESTAMP()` in connecteam_sync.py

### Priority 2: Migrate Data (Day 2)
1. Backup `clock_times` table
2. Run migration script
3. Verify migration

### Priority 3: Fix Queries (Days 3-4)
1. Update dashboard.py queries (20+ locations)
2. Update productivity_calculator.py queries
3. Update connecteam_sync.py queries

### Priority 4: Testing (Day 5)
1. Test with currently clocked-in employees
2. Test date boundary cases (11 PM CT)
3. Test historical data display

---

## Part 6: Files Requiring Changes

| File | Priority | Changes Needed |
|------|----------|----------------|
| `connecteam_client.py` | P1 | Fix `fromtimestamp()` to use UTC |
| `connecteam_sync.py` | P1 | Fix `NOW()` and `CURDATE()` |
| `dashboard.py` | P2 | Fix 20+ queries with COALESCE |
| `productivity_calculator.py` | P2 | Fix hardcoded offset, COALESCE |
| `podfactory_sync.py` | P3 | Verify UTC consistency |
| `timezone_helpers.py` | - | Already correct, expand usage |

---

## Part 7: Unresolved Questions

1. **Server Timezone:** What timezone is the MySQL server configured for? Run `SELECT @@global.time_zone, @@session.time_zone;`

2. **Historical Data Accuracy:** How far back does the CT-stored data go? Migration needs to handle all historical records.

3. **DST Handling:** The `INTERVAL 6 HOUR` hardcode in productivity_calculator.py - how long has this been in place? Any reports of 1-hour discrepancies in March/November?

4. **Multiple Servers:** If running on multiple servers (e.g., dev vs prod), are their system timezones identical?

5. **Frontend Impact:** Does the frontend make any timezone assumptions that need updating?

---

## Appendix A: Quick Reference

### Correct UTC Patterns

```python
# Python - Get UTC now
from datetime import datetime
utc_now = datetime.utcnow()

# Python - Parse UTC timestamp
utc_dt = datetime.utcfromtimestamp(unix_timestamp)

# Python - Convert CT to UTC
import pytz
central = pytz.timezone('America/Chicago')
ct_dt = central.localize(naive_dt)
utc_dt = ct_dt.astimezone(pytz.UTC)
```

```sql
-- MySQL - Get UTC now
SELECT UTC_TIMESTAMP();

-- MySQL - Convert UTC to CT for display
SELECT CONVERT_TZ(utc_column, '+00:00', 'America/Chicago');

-- MySQL - Get UTC date boundaries for a CT date
-- Use Python TimezoneHelper instead of SQL for accuracy
```

### Wrong Patterns (AVOID)

```python
# WRONG - Uses local timezone
datetime.fromtimestamp(ts)
datetime.now()

# WRONG - Manual hour offset (ignores DST)
utc_dt + timedelta(hours=6)
```

```sql
-- WRONG - Server timezone dependent
NOW()
CURDATE()

-- WRONG - Mixing CT data with UTC functions
WHERE DATE(ct_column) = CURDATE()
COALESCE(clock_out, NOW())
```
