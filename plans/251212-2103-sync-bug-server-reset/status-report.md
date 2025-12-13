# Status Report: Sync Bug Investigation

**Date**: 2025-12-12 21:03 CT
**Status**: Documentation Complete

---

## Summary

| Item | Status |
|------|--------|
| Bug Identified | YES - `connecteam_sync.py` lines 325-332 |
| Root Cause | Sync SKIPS instead of CORRECTING 6hr offset |
| Server Investigated | YES - PM2 running buggy code |
| Docs Updated | YES |
| Code Fixed | NO - Pending |
| Deployed | NO - Pending |

---

## Documents Created/Updated

### 1. Plan Document
**Path**: `plans/251212-2103-sync-bug-server-reset/plan.md`
- Full investigation details
- Bug analysis
- Server state
- Fix plan
- Commands reference

### 2. CHANGELOG
**Path**: `docs/CHANGELOG.md`
- Added v2.3.7 (PENDING) entry
- Documented sync bug discovery
- Listed data quality issues

### 3. Data Quality Issues
**Path**: `docs/data-quality-issues.md`
- Issue #6: Connecteam Sync 6-Hour Offset Bug
- Issue #7: Server Sync Running Buggy Code
- Data audit table (Dec 1-11)
- Resolution plan

---

## Bug Location

```
File: backend/integrations/connecteam_sync.py
Function: _sync_clock_time()
Lines: 325-332
```

### Problem Code
```python
if is_tz_shifted and not is_same_shift:
    logger.warning("Detected timezone-shifted duplicate...")
    return True  # BUG: Skips without correcting
```

### Required Fix
```python
if is_tz_shifted and not is_same_shift:
    logger.warning("Correcting timezone-shifted record...")
    # UPDATE existing record with correct UTC time
    cursor.execute("UPDATE clock_times SET clock_in=?, clock_out=?, duration_minutes=? WHERE id=?", ...)
    return True
```

---

## Next Actions

1. [ ] Fix sync code locally
2. [ ] Test fix
3. [ ] Write cleanup script for duplicates
4. [ ] Push to GitHub
5. [ ] Deploy to server
6. [ ] Verify data integrity

---

## Quick Reference

### SSH to Server
```bash
ssh root@134.199.194.237
```

### PM2 Commands
```bash
pm2 stop podfactory-sync
pm2 restart podfactory-sync
pm2 logs podfactory-sync
```

### Git Deploy
```bash
cd /var/www/productivity-system
git pull origin main
pm2 restart all
```
