# Data Quality Issues Log

## Overview
This document tracks data quality issues discovered during productivity calculations and their resolutions.

---

## Issue #1: Adranique Franks - Dual-Shift Without Clock Record

**Date Discovered**: Dec 10, 2025
**Employee**: Adranique Franks (ID=243)
**Status**: Noted (No code fix)

### Problem
`active_minutes = 0` despite having 58 items processed and 220 clocked minutes.

### Root Cause
Employee had **two separate work sessions** on the same CT date, but only ONE had a clock record:

| Session | Time (CT) | Activities | Items | Clock Record |
|---------|-----------|------------|-------|--------------|
| Morning | 08:26-10:26 | 16 | ~16 | **NONE** |
| Afternoon | 15:32-19:12 | 39 | 42 | 220 min |

### Technical Details
- `calculate_active_time()` pulls ALL 55 activities for Dec 10 CT
- First activity at UTC `14:26:00` is BEFORE clock-in at UTC `21:32:37`
- Calculation: `start_gap = (first_activity - clock_in)` = **NEGATIVE** (~-426 min)
- Negative start_gap breaks calculation → returns 0 active_minutes

### Impact
- `active_minutes`: 0 (incorrect - should be ~39 min)
- `items_processed`: 58 (correct)
- `clocked_minutes`: 220 (correct)
- `efficiency_rate`: 0% (incorrect)

### Possible Causes
1. Employee forgot to clock in for morning shift
2. Manual PodFactory scan without Connecteam clock
3. Data entry/sync timing issue

### Resolution
Noted as data quality issue. No code fix applied - would require modifying calculation logic to only count activities within clock periods (significant architectural change).

### Recommendation
- Train employees on proper clock-in procedures
- Consider adding validation alert when activities exist without clock record

---

## Issue #2: Abraham Ramirez - UTC/CT Timezone Mismatch (FIXED)

**Date Discovered**: Dec 10, 2025
**Employee**: Abraham Ramirez (ID=28)
**Status**: FIXED

### Problem
`active_hours = 0` in Cost Analysis despite having 360 items processed.

### Root Cause
`calculate_active_time()` queried `clock_times` table using UTC range, but `clock_times` stores values in CT (Central Time).

### Fix Applied
Three locations in `productivity_calculator.py`:
1. `calculate_active_time()` (lines 68-80): Use `DATE(clock_in) = %s` with CT date
2. `process_employee_day()` (lines 252-266): Same pattern
3. `process_all_employees_for_date()` (lines 470-481): Same pattern

**Note**: `CONVERT_TZ` failed on production (MySQL timezone tables not loaded). Used `DATE_ADD(clock_in, INTERVAL 6 HOUR)` instead.

### Results After Fix
- `active_minutes`: 0 → **466**
- `clocked_minutes`: 192 → **780**
- `efficiency_rate`: 0% → **60%**

---

## Issue #3: Hoang Duong - Stale daily_scores (FIXED)

**Date Discovered**: Dec 10, 2025
**Employee**: Hoang Duong (ID=255)
**Status**: FIXED

### Problem
`active_minutes = 0` despite having 374 items and 620 clocked minutes.

### Root Cause
`daily_scores` table had stale data from before the timezone fix was deployed.

### Resolution
Reprocessed via `calc.process_employee_day(255, date(2025, 12, 10))`

### Results After Fix
- `active_minutes`: 0 → **102**
- `items_processed`: 374
- `clocked_minutes`: 620
- `efficiency_rate`: **16%**

---

## Issue #4: Kieu Nguyen - Stale daily_scores (FIXED)

**Date Discovered**: Dec 10, 2025
**Employee**: Kieu Nguyen (ID=249)
**Status**: FIXED

### Problem
`active_minutes = 0` despite having 105 items and 728 clocked minutes.

### Root Cause
Same as Issue #3 - stale `daily_scores` data.

### Resolution
Reprocessed via `calc.process_employee_day(249, date(2025, 12, 10))`

### Results After Fix
- `active_minutes`: 0 → **364**
- `items_processed`: 105
- `clocked_minutes`: 728
- `efficiency_rate`: **50%**

---

## Issue #5: dung duong - Scheduler Timing (FIXED)

**Date Discovered**: Dec 10, 2025
**Employee**: dung duong
**Status**: FIXED

### Problem
`clocked_minutes = 0` in `daily_scores` despite having 608 minutes in `clock_times`.

### Root Cause
Scheduler calculated `daily_scores` BEFORE `clock_times` synced from Connecteam.

### Resolution
Reprocessed all employees via `calc.process_all_employees_for_date(date(2025, 12, 10))`

---

## Employees With Legitimate Data Gaps (No Fix Needed)

| Employee | Issue | Reason |
|----------|-------|--------|
| Admin | NO_CLOCK | No Connecteam ID configured |
| Nguyen Tran | NO_CLOCK | Didn't clock in on Dec 10 |
| Monique Ruiz | NO_CLOCK | Last clock was Dec 9 |
| Thien Thai Dang | NO_ACTIVITIES | Clocked but never scanned items |
| Kristal Nguyen | NO_DATA | Brief test clock, no activities |

---

## Summary Statistics (Dec 10, 2025)

**After All Fixes**:
- Total Employees: 32
- Total Clocked Hours: 257.40 hrs
- Total Active Hours: 118.77 hrs
- Total Items Processed: 10,666
- Average Efficiency: 46.1%

**Top 5 by Efficiency (min 100 items)**:
1. La Nguyen: 88%
2. Roberto Martinez: 83%
3. Nathan Gonzales: 83%
4. Anh Tu Le: 78%
5. Brandon Magallanez: 78%

---

---

## Issue #6: Connecteam Sync 6-Hour Offset Bug (PENDING FIX)

**Date Discovered**: Dec 12, 2025
**Status**: Bug Identified, Fix Pending
**Severity**: HIGH - Affects all historical data

### Problem
Dec 1-9 data shows mismatches between `clock_times` and `daily_scores`. Manual sync attempts showed "timezone-shifted duplicate" warnings.

### Data Audit Results (Dec 1-11)
| Date | clock_times (min) | daily_scores (min) | Diff |
|------|-------------------|-------------------|------|
| Dec 1 | 5,330 | 4,989 | +341 |
| Dec 2 | 13,206 | 8,698 | +4,508 |
| Dec 3 | 11,949 | 10,099 | +1,850 |
| Dec 4 | 14,110 | 11,815 | +2,295 |
| Dec 5 | 12,833 | 10,652 | +2,181 |
| Dec 6 | 13,102 | 11,032 | +2,070 |
| Dec 7 | 4,063 | 3,570 | +493 |
| Dec 8 | 4,038 | 3,570 | +468 |
| Dec 9 | 14,080 | 12,150 | +1,930 |
| Dec 10 | 15,544 | 15,544 | **0** |
| Dec 11 | 18,022 | 18,022 | **0** |

### Dec 2 Deep Dive
- **Connecteam API**: 52 shifts, 15,979 minutes
- **Database**: 31 records, 9,858 minutes
- **Gap**: 10 employees MISSING = 6,121 minutes

### Root Cause
**File**: `backend/integrations/connecteam_sync.py`
**Function**: `_sync_clock_time()` (lines 325-332)

```python
# BUG: Detects 6hr offset but SKIPS instead of CORRECTING
if is_tz_shifted and not is_same_shift:
    logger.warning("Detected timezone-shifted duplicate...")
    return True  # <-- Returns without correcting the shifted record!
```

### Impact
1. Old records stored with 6-hour offset (UTC vs CT)
2. Sync detects offset but doesn't correct it
3. Manual backfill created duplicates (old shifted + new correct)
4. Server running buggy code

### Current State
- **Server**: Buggy sync running (`podfactory-sync` PM2)
- **Database**: Has duplicate records
- **Manual Backfill**: 16 Dec 2 records inserted

### Resolution Plan
1. Fix local code to UPDATE shifted records instead of skip
2. Push to GitHub
3. Redeploy to server
4. Clean up duplicate records

---

## Issue #7: Server Sync Running Buggy Code

**Date Discovered**: Dec 12, 2025
**Status**: Pending Deployment

### Server Details
| Property | Value |
|----------|-------|
| IP | 134.199.194.237 |
| Domain | reports.podgasus.com |
| Tunnel | Cloudflare |
| Git Remote | github.com/nguyentranus1989/productivity-system.git |

### PM2 Processes
| Process | Status |
|---------|--------|
| cloudflare-tunnel | online |
| podfactory-sync | online (BUGGY CODE) |
| flask-backend | stopped |

### Required Actions
1. Stop `podfactory-sync`
2. `git pull origin main`
3. Restart services
4. Verify fix working

---

## Prevention Measures

1. **Scheduler Order**: Ensure `clock_times` sync runs BEFORE `daily_scores` calculation
2. **Timezone Awareness**: All queries to `clock_times` use CT date directly
3. **Validation Alerts**: Consider adding alerts for activities without clock records
4. **Employee Training**: Reinforce clock-in procedures before scanning items
5. **Sync Fix**: When detecting timezone-shifted records, UPDATE them instead of skip
6. **Deployment Pipeline**: Test sync locally before deploying to server
