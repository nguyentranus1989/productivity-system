# Employee Mapping Workflow - Simplification Analysis

**Date:** 2025-12-10
**Status:** Analysis & Recommendation
**Complexity:** Medium
**Impact:** High - affects data sync accuracy

---

## Problem Statement

Current employee mapping between Connecteam and PodFactory is overcomplicated and creates confusion:

1. **Connecteam sync** creates employees with `connecteam_user_id`
2. **PodFactory sync** uses NAME matching (not email) and stores `employee_id` in `activity_logs`
3. **`employee_podfactory_mapping_v2` table** exists but sync doesn't use it
4. **UI shows "No PodFactory Mapping"** for employees without mapping records
5. **Modal auto-generates emails** like `{firstname}.{lastname}shp@colorecommerce.us` that may not exist

**Root Issue:** The mapping table is disconnected from sync logic, and UI suggests non-existent emails.

---

## Current Architecture Analysis

### What Works
- **Connecteam sync** (`backend/integrations/connecteam_sync.py`):
  - Creates/updates employees with `connecteam_user_id`
  - Syncs shifts to `clock_times` table
  - Simple and reliable

### What's Broken
- **PodFactory sync** (`backend/podfactory_sync.py`):
  - Uses `get_employee_mapping()` for name-based matching (lines 101-171)
  - Ignores `employee_podfactory_mapping_v2` table completely
  - Creates complex name variations (normalized, with dots, underscores)
  - Has manual mappings hardcoded (lines 153-158)
  - Auto-creates employees via `EmployeeAutoCreator`

- **Mapping Table** (`employee_podfactory_mapping_v2`):
  - Schema includes: `employee_id`, `podfactory_email`, `podfactory_name`, `similarity_score`, `confidence_level`, `is_verified`
  - Used by UI to display mapped emails
  - Used by `auto_employee_mapper.py` for confident mappings
  - **NOT used by actual sync process**

- **UI** (`frontend/manager.html` line 3112+):
  - `mapEmployee()` function shows modal with unmapped users
  - Lists actual PodFactory emails from `/api/dashboard/unmapped-users`
  - But doesn't show suggestions from real PodFactory data

---

## Recommendation: Simplify & Fix

### Option A: Use Mapping Table (Recommended)
**Why:** Mapping table should be source of truth, not redundant metadata.

**Changes:**
1. **Modify PodFactory sync** to use `employee_podfactory_mapping_v2`:
   ```python
   # Instead of name-based matching in get_employee_mapping()
   # Query: SELECT employee_id, podfactory_email FROM employee_podfactory_mapping_v2 WHERE is_verified = 1
   # Match activity_logs.user_email against this table
   ```

2. **Add endpoint** `/api/dashboard/podfactory-emails/suggestions`:
   - Query real PodFactory DB for active emails (last 30 days)
   - Return distinct `user_email` + `user_name` from `pod-report-stag.report_actions`
   - Use for autocomplete/suggestions in mapping modal

3. **Update UI** to show real suggestions:
   - Replace auto-generated email pattern
   - Show dropdown with actual PodFactory emails
   - Include name from PodFactory for context

4. **Keep auto-creator** for unmapped users but flag them for review

**Pros:**
- Single source of truth (mapping table)
- Real email suggestions from PodFactory
- Verified mappings prevent errors
- Maintains audit trail (similarity_score, confidence_level)

**Cons:**
- Requires initial bulk mapping for existing employees
- More upfront work to populate table

---

### Option B: Remove Mapping Table
**Why:** If sync doesn't use it, why maintain it?

**Changes:**
1. **Drop** `employee_podfactory_mapping_v2` table
2. **Keep** name-based matching in sync
3. **Store** `podfactory_email` directly in `employees` table (new column)
4. **Simplify** UI to just edit employee record

**Pros:**
- Simpler schema
- One less table to maintain
- Faster queries

**Cons:**
- Loses multi-email support per employee
- Loses audit trail (confidence levels, similarity scores)
- Harder to track mapping quality
- Name matching is unreliable (nicknames, typos)

---

### Option C: Hybrid Approach
**Why:** Use mapping table for verification, name matching as fallback.

**Changes:**
1. **Primary**: Check `employee_podfactory_mapping_v2` first
2. **Fallback**: Use name matching if no verified mapping
3. **Auto-flag**: Create pending mapping records for name matches (confidence: 'low')
4. **Admin review**: Show pending mappings in UI for approval

**Pros:**
- Best of both worlds
- Gradual migration path
- Catches new employees automatically

**Cons:**
- Most complex to implement
- Two code paths to maintain

---

## Final Recommendation: **Option A**

**Rationale:**
1. Mapping table already exists with proper schema
2. Email-based matching is more reliable than name matching
3. Real PodFactory emails eliminate guesswork
4. Audit trail helps troubleshoot issues
5. Verified flag prevents bad mappings

**Implementation Priority:**
1. Add `/api/dashboard/podfactory-emails/suggestions` endpoint
2. Update UI modal to show real suggestions
3. Modify `podfactory_sync.py` to query mapping table
4. Keep name-based fallback for backwards compatibility
5. Run bulk mapping script for existing employees
6. Remove hardcoded manual mappings

---

## Migration Strategy

### Phase 1: Add Real Suggestions (Week 1)
- Create endpoint to fetch real PodFactory emails
- Update UI to show suggestions instead of auto-generated
- No breaking changes to sync

### Phase 2: Populate Mappings (Week 2)
- Run script to create mapping records for existing name matches
- Mark high-confidence matches as verified
- Flag low-confidence for manual review

### Phase 3: Switch Sync Logic (Week 3)
- Update `get_employee_mapping()` to query mapping table
- Keep name fallback for unmapped users
- Test thoroughly with production data

### Phase 4: Cleanup (Week 4)
- Remove hardcoded manual mappings
- Archive old name-matching logic
- Document new workflow

---

## Questions for User

1. **How many employees need mapping?** (affects migration effort)
2. **Can employees have multiple PodFactory emails?** (impacts schema decision)
3. **Who manages mappings?** (determines UI complexity)
4. **How often do new employees start?** (affects auto-mapping priority)
5. **Are PodFactory emails stable?** (or do they change frequently?)

---

## Success Metrics

- Zero "No PodFactory Mapping" employees after migration
- 100% sync success rate for mapped employees
- Mapping suggestions match actual PodFactory data
- Admin can verify mappings in <30 seconds per employee

---

## Risk Assessment

**Low Risk:**
- Adding suggestion endpoint (read-only)
- UI improvements

**Medium Risk:**
- Changing sync logic (test extensively)
- Bulk mapping script (need rollback plan)

**High Risk:**
- None (can rollback at each phase)
