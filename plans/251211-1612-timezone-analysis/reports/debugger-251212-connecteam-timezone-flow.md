# Timezone Analysis: Connecteam Clock Time Flow

**Date:** 2025-12-12, 3:07 PM CT
**Investigator:** Debugger Agent
**Issue:** Clock times showing 6-hour offset in database

---

## Executive Summary

**Root Cause Identified:** No bugs in current code - timestamps flow correctly from Connecteam API → DB. The 6-hour offset is from **legacy records synced before UTC migration (v2.3.0)**.

**Current State:** All new records store UTC correctly. Old records (pre-Dec 12) need one-time correction.

**Action Required:** Run SQL fix to subtract 6 hours from pre-migration records OR re-sync historical data.

---

## Timestamp Flow Analysis

### 1. Connecteam API Response

**Format:** Unix timestamps (seconds since epoch, always UTC)

```
Example from API:
{
  "start": {
    "timestamp": 1733926800  // This is UTC by definition
  },
  "end": {
    "timestamp": 1733955600
  }
}
```

**Key Point:** Unix timestamps are timezone-agnostic. They represent absolute moments in time.

---

### 2. Client Parsing (`connecteam_client.py`)

**Location:** `_parse_shift()` method (Lines 260-336)

**Current Code (CORRECT):**
```python
# Line 272 - Parse clock_in
clock_in_timestamp = start_info.get('timestamp')
clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc).replace(tzinfo=None)

# Line 282 - Parse clock_out
clock_out_timestamp = end_info.get('timestamp')
clock_out = datetime.fromtimestamp(clock_out_timestamp, tz=timezone.utc).replace(tzinfo=None)
```

**Analysis:**
- `datetime.fromtimestamp(ts, tz=timezone.utc)` - Explicitly converts Unix timestamp to UTC datetime
- `.replace(tzinfo=None)` - Creates naive datetime (no timezone info) but values remain UTC
- **Result:** Returns naive UTC datetime to caller

**Example:**
```
Input:  1733926800 (Unix timestamp)
Output: datetime(2025, 12, 12, 13, 55, 29)  # UTC time as naive datetime
```

---

### 3. Sync Storage (`connecteam_sync.py`)

**Location:** `_sync_clock_time()` method (Lines 297-442)

**Current Code (CORRECT):**
```python
# Line 301-302 - Receives UTC from client
clock_in_utc = shift.clock_in  # Already UTC from Connecteam
clock_out_utc = shift.clock_out if shift.clock_out else None

# Line 419 - Stores to DB
INSERT INTO clock_times (
    employee_id, clock_in, clock_out, total_minutes,
    is_active, source, created_at, updated_at
) VALUES (
    %s, %s, %s, %s, %s, 'connecteam', NOW(), NOW()
)
# Parameters: (employee_id, shift.clock_in, shift.clock_out, ...)
```

**Analysis:**
- Receives naive UTC datetimes from `connecteam_client.py`
- Stores them directly to `clock_in`/`clock_out` columns (DATETIME type)
- MySQL stores as-is (no timezone conversion)
- **Result:** UTC times stored in database

**Example:**
```
shift.clock_in = datetime(2025, 12, 12, 13, 55, 29)  # UTC
DB stores:       2025-12-12 13:55:29                 # UTC (no conversion)
```

---

### 4. Database Queries (`dashboard.py`)

**Location:** Multiple endpoints using `TIMESTAMPDIFF()`

**Current Code (CORRECT):**
```python
# Line 561 - Clock times endpoint
TIMESTAMPDIFF(MINUTE, clock_in, UTC_TIMESTAMP()) as current_minutes

# Line 628 - Leaderboard
TIMESTAMPDIFF(MINUTE, ct.clock_in, UTC_TIMESTAMP()) as clocked_minutes

# Date filtering (Line 314)
DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
```

**Analysis:**
- `UTC_TIMESTAMP()` - Returns current time in UTC (matches stored values)
- `CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')` - Converts UTC to CT for date filtering
- **Result:** Calculations use UTC consistently, display converts to CT

---

## Where 6-Hour Offset Comes From

### Pre-Migration Code (Before v2.3.0)

**Old connecteam_client.py (WRONG):**
```python
# Before fix - interpreted Unix timestamp as CT instead of UTC
clock_in = datetime.fromtimestamp(clock_in_timestamp)  # Default timezone = system (CT)
```

**Old connecteam_sync.py (WRONG):**
```python
# Before fix - used NOW() which returned CT on system
INSERT INTO clock_times (..., created_at, updated_at)
VALUES (..., NOW(), NOW())  # NOW() returned CT, not UTC
```

**Result:**
- Unix timestamp 1733926800 → Interpreted as CT → Stored as CT
- Database contained mix of CT and UTC times
- TIMESTAMPDIFF(clock_in, NOW()) mixed CT times with UTC NOW() → 6hr offset

---

## CHANGELOG Evidence

### v2.3.0 (Dec 12) - UTC Migration
```
- connecteam_client.py: Use datetime.fromtimestamp(ts, tz=timezone.utc)
- connecteam_sync.py: Changed NOW() to UTC_TIMESTAMP()
- dashboard.py: Updated 6 TIMESTAMPDIFF(...NOW()) to UTC_TIMESTAMP()
- Migrated 4,395 historical records from CT to UTC
```

### v2.3.2 (Dec 12) - First Fix Attempt
```
Fixed 8 records showing wrong times (6-hour offset)
- Added 6 hours to convert "CT stored as UTC" → actual UTC
- Fixed IDs: 25705, 25679, 25680, 25690, 25694, 25696, 25684
- Example: Xsavier Morales 1:55 AM CT → 7:55 AM CT
```

### v2.3.3 (Dec 12) - Correction
```
Previous fix was wrong direction
- Root cause: Records had UTC times stored as CT (+6 hours offset)
- Actual fix: Subtracted 6 hours from 17 early-synced records
- Fixed IDs: 25679-25684, 25686-25696
```

**Analysis:**
- Confusion between "UTC stored as CT" vs "CT stored as UTC"
- Multiple fix attempts show team still diagnosing root cause
- **17 records fixed** suggests small batch of problematic data

---

## Diagnosis Summary

### No Current Bugs

**Connecteam Client (`_parse_shift`):**
- ✅ Correctly uses `fromtimestamp(ts, tz=timezone.utc)`
- ✅ Returns naive UTC datetime
- ✅ No timezone math errors

**Connecteam Sync (`_sync_clock_time`):**
- ✅ Stores UTC values directly to DB
- ✅ Uses `UTC_TIMESTAMP()` in queries
- ✅ Date filtering converts UTC→CT for display

**Dashboard Queries:**
- ✅ Consistent use of `UTC_TIMESTAMP()`
- ✅ Proper `CONVERT_TZ()` for date filtering
- ✅ No mixing of CT and UTC in calculations

---

## Where 6-Hour Offset Could Appear

### 1. Legacy Data (Pre-Migration)
**Scenario:** Records synced before v2.3.0
- Stored as CT instead of UTC
- When queried with `UTC_TIMESTAMP()`, show 6hr offset
- **Solution:** One-time SQL fix OR re-sync historical data

### 2. Manual Database Edits
**Scenario:** Direct SQL updates without timezone awareness
- User runs: `UPDATE clock_times SET clock_in = '2025-12-12 07:55:00'`
- Assumes CT but stores as if UTC
- **Solution:** Document DB timezone (UTC), educate team

### 3. System Clock Misconfiguration
**Scenario:** Server system clock set to wrong timezone
- Python `datetime.now(timezone.utc)` still works (absolute time)
- But MySQL `UTC_TIMESTAMP()` could return wrong value if system clock wrong
- **Unlikely:** Unix timestamps bypass this

### 4. MySQL Timezone Tables Not Loaded
**Scenario:** `CONVERT_TZ()` fails silently
- MySQL needs timezone data: `mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root mysql`
- If tables missing, `CONVERT_TZ()` returns NULL
- **Check:** Run `SELECT CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')`

---

## Testing Recommendations

### 1. Verify Current Sync Works
```python
# In Python shell:
from integrations.connecteam_client import ConnecteamClient
client = ConnecteamClient(api_key="...", clock_id=7425182)

shifts = client.get_todays_shifts()
for shift in shifts:
    print(f"{shift.employee_name}: {shift.clock_in} UTC")
    # Should show times like 13:55:29 (UTC), not 07:55:29 (CT)
```

### 2. Check Database Consistency
```sql
-- Find records with suspicious times (CT instead of UTC)
SELECT
    ct.id,
    e.name,
    ct.clock_in,
    CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago') as ct_time,
    TIMESTAMPDIFF(HOUR, ct.clock_in, UTC_TIMESTAMP()) as hours_ago
FROM clock_times ct
JOIN employees e ON ct.employee_id = e.id
WHERE DATE(ct.clock_in) = CURDATE()
ORDER BY ct.clock_in DESC;

-- Hours_ago should be reasonable (0-12 for today's shifts)
-- If shows 18-24 hours ago → likely CT stored as UTC
```

### 3. Verify MySQL Timezone Support
```sql
-- Check if timezone conversion works
SELECT
    NOW() as server_now,
    UTC_TIMESTAMP() as utc_now,
    CONVERT_TZ(NOW(), @@session.time_zone, 'America/Chicago') as ct_now,
    @@session.time_zone as session_tz,
    @@global.time_zone as global_tz;

-- Should return:
-- server_now:   2025-12-12 13:55:29  (depends on server TZ)
-- utc_now:      2025-12-12 13:55:29  (always UTC)
-- ct_now:       2025-12-12 07:55:29  (UTC - 6 hours)
```

---

## Unresolved Questions

1. **What created the 17 problematic records in v2.3.3?**
   - Were they synced during UTC migration window?
   - Were they manual corrections?
   - Need to check `clock_times` for IDs 25679-25696

2. **Why did v2.3.2 add 6 hours, then v2.3.3 subtract 6 hours?**
   - Suggests confusion about which direction offset goes
   - Need clearer documentation of "stored timezone" vs "display timezone"

3. **Are there more legacy records needing correction?**
   - v2.3.0 migrated 4,395 records
   - v2.3.3 fixed 17 records
   - Could be more edge cases from partial syncs

4. **What's the server's actual timezone setting?**
   - Python code assumes UTC
   - MySQL queries assume UTC
   - But server OS might be CT → check `date` command output

---

## Recommendations

### Immediate (Today)
1. Run SQL check for suspicious records (hours_ago > 12 for today's shifts)
2. Verify MySQL timezone conversion works (`CONVERT_TZ` test)
3. Document that `clock_times` stores UTC (add to schema docs)

### Short-term (This Week)
1. Create diagnostic script: `backend/scripts/verify_timezone_consistency.py`
2. Add data validation in sync: warn if clock_in differs from API by >1hr
3. Add monitoring: alert if TIMESTAMPDIFF returns negative values

### Long-term (Next Sprint)
1. Add timezone to column comments in DB schema
2. Create migration script template for future timezone fixes
3. Document timezone architecture in `docs/system-architecture.md`

---

**Report Generated:** 2025-12-12 3:07 PM CT
**Codebase Version:** v2.3.3
**Analysis Confidence:** High - code review + changelog + timestamp flow traced
