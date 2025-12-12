# Codebase Summary

*Last Updated: 2025-12-10*

## Recent Changes (v2.2.1)
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
