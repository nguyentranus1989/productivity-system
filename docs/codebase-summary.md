# Codebase Summary

*Last Updated: 2025-12-15*

## Recent Changes (v2.2.3)
- **Per-Role Auth0 Credentials**: Each PodFactory email = separate Auth0 account
  - Added `auth0_user_id`, `auth0_password` columns to `employee_podfactory_mapping_v2`
  - Supports multiple roles per employee (e.g., Shipping, QC each with own login)
  - Custom password option when creating/resetting Auth0 accounts
- **New API Endpoints**:
  - `GET /api/admin/employees/<id>/podfactory-credentials` - all role credentials
  - `POST /api/admin/podfactory-mappings/<id>/setup-auth0` - create Auth0 per email
  - `POST /api/admin/podfactory-mappings/<id>/reset-auth0-password` - reset per email
- **Frontend Updates**:
  - PodFactory "View (N)" button shows count of role emails
  - Modal lists all emails with Setup/Reset/Copy buttons per row
  - Setup/Reset modals have checkbox for custom password input
- **Bug Fix**: PodFactory column was showing "-" - fixed adminMap merge to include `podfactory_email`

## Previous (v2.2.2)
- **Auth0 Integration**: Employee account management
  - Auto-create Auth0 accounts when adding employees
  - Reset Auth0 password with `auth0_password` stored for admin reference
  - Welcome email with Employee ID + PIN sent on creation
- **Credential Management UI**: New Portal/PodFactory columns in employee table
  - Portal: Employee ID + PIN with View/Reset
  - PodFactory: Work email from `employee_podfactory_mapping_v2` + Auth0 password
  - Orange dot indicator when credentials missing
- **Styled Modals**: Replaced all native browser popups with themed modals

## Previous (v2.2.1)
- **Negative Hours Protection**: Multi-layer defense
  - `GREATEST(0,...)` wrappers on 5 TIMESTAMPDIFF locations
  - Validation in `_parse_shift()` and `_sync_clock_time()`
- **Data Quality Scripts**: audit, fix, and clear clock_times
- **Fresh Re-sync**: 0 invalid records after clean Connecteam sync

## Previous (v2.2.0)
- **Performance**: Flask startup 14.75s → 1.54s (90% faster)
- **Connecteam Pagination**: Now syncs all employees (71 → 83)
- **Cost Analysis Fix**: Timezone mismatch causing negative hours
- **Salary Formula**: Fixed work days/month (22 → 26)
- **PodFactory Mapping**: New email suggestion workflow
- **Payrate UI**: Redesigned management interface

## Backend Modules

### API Layer (`backend/api/`)
| File | Purpose | Lines |
|------|---------|-------|
| activities.py | Activity CRUD endpoints | - |
| admin_auth.py | Admin authentication | - |
| auth.py | Shared auth utilities | - |
| cache.py | Cache management | - |
| connecteam.py | Connecteam integration API | - |
| dashboard.py | Dashboard data aggregation | - |
| employee_auth.py | Employee login/logout | - |
| flags.py | Feature flags | - |
| gamification.py | Achievements, leaderboards | - |
| idle.py | Idle detection endpoints | - |
| intelligent_schedule.py | AI scheduling | - |
| schedule.py | Manual scheduling | - |
| scheduling_insights.py | Schedule analytics | - |
| system_control.py | System admin controls | - |
| team_metrics.py | Team performance | - |
| trends.py | Historical trends | - |
| user_management.py | Employee CRUD, PIN, Auth0 | - |
| validators.py | Input validation | - |

### Calculation Engine (`backend/calculations/`)
| File | Purpose |
|------|---------|
| productivity_calculator.py | Core productivity scoring |
| idle_detector.py | Idle period detection |
| enhanced_idle_detector.py | Advanced idle detection |
| gamification_engine.py | Achievement logic |
| team_metrics_engine.py | Team aggregations |
| trend_analyzer.py | Trend computation |
| scheduler.py | Background job scheduler |
| performance_predictor.py | ML predictions |
| predictive_scorer.py | Score predictions |
| activity_flagger.py | Activity anomaly detection |
| activity_processor.py | Activity data processing |

### Integrations (`backend/integrations/`)
| File | Purpose |
|------|---------|
| connecteam_sync.py | Connecteam API sync |
| auth0_manager.py | Auth0 user management (create, delete, reset password) |

### Database (`backend/database/`)
| File | Purpose |
|------|---------|
| db_manager.py | MySQL connection manager |

## Frontend Pages

| File | Purpose | Size |
|------|---------|------|
| manager.html | Main manager dashboard | 219KB |
| employee.html | Employee self-view | 36KB |
| admin.html | Admin controls | 26KB |
| intelligent-schedule.html | Scheduling tool | 101KB |
| shop-floor.html | Shop floor display | 28KB |
| login.html | Login page | 19KB |
| station-assignment.html | Station assignments | 6KB |

## Key Dependencies

### Python (`requirements.txt`)
- Flask 3.1.2 - Web framework
- APScheduler 3.11.0 - Background jobs
- mysql-connector-python 9.4.0 - MySQL driver
- PyMySQL 1.1.2 - Alternative MySQL driver
- redis 6.4.0 - Redis client
- pandas 2.3.2 - Data processing
- scikit-learn 1.7.1 - ML predictions
- python-dotenv 1.1.1 - Env management
- pytz 2025.2 - Timezone handling
- requests 2.32.5 - HTTP client
- bcrypt 4.3.0 - Password hashing

## Database Schema (Inferred)

### Core Tables
- `employees` - Employee records
- `activity_logs` - Production activities
- `connecteam_shifts` - Time clock data
- `achievements` - Gamification badges
- `daily_scores` - Calculated productivity scores
- `employee_podfactory_mapping_v2` - Maps employees to PodFactory work emails
- `employee_auth` - Employee PIN authentication for portal

### Employee Email Architecture

**IMPORTANT**: The system uses separate email fields for different purposes:

| Field | Table | Purpose | Example |
|-------|-------|---------|---------|
| `email` | `employees` | Primary work email (legacy) | `john.smithshp@colorecommerce.us` |
| `personal_email` | `employees` | Personal email for notifications | `johnsmith@gmail.com` |
| `podfactory_email` | `employee_podfactory_mapping_v2` | Role-specific work email | `john.smithshp@colorecommerce.us` |

**Per-Role Auth0 Architecture (v2.2.3):**
- Each employee can have 1-3 **roles** in PodFactory (e.g., Shipping, QC, Admin)
- Each **role** has its own **work email** (@colorecommerce.us)
- Each **work email** = separate **Auth0 account** with its own password
- This allows tracking performance per role when employee logs in

```
Employee: Abraham Ramirez
├── Role: Shipping → abraham_ramirezship@colorecommerce.us → Auth0 Account A
├── Role: QC      → abraham_ramirez@colorecommerce.us     → Auth0 Account B
└── Role: Generic → abraham@colorecommerce.us             → Auth0 Account C
```

**Key Tables:**
```sql
-- employee_podfactory_mapping_v2 (Auth0 credentials per role email)
employee_id       INT           -- FK to employees.id
podfactory_email  VARCHAR       -- @colorecommerce.us work email
podfactory_name   VARCHAR       -- Display name from PodFactory
auth0_user_id     VARCHAR(128)  -- Auth0 account ID for this email
auth0_password    VARCHAR(64)   -- Stored password for admin reference
similarity_score  FLOAT         -- Auto-mapping confidence
confidence_level  VARCHAR       -- HIGH, MEDIUM, LOW, MANUAL
is_verified       TINYINT       -- Admin verified (0/1)
```

**DO NOT:**
- Generate random work emails - they already exist in PodFactory
- Assume one Auth0 account per employee - each role email needs its own
- Store Auth0 credentials in `employees` table - use mapping table instead

## Configuration

### Development vs Production
- Development: localhost connections
- Production: 134.199.194.237

### Scheduler Jobs
1. **Productivity calculation** - Periodic score updates
2. **Connecteam sync** - Every 5 minutes
3. **Employee sync** - Daily at 2 AM

## File Naming Conventions
- API: `{feature}.py`
- Calculations: `{feature}_calculator.py` or `{feature}_engine.py`
- Sync scripts: `{service}_sync.py`
- Fix scripts: `fix_{issue}.py` (archived)
