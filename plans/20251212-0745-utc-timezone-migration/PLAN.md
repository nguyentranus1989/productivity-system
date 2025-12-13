# UTC Timezone Migration Plan

**Date:** 2025-12-12
**Author:** Planning Agent
**Status:** DRAFT

## Executive Summary

This plan addresses timezone inconsistency in the `clock_times` table causing 6-hour offset errors. The root cause: `clock_in`/`clock_out` are stored in Central Time (CT) while MySQL `NOW()` returns UTC.

**Recommendation:** Store everything in UTC, convert to CT only for display.

---

## 1. Current State Analysis

### 1.1 Data Sources & Storage Patterns

| Source | Field | Current Storage | Issue |
|--------|-------|-----------------|-------|
| Connecteam Sync | `clock_in`, `clock_out` | **CT** (via `datetime.fromtimestamp()` on UTC server - **WRONG ASSUMPTION**) | Stored as naive datetime |
| PodFactory Sync | `window_start`, `window_end` | **UTC** (explicitly handled) | Already correct |
| MySQL | `NOW()`, `UTC_TIMESTAMP()` | **UTC** | Correct |
| activity_logs | timestamps | **UTC** | Correct |

### 1.2 Root Cause

In `backend/integrations/connecteam_client.py`, line 271:
```python
clock_in = datetime.fromtimestamp(clock_in_timestamp)
```

- Connecteam API returns Unix timestamps (seconds since epoch, UTC)
- `datetime.fromtimestamp()` converts to **local server time** (UTC on production)
- However, the audit script (`scripts/audit_timezone_state.py`) claims clock_times stores UTC
- **CONFUSION**: Comments say UTC but actual behavior depends on server timezone setting

### 1.3 Problematic Query Patterns

Files using `TIMESTAMPDIFF(MINUTE, clock_in, NOW())` that will be broken if clock_in is CT but NOW() is UTC:

| File | Line | Pattern |
|------|------|---------|
| `api/dashboard.py` | 610 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))` |
| `api/dashboard.py` | 680 | `COALESCE(MAX(clock_out), NOW())` |
| `api/dashboard.py` | 877 | `TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), UTC_TIMESTAMP()))` |
| `api/dashboard.py` | 1327 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, UTC_TIMESTAMP()))` |
| `api/dashboard.py` | 1473 | `TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), NOW()))` |
| `api/dashboard.py` | 3485 | `TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW()))` |
| `api/dashboard.py` | 3617 | `TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, NOW()))` |
| `calculations/productivity_calculator.py` | 73 | `TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, NOW())))` |
| `calculations/productivity_calculator.py` | 255 | `MAX(COALESCE(clock_out, NOW()))` |
| `integrations/connecteam_sync.py` | 352 | `SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW())` |
| `connecteam_reconciliation.py` | 186 | `TIMESTAMPDIFF(HOUR, ct.clock_in, NOW())` |

### 1.4 Current Timezone Handling (Already Exists)

**Good patterns already in use:**
- `utils/timezone_helpers.py` - `TimezoneHelper` class with CT/UTC conversions
- `podfactory_sync.py` - Stores times in UTC explicitly
- Some queries use `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')` for date filtering

---

## 2. Migration Strategy: Store Everything in UTC

### 2.1 Overview

1. **Phase 1:** Fix data ingestion (Connecteam sync stores UTC)
2. **Phase 2:** Migrate existing CT data to UTC
3. **Phase 3:** Update all queries to use UTC consistently
4. **Phase 4:** Update display layer to convert UTC -> CT

### 2.2 Phase 1: Fix Data Ingestion

**File:** `backend/integrations/connecteam_client.py`

**Current (Line 271, 281, 303):**
```python
clock_in = datetime.fromtimestamp(clock_in_timestamp)
clock_out = datetime.fromtimestamp(clock_out_timestamp)
current_time = datetime.now().timestamp()
```

**Change to:**
```python
from datetime import datetime, timezone

clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc)
clock_out = datetime.fromtimestamp(clock_out_timestamp, tz=timezone.utc)
current_time = datetime.now(timezone.utc).timestamp()
```

**File:** `backend/integrations/connecteam_sync.py`

Verify `_sync_clock_time()` stores the UTC datetime correctly. Current implementation at line 409 inserts `shift.clock_in` which should now be UTC-aware.

### 2.3 Phase 2: Data Migration

**SQL Migration Script:**

```sql
-- STEP 1: Create backup table
CREATE TABLE clock_times_backup_20251212 AS SELECT * FROM clock_times;

-- STEP 2: Verify backup
SELECT COUNT(*) FROM clock_times;
SELECT COUNT(*) FROM clock_times_backup_20251212;

-- STEP 3: Identify records to migrate (CT -> UTC)
-- During standard time (CDT offset is -5, CST is -6)
-- Assuming data is CT and needs to become UTC

-- STEP 4: Update clock_in (add 6 hours for CST, or 5 for CDT)
-- Check if current DST: CONVERT_TZ returns correct offset
UPDATE clock_times
SET clock_in = DATE_ADD(clock_in, INTERVAL 6 HOUR)
WHERE clock_in IS NOT NULL
AND clock_in < '2025-12-12';  -- Only migrate historical data

-- STEP 5: Update clock_out similarly
UPDATE clock_times
SET clock_out = DATE_ADD(clock_out, INTERVAL 6 HOUR)
WHERE clock_out IS NOT NULL
AND clock_out < '2025-12-12';

-- STEP 6: Verify migration
SELECT id, employee_id,
       clock_in as new_utc,
       CONVERT_TZ(clock_in, '+00:00', 'America/Chicago') as should_be_original
FROM clock_times
LIMIT 10;
```

**CAUTION:** DST handling - migration must account for whether original data was CDT or CST:
- CDT (Mar-Nov): offset is -5, add 5 hours
- CST (Nov-Mar): offset is -6, add 6 hours

Better approach - use MySQL CONVERT_TZ:
```sql
UPDATE clock_times
SET clock_in = CONVERT_TZ(clock_in, 'America/Chicago', '+00:00')
WHERE clock_in IS NOT NULL;
```

### 2.4 Phase 3: Update Queries

**Strategy:** Replace `NOW()` with `UTC_TIMESTAMP()` where comparing with UTC-stored data.

**Files to modify:**

| File | Changes Required |
|------|-----------------|
| `api/dashboard.py` | ~15 instances of NOW() with clock data |
| `calculations/productivity_calculator.py` | 3 instances |
| `integrations/connecteam_sync.py` | 5 instances |
| `connecteam_reconciliation.py` | 1 instance |
| `daily_reconciliation.py` | 3 instances |
| `auto_reconciliation.py` | 2 instances |

**Pattern replacements:**

```sql
-- BEFORE (broken if clock_in is UTC but NOW() is also UTC - actually OK)
-- BEFORE (broken if clock_in is CT but NOW() is UTC)
TIMESTAMPDIFF(MINUTE, clock_in, NOW())

-- AFTER (consistent UTC)
TIMESTAMPDIFF(MINUTE, clock_in, UTC_TIMESTAMP())
```

**Date filtering changes:**

```sql
-- BEFORE
WHERE DATE(clock_in) = CURDATE()

-- AFTER (filter by CT date but data is UTC)
WHERE clock_in >= %s AND clock_in < %s  -- Pass UTC bounds for CT date
```

Already implemented pattern in `utils/timezone_helpers.py`:
```python
utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)
# Then: WHERE clock_in >= utc_start AND clock_in < utc_end
```

### 2.5 Phase 4: Display Layer

**All timestamp outputs must convert UTC -> CT for display.**

Use existing `TimezoneHelper.utc_to_ct()` or `format_for_display()`:

```python
from utils.timezone_helpers import TimezoneHelper
tz_helper = TimezoneHelper()

# For display
clock_in_display = tz_helper.utc_to_ct(record['clock_in']).strftime('%I:%M %p')
```

---

## 3. Files Requiring Changes

### 3.1 Critical Files (Must Change)

| File | Priority | Changes |
|------|----------|---------|
| `backend/integrations/connecteam_client.py` | HIGH | Fix `datetime.fromtimestamp()` to use UTC |
| `backend/integrations/connecteam_sync.py` | HIGH | Verify UTC storage, fix NOW() queries |
| `backend/api/dashboard.py` | HIGH | ~15 NOW() replacements for clock calculations |
| `backend/calculations/productivity_calculator.py` | HIGH | Fix NOW() in active time calculations |

### 3.2 Secondary Files

| File | Priority | Changes |
|------|----------|---------|
| `backend/connecteam_reconciliation.py` | MEDIUM | 1 NOW() fix |
| `backend/daily_reconciliation.py` | MEDIUM | 3 NOW() fixes |
| `backend/auto_reconciliation.py` | MEDIUM | 2 NOW() fixes |
| `backend/auto_employee_mapper.py` | LOW | 1 NOW() fix |

### 3.3 Already Correct (No Changes)

| File | Status |
|------|--------|
| `backend/podfactory_sync.py` | Already stores UTC explicitly |
| `backend/utils/timezone_helpers.py` | Correct implementation |

---

## 4. Detailed Change List

### 4.1 `connecteam_client.py`

**Line 271:** `clock_in = datetime.fromtimestamp(clock_in_timestamp)`
- Change to: `clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc)`

**Line 281:** `clock_out = datetime.fromtimestamp(clock_out_timestamp)`
- Change to: `clock_out = datetime.fromtimestamp(clock_out_timestamp, tz=timezone.utc)`

**Line 303:** `current_time = datetime.now().timestamp()`
- Change to: `current_time = datetime.now(timezone.utc).timestamp()`

**Line 314-315:** Break timestamps
- Apply same UTC conversion

### 4.2 `connecteam_sync.py`

**Line 352:** `SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW())`
- Change to: `SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, UTC_TIMESTAMP())`

**Line 390:** `DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))`
- Already correct (converting NOW to CT for date comparison)

### 4.3 `dashboard.py`

**Line 610:** `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, NOW()))`
- Change to: `TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, UTC_TIMESTAMP()))`

**Line 680, 686:** `COALESCE(MAX(clock_out), NOW())`
- Change to: `COALESCE(MAX(clock_out), UTC_TIMESTAMP())`

**Line 877, 1327:** Already use `UTC_TIMESTAMP()` - CORRECT

**Line 1473, 3485, 3617:** Use `NOW()`
- Change to: `UTC_TIMESTAMP()`

### 4.4 `productivity_calculator.py`

**Line 73:** `COALESCE(clock_out, NOW())`
- Change to: `COALESCE(clock_out, UTC_TIMESTAMP())`

**Line 175:** `datetime.now()` for comparison
- Change to: `datetime.now(pytz.UTC)`

**Line 255:** `COALESCE(clock_out, NOW())`
- Change to: `COALESCE(clock_out, UTC_TIMESTAMP())`

---

## 5. Migration Execution Plan

### Step 1: Backup (Mandatory)
```sql
CREATE TABLE clock_times_backup_20251212 LIKE clock_times;
INSERT INTO clock_times_backup_20251212 SELECT * FROM clock_times;
```

### Step 2: Code Changes
Deploy code changes first but with feature flag disabled.

### Step 3: Data Migration
Run during low-traffic period (before shift start):
```sql
-- Migrate historical data (before today)
UPDATE clock_times
SET
    clock_in = CONVERT_TZ(clock_in, 'America/Chicago', '+00:00'),
    clock_out = CONVERT_TZ(clock_out, 'America/Chicago', '+00:00')
WHERE DATE(clock_in) < CURDATE();
```

### Step 4: Enable New Code
Enable feature flag / deploy updated code.

### Step 5: Verify
```sql
-- Check recent records
SELECT
    id,
    clock_in as utc_stored,
    CONVERT_TZ(clock_in, '+00:00', 'America/Chicago') as ct_display,
    TIMESTAMPDIFF(MINUTE, clock_in, UTC_TIMESTAMP()) as minutes_since_clock_in
FROM clock_times
WHERE clock_out IS NULL
ORDER BY clock_in DESC
LIMIT 5;
```

---

## 6. Pros and Cons

### 6.1 Pros

1. **Consistency** - All timestamps in UTC, no timezone confusion
2. **Correct calculations** - TIMESTAMPDIFF works correctly with same timezone
3. **Industry standard** - UTC storage is best practice
4. **DST handling** - No DST issues in stored data (only at display time)
5. **Existing patterns** - `podfactory_sync.py` and `timezone_helpers.py` already follow this
6. **Future-proof** - Easy to add support for other timezones

### 6.2 Cons

1. **Migration risk** - Historical data must be converted carefully
2. **DST edge cases** - Historical data migration may have DST errors
3. **Code changes** - Many files need updates (~20+ query changes)
4. **Testing burden** - Need comprehensive testing across all date boundaries
5. **Display complexity** - Every display point needs CT conversion
6. **Temporary inconsistency** - During migration, some data may be mixed

### 6.3 Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Data loss | Create backup table before migration |
| Wrong DST conversion | Test with known timestamps from both CDT and CST periods |
| Code bugs | Feature flag for gradual rollout |
| Display errors | Centralize display formatting in `TimezoneHelper` |

---

## 7. Testing Requirements

### 7.1 Unit Tests

- Test `TimezoneHelper.ct_date_to_utc_range()` for DST boundaries
- Test `connecteam_client` returns UTC-aware datetimes
- Test display formatting converts UTC -> CT correctly

### 7.2 Integration Tests

- Verify clock_in/clock_out stored as UTC after sync
- Verify leaderboard shows correct hours
- Verify "currently working" calculation is accurate

### 7.3 Edge Cases

- Clock in at 11 PM CT (next day UTC)
- Clock out during DST transition
- Shift spanning midnight CT
- Employee who clocked in yesterday still working

---

## 8. Rollback Plan

### 8.1 Code Rollback
Revert git commits.

### 8.2 Data Rollback
```sql
-- Restore from backup
TRUNCATE TABLE clock_times;
INSERT INTO clock_times SELECT * FROM clock_times_backup_20251212;
```

---

## 9. Unresolved Questions

1. **Historical data accuracy** - Is existing clock_times data definitively in CT or UTC? The audit script claims UTC but problem description says CT.

2. **Server timezone** - What is the production server's system timezone? This affects `datetime.fromtimestamp()` behavior.

3. **Break times** - Are break timestamps in `break_entries` table also affected?

4. **Cache data** - Does Redis cache contain any timezone-sensitive data that needs clearing?

5. **Reports** - Are there any historical reports or exports that assume CT storage?

---

## 10. Summary

**Recommendation:** Proceed with UTC migration approach.

**Timeline estimate:**
- Code changes: 2-3 hours
- Testing: 2-4 hours
- Data migration: 30 minutes (with downtime)
- Verification: 1 hour

**Total effort:** ~6-8 hours

**File path:** `C:\Users\12104\Projects\Productivity_system\plans\20251212-0745-utc-timezone-migration\PLAN.md`
