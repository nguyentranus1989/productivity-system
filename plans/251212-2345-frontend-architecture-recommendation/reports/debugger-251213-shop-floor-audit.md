# Shop Floor Display - Bug Audit Report
**Date**: 2025-12-13
**File**: `frontend/shop-floor.html`
**Auditor**: Claude Debugger Agent
**Reference Issues**: Timezone bugs, race conditions, date parsing from manager.html

---

## Executive Summary

Audited `shop-floor.html` for similar bugs found/fixed in `manager.html`. **Good news**: Most critical bugs DON'T exist in shop-floor.html because it uses shared `dashboard-api.js` which handles timezone correctly.

**Status**: ✅ CLEAN - No critical bugs found
**Recommendation**: No immediate fixes required

---

## Issues Analyzed

### ❌ 1. Hardcoded Timezone Offsets
**Status**: NOT PRESENT ✅

**Analysis**:
- shop-floor.html (line 1343) uses `this.api.getCurrentCentralTime()` from dashboard-api.js
- dashboard-api.js (line 126-129) uses proper `Intl` API:
  ```javascript
  getCurrentCentralTime() {
      const now = new Date();
      return new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));
  }
  ```
- This correctly auto-detects CST/CDT based on system locale
- No hardcoded UTC-5 or UTC-6 offsets

**Evidence**:
- Line 1343: `const now = this.api.getCurrentCentralTime();`
- Line 1721: `const now = this.api.getCurrentCentralTime();`

---

### ❌ 2. Race Conditions in API Calls
**Status**: MINOR RISK ⚠️

**Analysis**:
- shop-floor.html uses flag-based protection: `isUpdating` (line 1282, 1384-1385)
- Prevents overlapping refreshes with guard clause:
  ```javascript
  if (this.isUpdating) return;
  this.isUpdating = true;
  ```
- Uses `Promise.allSettled` instead of `Promise.all` (line 1389) - safer pattern
- **HOWEVER**: No request ID tracking like manager.html's fix
- Theoretical risk: slow API response returns after newer one, overwrites fresh data

**Evidence**:
- Line 1384-1386: Guard clause prevents overlapping calls
- Line 1389: `Promise.allSettled` handles partial failures gracefully

**Risk Level**: LOW - unlikely in 30s refresh interval

---

### ❌ 3. Date Parsing Issues
**Status**: NOT PRESENT ✅

**Analysis**:
- No manual date string construction like `new Date('2025-12-01')`
- Uses API methods that return proper Date objects
- Clock display (line 1343-1357) uses direct `toLocaleDateString/toLocaleTimeString`
- Midnight refresh (line 1721-1724) uses proper Date object manipulation:
  ```javascript
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(0, 0, 5, 0);
  ```

**Evidence**:
- Line 1721-1724: Proper date math, no string parsing
- Line 1343-1357: Uses Date methods, not string construction

---

### ❌ 4. Cache Issues
**Status**: NOT APPLICABLE N/A

**Analysis**:
- shop-floor.html is display-only (no recalculation triggers)
- No cache clearing needed since no user actions trigger backend recalc
- Auto-refresh every 30s (line 1286) keeps data fresh

---

## Additional Observations

### ✅ Strengths
1. **Shared API layer**: Using `dashboard-api.js` ensures consistency
2. **Proper timezone handling**: Intl API throughout
3. **Error resilience**: `Promise.allSettled` prevents cascade failures
4. **Auto-recovery**: Window focus listener (line 1714-1717) refreshes on tab return

### ⚠️ Minor Improvements Possible
1. **Request ID tracking**: Add like manager.html to guarantee fresh data
2. **Stale data indicator**: Show warning if API calls fail repeatedly
3. **Error state**: Better UX for network failures (currently just logs)

---

## Comparison with manager.html Fixes

| Issue | manager.html | shop-floor.html | Status |
|-------|-------------|-----------------|--------|
| Hardcoded timezone | ❌ Fixed (UTC-5→Intl) | ✅ Never existed | OK |
| Race conditions | ❌ Fixed (request IDs) | ⚠️ Flag-based | Minor risk |
| Date parsing | ❌ Fixed (T12:00:00) | ✅ No string parsing | OK |
| Cache clearing | ❌ Fixed (invalidation) | N/A Display-only | OK |

---

## Recommendations

### Priority: LOW
**No urgent fixes required**

### Optional Enhancements
1. **Add request ID tracking** (like manager.html lines 2935-2937):
   ```javascript
   const requestId = Date.now();
   this.lastRequestId = requestId;
   // Later: if (requestId !== this.lastRequestId) return;
   ```

2. **Add offline detection**:
   ```javascript
   if (!navigator.onLine) {
       this.showError('No network connection');
       return;
   }
   ```

3. **Add stale data warning** if last successful update >2 minutes

---

## Unresolved Questions
1. How often do 30s API calls actually overlap in production?
2. Should we add request ID tracking preemptively or wait for issue?
3. Is 30s refresh too aggressive for shop floor TV display?

---

## Conclusion

shop-floor.html is **production-ready** with no critical bugs. Benefits from shared API layer that already has proper timezone handling. Minor race condition risk exists but unlikely to manifest with 30s refresh interval.

**Action Required**: None (monitoring recommended)
