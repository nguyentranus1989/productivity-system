# Codebase Summary

*Last Updated: 2025-12-14*

## Recent Changes (v2.2.2)
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
| `email` | `employees` | Contact/personal email | `john.smith@gmail.com` |
| `personal_email` | `employees` | Notification email | `johnsmith@yahoo.com` |
| `podfactory_email` | `employee_podfactory_mapping_v2` | Work email for PodFactory | `john.smithshp@colorecommerce.us` |

**Work Email Mapping Flow:**
1. Employees use work emails (@colorecommerce.us) in PodFactory daily
2. PodFactory sync pulls activities with `user_email` from `pod-report-stag.report_actions`
3. `employee_podfactory_mapping_v2` maps PodFactory emails to local employee IDs
4. One employee can have multiple PodFactory emails mapped (e.g., name variations)

**Key Tables:**
```sql
-- employee_podfactory_mapping_v2
employee_id       INT           -- FK to employees.id
podfactory_email  VARCHAR       -- @colorecommerce.us work email
podfactory_name   VARCHAR       -- Display name from PodFactory
similarity_score  FLOAT         -- Auto-mapping confidence
confidence_level  VARCHAR       -- HIGH, provisional, MANUAL
is_verified       TINYINT       -- Admin verified (0/1)
```

**DO NOT:**
- Generate random work emails - they already exist in PodFactory
- Treat `employees.email` as the work email
- Replace `employees.email` with work email

**Auth0 Integration:**
- `auth0_user_id` in `employees` - Links to Auth0 account
- `auth0_password` in `employees` - Stored password for admin reference
- Work emails in PodFactory != Auth0 login emails (legacy accounts may differ)

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
