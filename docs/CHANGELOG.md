# Changelog

All notable changes to the Productivity Tracker system.

## [2.3.9] - 2025-12-12

### Enhanced - Dashboard Date Range View
- **New Summary Cards**: Redesigned date range view with meaningful aggregations
  - Avg employees/day / Total employees (who clocked in)
  - Avg QC items/day / Total QC Passed items (excludes other activity types)
  - Avg efficiency across range (total active / total clocked minutes)
  - Days in range count
- **Removed Live Overlay**: Date range view no longer shows live data indicators
- **QC Passed Items Only**: Summary now filters to `activity_type = 'QC Passed'` from activity_logs
  - Previously included all types: In Production, QC Passed, Picking, Labeling, Film Matching

### Fixed
- **JavaScript Error**: Fixed `totalItems is not defined` at line 4854
  - Changed to `summary.total_items` reference
  - Employee details table now renders correctly

### Technical Details
- `backend/api/dashboard.py`: Added `qc_items_query` for QC Passed filtering
- `frontend/manager.html`: Updated `updateDateRangeView()` with new card layouts

---

## [2.3.8] - 2025-12-12

### Fixed - Recalculation & Cache Issues
- **daily_cost_summary in Calculate All**: Added as 7th stage in recalculation job
  - Previously "Calculate All" didn't recalculate cost summary table
  - Now all 7 stages: clock_times → daily_scores (4 fields) → cost_summary → status view
- **Cache Invalidation**: Dashboard cache now cleared after recalculation completes
  - Added `clear_dashboard_cache()` function to `dashboard.py`
  - Called automatically after successful recalculation
- **Race Condition Fix**: Cost Analysis stale response prevention
  - Added request tracking (`costAnalysisRequestId`) to ignore superseded responses
  - Prevents older async responses from overwriting newer data
- **Date Display Timezone Fix**: Fixed JavaScript UTC parsing issue
  - `new Date('2025-12-01')` parsed as midnight UTC → showed Nov 30 in CT
  - Fixed by using `new Date('2025-12-01T12:00:00')` to parse as noon local time

### Technical Details
- `backend/api/system_control.py`: Added `daily_cost_summary` stage + cache clear
- `backend/api/dashboard.py`: Added `clear_dashboard_cache()` export
- `frontend/manager.html`: Request tracking + `T12:00:00` date parsing fix

---

## [2.3.7] - 2025-12-12

### Fixed - Connecteam Sync Bug
- **Root Cause**: `connecteam_sync.py` detected 6hr timezone offset but SKIPPED instead of CORRECTING
- **Impact**: Dec 1-9 data had mismatches between clock_times and daily_scores
- **Location**: `_sync_clock_time()` lines 329-362
- **Fix**: Now UPDATES existing shifted records with correct UTC times
- **Status**: DEPLOYED to server (commit 941114c)

### Fixed - Batch Sync Performance
- **New v2 sync methods**: Batch fetch + exact clock_in matching
- **Performance**: 500 shifts now sync in ~30 seconds (was O(n) queries)
- **Data Integrity**: Unique constraint on `(employee_id, clock_in)` prevents duplicates
- Re-synced Dec 1-11: 585 records created correctly

### Data Quality Issues Found
- Dec 2: Connecteam API had 52 shifts, DB only had 31 (10 employees missing)
- Manually backfilled 16 shifts for Dec 2
- Cleaned duplicate records after fix

---

## [2.3.6] - 2025-12-12

### Performance
- **Pre-calculated Daily Cost Summary**: Dramatically faster Cost Analysis for historical queries
  - Created `daily_cost_summary` table for pre-aggregated daily cost data
  - Historical queries (not including today) now use pre-calculated data
  - **Before**: 15-17 seconds for 12-day range (real-time calculation)
  - **After**: 6-7 seconds for 11-day historical range (2.3x faster)
  - Today's data still calculated real-time for live accuracy
  - API response includes `source: "pre-calculated"` for debugging

### Added
- **End-of-day Cost Summary Job**: Scheduler runs at 6:15 PM CT
  - Automatically calculates daily cost summary after workday ends
  - Runs after daily score finalization (6:00 PM)
- **Cost Summary API Endpoints**:
  - `POST /api/system/cost-summary/calculate` - Backfill historical data
  - `GET /api/system/cost-summary/status` - Check summary coverage

### Technical Details
- `daily_cost_summary` table: employee_id, clocked_hours, active_hours, costs, activity breakdown
- `backend/api/system_control.py`: Added `calculate_daily_cost_summary()` function
- `backend/api/dashboard.py`: Added `get_cost_analysis_from_summary()` helper
- `backend/app.py`: Added scheduler job for daily calculation
- Backfilled 398 records for Dec 1-12

---

## [2.3.5] - 2025-12-12

### Added
- **Data Recalculation UI**: System Controls → Data Maintenance
  - Date range picker with estimate before running
  - Real-time progress bar with stage indicators
  - Per-stage timing and record counts in results
  - 6-stage pipeline: clock_times → clocked_minutes → active_minutes → idle_periods → items_processed → efficiency_rate

### Fixed
- **Cost Analysis Utilization Bug**: Was showing 8000%+ instead of correct 2-20%
  - **Root Cause**: Used `efficiency_rate * 100` (items/min × 100) instead of actual utilization
  - **Fix**: Changed to `(active_minutes / clocked_minutes) * 100`
  - **Example**: Hoang Duong showed 8391% → now shows 2.7% (correct)

- **Console Error**: Removed dead `pendingBadge` code throwing null reference errors
  - Element never existed in DOM, code was orphaned

### Performance
- **Cost Analysis Query Optimization**: Changed clock_times filter to use UTC range
  - **Before**: `WHERE DATE(CONVERT_TZ(clock_in...))` - full table scan (4494 rows)
  - **After**: `WHERE clock_in >= ? AND clock_in < ?` - index range scan (800 rows for 1 month)
  - **Impact**: 5-6x fewer rows scanned, scales better with data growth

### Technical Details
- `backend/api/system_control.py`: Added recalculation endpoints with timing
- `backend/api/dashboard.py`: Fixed utilization formula, optimized clock_times filter
- `frontend/manager.html`: Added recalculation modal, removed dead badge code

---

## [2.3.4] - 2025-12-12

### Fixed
- **Clock Times Complete Resync**: Deleted and resynced all Dec 12 clock_times
  - **Root Cause**: Mix of pre-fix and post-fix records with inconsistent timezone handling
  - **Solution**: Clean slate - deleted 52 records, resynced 55 from Connecteam
  - **Verification**: User confirmed correct times:
    - Toan Chau: 4:45 AM CT ✓
    - Man Nguyen: 2:06 AM CT ✓
    - Andrea Romero: 5:09 AM CT ✓

- **Daily Scores Stale Data**: Fixed `active_minutes` showing impossible values
  - **Root Cause**: `daily_scores.active_minutes` not synced with `activity_logs`
  - **Example**: Adrianna Charo showed 1370 active_minutes but only 235 clocked_minutes
  - **Fix**: Recalculated from `activity_logs` for all Dec 12 records (35 updated)

### Data Fixes
- Deleted all Dec 12 clock_times and resynced from Connecteam API
- Recalculated `daily_scores.clocked_minutes` from corrected `clock_times`
- Recalculated `daily_scores.active_minutes` from `activity_logs`

### Analysis
- Identified 9 database tables with derived/cached data prone to staleness:
  - daily_scores, idle_periods, alerts, employee_current_status
  - employee_hourly_costs, currently_working, today_clock_times
  - working_today, employee_primary_roles
- **Planned**: Data Recalculation UI with date range picker and real-time progress

---

## [2.3.3] - 2025-12-12

### Fixed
- **Clock Times Timezone Bug (Corrected)**: Previous fix was wrong direction
  - **Root Cause**: Records synced before UTC fix had UTC times stored as CT (+6 hours offset)
  - **Actual Fix**: Subtracted 6 hours from 17 early-synced records
  - **Verification**: User confirmed correct times:
    - Toan Chau: 4:45 AM CT ✓
    - Man Nguyen: 2:06 AM CT ✓
    - Andrea Romero: 5:09 AM CT ✓

### Data Fixes
- Fixed clock_times IDs: 25679-25684, 25686-25696 (17 records)
- Skipped 25685 (Roger Dickerson) - already correct, would create duplicate
- **Note**: This fix was later superseded by v2.3.4 complete resync

---

## [2.3.2] - 2025-12-12

### Fixed
- **Clock Times Timezone Bug**: Fixed 8 records showing wrong clock-in times (6-hour offset)
  - **Root Cause**: Records synced before UTC fix showed CT time stored as UTC
  - **Example**: Xsavier Morales showed 1:55 AM CT instead of 7:55 AM CT
  - **Fix**: Added 6 hours to affected records to convert CT→UTC properly
  - **Verification**: Connecteam API now returns correct 13:55:29 UTC (= 7:55 AM CT)

### Data Fixes
- Fixed clock_times IDs: 25705, 25679, 25680, 25690, 25694, 25696, 25684
- Rolled back 1 over-corrected record (25685 - Roger Dickerson)

---

## [2.3.1] - 2025-12-12

### Fixed
- **Dashboard Rapid Refresh Bug**: Fixed API calls firing every 2-6 seconds instead of intended interval
  - **Root Cause 1**: `ManagerDashboard` class in `dashboard-api.js` auto-initializing with 30s interval
  - **Root Cause 2**: Duplicate functions (`setDateRange`, `showSection`, `applyDateFilter`) outside DOMContentLoaded
  - **Root Cause 3**: Syntax error in duplicate `applyDateFilter` (`'T12:00:00');f`)

  **Fixes Applied:**
  - Disabled ManagerDashboard auto-init in `dashboard-api.js` (line 1246-1252)
  - Removed 3 duplicate functions from end of `manager.html`
  - Increased debounce from 10s → 30s with lock mechanism
  - Increased auto-refresh interval from 60s → 2 minutes
  - Added `[DEBUG]` logging to trace API call triggers

### Added
- **Active Employees Popup**: Click on "Active Employees" metric card to see all clocked-in employees
  - Shows employee name, status (Clocked In/Out), time worked, items processed
  - Search functionality to filter employees
  - Click outside or X button to close

### Changed
- **Auto-refresh Intervals**: Dashboard now refreshes every 2 minutes (was 60 seconds)

---

## [2.3.0] - 2025-12-12

### Fixed (CRITICAL)
- **UTC Timezone Migration**: Fixed 6-hour offset bug causing wrong time calculations
  - **Root Cause**: `clock_times` stored timestamps in CT while `NOW()` returned UTC
  - **Solution**: Migrated all clock_times to UTC storage, updated all queries to use `UTC_TIMESTAMP()`

  **Changes Made:**
  - `connecteam_client.py`: Use `datetime.fromtimestamp(ts, tz=timezone.utc)` for explicit UTC
  - `connecteam_sync.py`: Changed `NOW()` to `UTC_TIMESTAMP()` in update queries
  - `dashboard.py`: Updated 6 `TIMESTAMPDIFF(...NOW())` to use `UTC_TIMESTAMP()`
  - `dashboard.py`: Fixed 5 date filters to use `DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))`
  - `dashboard.py`: Fixed Recent Activity feed to display times in CT (was showing UTC)
  - `dashboard.py`: Leaderboard now uses real-time TIMESTAMPDIFF instead of stored total_minutes
  - `dashboard.py`: Team-metrics fixed `CURDATE()` → CT date (4 queries)
  - `productivity_calculator.py`: Updated 2 `NOW()` instances to `UTC_TIMESTAMP()`
  - Migrated 4,395 historical records from CT to UTC using `CONVERT_TZ()`

  **Impact:** Time worked calculations now accurate (was showing +6 hours for active workers)
  **Impact:** "Recent Activity" feed now shows correct CT times (was showing 01:53 PM instead of 07:53 AM)
  **Impact:** Dashboard "Total Hours Worked" now shows correct ~75h instead of inflated ~148h

### Changed (UI)
- **Clock Activity Header**: Renamed "Top Performers & Recent Activity" to "Clock Activity" (reflects actual content)
- **Auto-refresh Intervals**: Changed from 30s to 60s for Dashboard, System Health, and Bottleneck tabs
- **Department Performance**: Now shows target rate - "Avg Items/Min (Target: X)"

### Data Migration
- Created backup: `clock_times_backup_20251212` (4,395 records)
- Migrated clock_in/clock_out from CT to UTC using MySQL `CONVERT_TZ()`
- All date filtering now uses CT conversion: `DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))`

---

## [2.2.5] - 2025-12-12

### Added
- **Clock Times Tooltip**: Hover over clocked hours in Cost Analysis to see clock in/out times
  - Shows each clock in/out time for single-day view only
  - Small clock icon indicates hoverable cells
  - Format: `05:20 AM - 03:41 PM (10h 21m)`

### Changed
- **Removed Auto-Refresh**: Cost Analysis no longer auto-refreshes every minute
  - Reduces unnecessary API calls and improves stability

---

## [2.2.4] - 2025-12-11

### Fixed
- **Clock Times Duplicate Records**: Fixed timezone-shifted duplicates (6-hour offset)
  - Root cause: UTC vs CT confusion creating duplicate clock_times records
  - Added deduplication logic in `connecteam_sync.py` to detect and skip duplicates
  - Created cleanup script `scripts/cleanup_clock_duplicates.py` to remove existing duplicates

- **Active Minutes Calculation**: Fixed active_minutes showing 0 for employees with activity
  - Root cause: daily_scores.active_minutes not being updated from activity_logs
  - Created `scripts/check_active_minutes.py` to detect and fix mismatches
  - Fixed 13 employee records with incorrect active_minutes values

- **API Response Enhancement**: Added active_minutes to dashboard endpoints
  - `/api/dashboard/leaderboard` now includes `active_minutes` from daily_scores
  - `/api/dashboard/clock-times/today` now includes `active_minutes` and `items_processed`

### Added
- **Diagnostic Scripts** in `backend/scripts/`:
  - `cleanup_clock_duplicates.py`: Removes duplicate clock records, fixes negative minutes
  - `compare_clocked_times.py`: Compares DB vs API clock time data
  - `check_active_minutes.py`: Validates active_minutes against activity_logs

### Technical Details
- **Modified Files**:
  - `backend/api/dashboard.py`: Added active_minutes to leaderboard (L307) and clock-times/today (L599-618)
  - `backend/integrations/connecteam_sync.py`: Added 6-hour offset detection (L325-332), fixed new shift logic (L361-378)

---

## [2.2.3] - 2025-12-11

### Added
- **System Controls - Real Functionality**: All buttons now perform actual operations
  - `Force Sync`: Triggers real `ConnecteamSync.sync_todays_shifts()` or `PodFactorySync.sync_activities()`
  - `Clear Logs`: Deletes sync logs older than 7 days from database
  - `Reset Pool`: Resets database connection pool
  - `Test Connection`: Measures actual DB latency in milliseconds
  - `View Logs`: New endpoint + modal displaying real sync logs from database
  - `Restart Service`: PM2 restart on Linux, guidance message on Windows

- **View Logs Modal**: Styled modal with scrollable log entries
  - Shows Connecteam sync status, timestamps, record counts, errors
  - Shows PodFactory daily sync summaries
  - ESC key and X button to close

### Changed
- **Custom UI Modals**: Replaced all native Chrome `confirm()` and `alert()` with styled modals
  - `showConfirmModal()`: Dark themed confirm dialog with Confirm/Cancel buttons
  - `showNotification()`: Toast notifications (success/error/warning/info)
  - `showLoadingModal()`: Spinner with progress bar, X button, ESC to cancel

### Technical Details
- **Backend** (`backend/api/system_control.py`):
  - `force_sync()`: Imports and runs actual sync classes
  - `clear_sync_logs()`: DELETE query on `connecteam_sync_log` table
  - `reset_connection_pool()`: Resets DB pool via `get_db()`
  - `test_database_connection()`: Real latency measurement with `time.time()`
  - `get_service_logs()`: New endpoint returning formatted sync logs

- **Frontend** (`frontend/manager.html`):
  - Added `showNotification()`, `showConfirmModal()`, `showLoadingModal()`
  - Refactored 6 system control functions to use async callbacks
  - Added `viewLogs()` with fetch + modal display

---

## [2.2.2] - 2025-12-11

### Fixed
- **System Health 404 Error**: Fixed `/api/system/health` endpoint returning 404
  - Root cause: `backend/api/system_control.py` imported `mysql.connector` (not installed in venv)
  - Flask silently failed to register `system_control_bp` blueprint due to import error
  - Fix: Changed import from `mysql.connector` to `pymysql` (already in venv)
  - Updated `get_db_connection()` to use pymysql syntax with `DictCursor`
  - System Health indicators in manager.html now display properly

---

## [2.2.1] - 2025-12-10

### Fixed
- **Negative Hours Data Protection**: Added multi-layer defense against invalid clock times
  - Added `GREATEST(0, ...)` wrappers to 5 TIMESTAMPDIFF locations in dashboard.py
  - Added validation in `_parse_shift()` (connecteam_client.py) - rejects invalid shifts
  - Added validation in `_sync_clock_time()` (connecteam_sync.py) - second layer defense

### Added
- **Data Quality Scripts**: Tools for auditing and fixing clock_times data
  - `backend/scripts/audit_clock_times.py`: Finds records with clock_out < clock_in
  - `backend/scripts/fix_negative_hours.py`: Auto-fixes overnight shift date errors
  - `backend/scripts/clear_today_clock_times.py`: Clears today's data for fresh re-sync

### Data Quality
- Re-synced Dec 10 data from Connecteam - **0 invalid records** after fresh sync
- Previous 16 bad records were caused by stale/corrupted data, not Connecteam source

---

## [2.2.0] - 2025-12-10

### Performance
- **Flask Startup Optimization**: Reduced startup time from 14.75s → 1.54s (90% improvement)
  - Converted 8 heavy import jobs to deferred scheduler registration
  - Jobs now register on first request rather than import time
  - Added `_jobs_registered` flag to prevent duplicate registration

### Fixed
- **Connecteam Pagination**: Fixed sync missing employees (71 → 83 employees)
  - API returns max 100 users per page; added pagination loop
  - Now fetches all pages using `nextPageToken`

- **Cost Analysis Negative Hours**: Fixed timezone mismatch causing impossible negative hours
  - Root cause: `CONVERT_TZ(NOW(), 'UTC', 'America/Chicago')` but `clock_times` stores UTC
  - Fix: Changed all 4 occurrences to use `NOW()` directly
  - Locations fixed:
    - Line 561: `/clock-times/today` endpoint
    - Lines 628/634: `/leaderboard` endpoint
    - Line 1421: Analytics endpoint
    - Line 3441: Cost Analysis CTE

- **Salary Formula**: Fixed monthly cost calculation (22 → 26 work days/month)
  - Formula: `hourly_rate = annual_salary / (26 * 12 * 8)`

### Added
- **PodFactory Email Mapping Workflow**: New endpoint for suggesting PodFactory emails
  - `POST /api/podfactory/suggest-emails` - Returns email suggestions for unmapped employees
  - Modal in frontend for manual email entry when auto-match fails

- **Payrate UI Redesign**: Improved employee payrate management
  - Cleaner card-based layout
  - Better visual hierarchy for salary vs hourly employees
  - Inline editing capabilities

### Technical Details
- **Modified Files**:
  - `backend/app.py`: Deferred scheduler job registration
  - `backend/api/dashboard.py`: Timezone fixes (4 locations), salary formula
  - `backend/integrations/connecteam_sync.py`: Pagination support
  - `frontend/manager.html`: PodFactory mapping modal, payrate UI

---

## [2.1.0] - 2025-12-09

### Added
- **Link to Connecteam Feature**: Smart employee mapping between PodFactory and Connecteam
  - Name similarity algorithm using Dice coefficient on bigrams
  - Three confidence levels with visual indicators:
    - HIGH CONFIDENCE (green): ≥50% similarity
    - POSSIBLE MATCH (yellow): 20-50% similarity
    - BEST AVAILABLE (gray): <20% similarity
  - Always shows best available match even for low-similarity names
  - Manual verification workflow for employee linking

### Changed
- Employee mapping now always displays recommendation regardless of similarity score
- Improved UX with color-coded confidence badges

### Fixed
- `showNotification is not defined` error in `saveSmartMappingConnecteam()` function
  - Replaced with `alert()` for browser compatibility

### Technical Details
- **Modified Files**:
  - `frontend/manager.html`:
    - Lines 3845-3880: Updated `openSmartMapping()` with confidence level logic
    - Lines 3937-3948: Fixed notification calls in `saveSmartMappingConnecteam()`

---

## [2.0.0] - Previous

### Core Features
- Real-time productivity tracking
- Idle detection system
- Gamification (achievements, leaderboards)
- Team metrics aggregation
- Intelligent scheduling
- Connecteam integration (time clock sync)
- PodFactory integration (production data)

### API Endpoints
- `/api/activities` - Activity management
- `/api/dashboard` - Dashboard aggregation
- `/api/connecteam` - Connecteam integration
- `/api/gamification` - Achievements/badges
- `/api/idle` - Idle detection
- `/api/team-metrics` - Team performance
- `/api/trends` - Historical trends
- `/api/schedule` - Scheduling
- `/api/system` - System controls

### Scheduler Jobs
- Activity processing every 10 minutes
- Idle check every 5 minutes
- Daily score finalization at 6 PM Central
- Daily reports at 6:30 PM Central
- Real-time score updates every 5 minutes
- Daily data reset at midnight
