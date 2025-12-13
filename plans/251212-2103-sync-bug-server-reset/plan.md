# Connecteam Sync Bug & Server Reset Plan

**Created**: 2025-12-12 21:03 CT
**Status**: Investigation Complete, Ready for Fix
**Priority**: HIGH - Data integrity issue

---

## Executive Summary

Discovered critical bug in Connecteam sync code causing 6-hour timezone offset in stored clock times. Server is running buggy code. Database has duplicate records (old shifted + new correct). Need to fix code, redeploy, and clean data.

---

## 1. Problem Discovery

### Timeline
| Date | Event |
|------|-------|
| Dec 1-9 | clock_times > daily_scores (341-4508 min mismatches) |
| Dec 10-11 | Perfect match after recent fixes |
| Dec 12 | User reported frontend data looks wrong for Dec 2 |

### Dec 2 Data Audit Results
- **Connecteam API**: 52 shifts, 15,979 minutes
- **Database**: 31 records, 9,858 minutes
- **Gap**: 10 employees MISSING = 6,121 minutes

### Root Cause
1. Connecteam sync wasn't running properly before Dec 4
2. When manual sync attempted, got "timezone-shifted duplicate" messages
3. Existing records stored with **6-hour offset** (UTC vs CT bug)

---

## 2. Bug Analysis

### Location
**File**: `backend/integrations/connecteam_sync.py`
**Function**: `_sync_clock_time()` (lines 325-332)

### Buggy Code
```python
# Check for exact match OR 6-hour offset (UTC vs CT timezone bug)
is_same_shift = seconds_diff < 300  # Within 5 minutes
is_tz_shifted = abs(seconds_diff - 21600) < 300  # 6 hours ± 5 min

if is_same_shift or is_tz_shifted:
    if is_tz_shifted and not is_same_shift:
        logger.warning(f"Detected timezone-shifted duplicate for employee {employee_id} "
                      f"(6hr offset detected, using existing record ID {existing['id']})")
    # Update only if needed - BUT SKIPS INSERTING CORRECT RECORD!
    return True  # <-- BUG: Returns without correcting the shifted record
```

### Problem
- Code **DETECTS** 6hr offset correctly
- But then **SKIPS** instead of **CORRECTING**
- Logs warning but takes no corrective action
- New correct records never inserted

---

## 3. Current Server State

### Server Info
- **IP**: 134.199.194.237
- **Domain**: reports.podgasus.com (via Cloudflare tunnel)
- **Git Remote**: github.com/nguyentranus1989/productivity-system.git

### Running Services (PM2)
| Process | Status | Uptime |
|---------|--------|--------|
| cloudflare-tunnel | online | ~15 days |
| podfactory-sync | online | ~15 days |
| flask-backend | stopped | - |

### Key Paths
- Project: `/var/www/productivity-system/`
- Backend: `/var/www/productivity-system/backend/`
- Nginx config: `/etc/nginx/sites-available/reports-podgasus`

### Current Sync Process
- **Process**: `podfactory-sync`
- **Command**: `sync_wrapper.py continuous`
- **Status**: RUNNING with BUGGY code

---

## 4. Database State

### Connection
- **Host**: db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com
- **Port**: 25060
- **Database**: productivity_tracker

### Data Quality Issues
| Issue | Status |
|-------|--------|
| Missing Dec 2 shifts | Manually backfilled 16 records |
| 6hr offset duplicates | NOT cleaned up |
| Dec 1-9 mismatches | Needs investigation |

---

## 5. Fix Plan

### Phase 1: Fix Sync Code (Local)
1. Modify `_sync_clock_time()` to UPDATE shifted records instead of skip
2. Add logic to correct 6hr offset when detected
3. Test locally

### Phase 2: Clean Database
1. Identify all records with 6hr offset
2. Delete duplicates (keep correct times)
3. Verify data integrity

### Phase 3: Deploy to Server
1. Stop `podfactory-sync` on server
2. Git pull latest code
3. Restart services
4. Verify sync working correctly

### Phase 4: Verify
1. Run manual sync
2. Check for new "timezone-shifted" warnings
3. Compare Connecteam API vs DB counts

---

## 6. Code Fix Required

### Current Behavior (Bug)
```
Detect 6hr offset → Log warning → SKIP → Return True
```

### Required Behavior (Fix)
```
Detect 6hr offset → UPDATE existing record with correct time → Return True
```

### Proposed Fix
```python
if is_tz_shifted and not is_same_shift:
    logger.warning(f"Correcting timezone-shifted record for employee {employee_id}")
    # UPDATE the existing record with correct UTC time
    cursor.execute("""
        UPDATE clock_times
        SET clock_in = %s, clock_out = %s, duration_minutes = %s
        WHERE id = %s
    """, (clock_in_utc, clock_out_utc, duration_minutes, existing['id']))
    return True
```

---

## 7. Files Inventory

### Local Files (Need Fix)
| File | Size | Status |
|------|------|--------|
| `backend/integrations/connecteam_sync.py` | 36KB | Contains bug |
| `backend/app.py` | Modified | OK |
| `backend/config.py` | Read | OK |

### Server Files (Running Buggy Code)
| File | Location |
|------|----------|
| `sync_wrapper.py` | `/var/www/productivity-system/backend/` |
| `connecteam_sync.py` | `/var/www/productivity-system/backend/integrations/` |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during cleanup | Medium | High | Backup before delete |
| Sync interruption | Low | Medium | Brief downtime acceptable |
| New bugs in fix | Low | High | Test locally first |

---

## 9. Next Steps

1. [ ] Fix `connecteam_sync.py` locally
2. [ ] Test fix with sample data
3. [ ] Write cleanup script for duplicates
4. [ ] Push to GitHub
5. [ ] SSH to server and deploy
6. [ ] Verify data integrity

---

## Appendix: Commands Reference

### SSH to Server
```bash
ssh root@134.199.194.237
```

### PM2 Commands (on server)
```bash
pm2 list                    # Show all processes
pm2 stop podfactory-sync    # Stop sync
pm2 restart podfactory-sync # Restart sync
pm2 logs podfactory-sync    # View logs
```

### Git Deploy (on server)
```bash
cd /var/www/productivity-system
git pull origin main
pm2 restart all
```
