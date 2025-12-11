# Changelog

All notable changes to the Productivity Tracker system.

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
