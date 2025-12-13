# Debugger Report: Clock Times Timezone Issue - Dec 12, 2025

**Date:** 2025-12-12
**Time:** 3:07 PM CT
**Issue:** Clock_times records showing wrong times for Dec 12

---

## Executive Summary

### Problem
3 employees have incorrect clock-in times in DB vs user-confirmed actual times for Dec 12:
- **Man Nguyen**: Actual 2:06 AM CT, DB shows duplicate records (8:06 PM Dec 11 + 8:06 AM Dec 12)
- **Toan Chau**: Actual 4:45 AM CT, DB shows duplicate + triplicate records
- **Andrea Romero**: Actual 5:09 AM CT, DB shows duplicate records

### Root Cause
**6-hour timezone offset error** - all confirmed employees synced around 8:03-8:06 AM CT creating TWO versions:
1. Clock_in stored as UTC timestamp (no conversion) → appears 6h earlier in CT display
2. Clock_in stored with +12h offset → appears 6h later than actual

### Impact
- Wrong clock-in times affect productivity calculations
- Duplicate records per employee
- Pattern affects 59 total Dec 12 records (42 synced morning, 17 afternoon)

---

## Technical Analysis

### Database Evidence

#### Man Nguyen (Actual: 2:06 AM CT)
```
Record #1 (ID: 25700):
  Clock-in (UTC):  2025-12-12 02:06:23 UTC
  Clock-in (CT):   2025-12-11 08:06:23 PM CT  ← 6h EARLIER (previous day)
  Created at:      2025-12-12 14:03:15 UTC (8:03 AM CT)
  Difference:      -5.99 hours

Record #2 (ID: 25679):
  Clock-in (UTC):  2025-12-12 14:06:23 UTC
  Clock-in (CT):   2025-12-12 08:06:23 AM CT  ← 6h LATER
  Created at:      2025-12-12 13:15:58 UTC (7:15 AM CT)
  Difference:      +6.01 hours
```

#### Toan Chau (Actual: 4:45 AM CT)
```
Record #1 (ID: 25706):
  Clock-in (UTC):  2025-12-12 04:45:46 UTC
  Clock-in (CT):   2025-12-11 10:45:46 PM CT  ← 6h EARLIER (previous day)
  Created at:      2025-12-12 14:06:04 UTC (8:06 AM CT)
  Difference:      -5.99 hours

Record #2 (ID: 25690):
  Clock-in (UTC):  2025-12-12 16:45:46 UTC
  Clock-in (CT):   2025-12-12 10:45:46 AM CT  ← 6h LATER
  Created at:      2025-12-12 13:25:42 UTC (7:25 AM CT)
  Difference:      +6.01 hours

Record #3 (ID: 25720):
  Clock-in (UTC):  2025-12-12 17:41:35 UTC
  Clock-in (CT):   2025-12-12 11:41:35 AM CT  ← 6.94h LATER
  Created at:      2025-12-12 17:51:47 UTC (11:51 AM CT)
  Difference:      +6.94 hours
```

#### Andrea Romero (Actual: 5:09 AM CT)
```
Record #1 (ID: 25702):
  Clock-in (UTC):  2025-12-12 05:09:30 UTC
  Clock-in (CT):   2025-12-11 11:09:30 PM CT  ← 6h EARLIER (previous day)
  Created at:      2025-12-12 14:04:01 UTC (8:04 AM CT)
  Difference:      -5.99 hours

Record #2 (ID: 25696):
  Clock-in (UTC):  2025-12-12 17:09:30 UTC
  Clock-in (CT):   2025-12-12 11:09:30 AM CT  ← 6h LATER
  Created at:      2025-12-12 13:41:36 UTC (7:41 AM CT)
  Difference:      +6.01 hours
```

### Pattern Identification

**All 3 confirmed employees synced between 8:03-8:06 AM CT**

Sync time distribution for ALL Dec 12 records (59 total):
- Before 3 AM CT: **0 records**
- 3 AM - 12 PM CT: **42 records** (includes confirmed employees)
- After 12 PM CT: **17 records**

**Duplicate pattern:** Each employee has 2+ clock_times records with exactly 12-hour offset between UTC timestamps.

### Evidence Trail

1. **Expected behavior:** User clocks in at 2:06 AM CT → stored as `2025-12-12 08:06:00 UTC` (CT + 6h)
2. **Actual Record #1:** Stored as `2025-12-12 02:06:23 UTC` (raw CT time treated as UTC)
3. **Actual Record #2:** Stored as `2025-12-12 14:06:23 UTC` (CT + 12h instead of +6h)

**Hypothesis:** Connecteam sync process applying inconsistent timezone conversions:
- One sync path: stores CT timestamp AS UTC (no conversion)
- Another sync path: adds 12h instead of 6h offset
- Both records created during same sync window (7-8 AM CT)

---

## Actionable Recommendations

### Priority 1: Data Cleanup
1. Delete incorrect duplicate records for Dec 12
2. Keep only records matching user-confirmed times
3. Verify all 59 Dec 12 records - likely ALL affected

### Priority 2: Sync Code Investigation
**Files to investigate:**
- `backend/integrations/connecteam_sync.py` (active sync)
- `backend/daily_reconciliation.py`
- `backend/connecteam_reconciliation.py`
- `backend/auto_reconciliation.py`

**Look for:**
- Multiple INSERT paths for clock_times
- Timezone conversion logic (especially CT → UTC)
- Duplicate prevention logic
- Any code applying +12h offset

### Priority 3: Prevention
1. Add unique constraint: `(employee_id, clock_in)` in clock_times table
2. Add validation: reject clock_in times >6h offset from current time
3. Standardize timezone conversion to single code path
4. Add logging for timezone conversions during sync

### Priority 4: Monitoring
- Check Dec 13+ for same pattern
- Verify historical dates (Dec 6-11 data looks suspect too - created_at shows ~100-130h deltas)
- Alert on duplicate clock_times creation

---

## Supporting Evidence

**Script used:** `backend/analyze_confirmed_times.py`

**Query executed:**
```sql
SELECT ct.id, e.name, ct.clock_in, ct.clock_out, ct.created_at
FROM clock_times ct
JOIN employees e ON ct.employee_id = e.id
WHERE e.name IN ('Toan Chau', 'Man Nguyen', 'Andrea Romero')
AND DATE(ct.clock_in) = '2025-12-12'
ORDER BY e.name, ct.clock_in
```

**Total affected scope:**
- 3 confirmed employees
- 7 duplicate records between them
- 59 total Dec 12 clock_times records (likely all affected)
- Possibly hundreds more in Dec 6-11 (high created_at deltas observed)

---

## Unresolved Questions

1. Why are TWO records created per employee during single sync window?
2. Which sync process is correct - the -6h or +6h version?
3. How many total duplicate records exist across all dates?
4. Is the +12h offset hardcoded somewhere or calculation error?
5. Why didn't unique constraints prevent duplicates?
