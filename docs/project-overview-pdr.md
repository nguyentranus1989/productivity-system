# Productivity Tracker System - Project Overview

## Summary
Employee productivity tracking system for manufacturing/production environments. Integrates with Connecteam (time clock) and PodFactory (production data) to calculate real-time productivity scores.

## Tech Stack
| Layer | Technology |
|-------|------------|
| Backend | Python 3.x + Flask |
| Database | MySQL |
| Cache | Redis |
| Frontend | Vanilla HTML/CSS/JS |
| Scheduler | APScheduler |
| Integrations | Connecteam API, PodFactory API |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (HTML/JS)                      │
├─────────────────────────────────────────────────────────────┤
│  manager.html  │  employee.html  │  admin.html  │  shop-floor │
└────────────────┴─────────────────┴──────────────┴────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask REST API (:5000)                    │
├─────────────────────────────────────────────────────────────┤
│  /api/activities    │  /api/dashboard   │  /api/gamification │
│  /api/connecteam    │  /api/idle        │  /api/team-metrics │
│  /api/trends        │  /api/schedule    │  /api/cache        │
└─────────────────────┴───────────────────┴────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────────┐
        │  MySQL   │   │  Redis   │   │  APScheduler │
        └──────────┘   └──────────┘   └──────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        ┌──────────────┐              ┌──────────────┐
        │  Connecteam  │              │  PodFactory  │
        │  (Time Clock)│              │ (Production) │
        └──────────────┘              └──────────────┘
```

## Core Features

### 1. Productivity Tracking
- Real-time productivity score calculation
- Items per hour metrics
- Active time vs clocked hours comparison

### 2. Idle Detection
- Monitors employee activity gaps
- Configurable idle thresholds
- Alerts for extended idle periods

### 3. Gamification
- Achievement system
- Leaderboards
- Performance badges

### 4. Team Metrics
- Aggregated team performance
- Cross-team comparisons
- Historical trends

### 5. Intelligent Scheduling
- Shift optimization
- Station assignment recommendations
- Performance-based scheduling

### 6. Integrations
- **Connecteam**: Auto-sync time clock data every 5 minutes
- **PodFactory**: Production activity data sync

## Directory Structure

```
productivity-system/
├── backend/
│   ├── app.py                  # Flask entry point
│   ├── config.py               # Environment configuration
│   ├── api/                    # REST API blueprints
│   │   ├── activities.py       # Activity endpoints
│   │   ├── dashboard.py        # Dashboard data
│   │   ├── connecteam.py       # Connecteam integration
│   │   ├── gamification.py     # Achievements/badges
│   │   ├── idle.py             # Idle detection
│   │   ├── schedule.py         # Scheduling
│   │   ├── team_metrics.py     # Team aggregations
│   │   └── trends.py           # Historical trends
│   ├── calculations/           # Core business logic
│   │   ├── productivity_calculator.py
│   │   ├── idle_detector.py
│   │   ├── gamification_engine.py
│   │   └── scheduler.py
│   ├── database/               # Database layer
│   │   └── db_manager.py
│   ├── integrations/           # External APIs
│   │   └── connecteam_sync.py
│   └── models/                 # Data models
├── frontend/
│   ├── manager.html            # Manager dashboard
│   ├── employee.html           # Employee view
│   ├── admin.html              # Admin panel
│   ├── shop-floor.html         # Shop floor display
│   ├── intelligent-schedule.html
│   └── js/                     # Shared JavaScript
└── backups/                    # Database backups
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| ENVIRONMENT | dev/production | development |
| DB_HOST | MySQL host | localhost |
| DB_PORT | MySQL port | 3306 |
| DB_NAME | Database name | productivity_tracker |
| DB_USER | Database user | root |
| DB_PASSWORD | Database password | - |
| REDIS_HOST | Redis host | localhost |
| REDIS_PORT | Redis port | 6379 |
| CONNECTEAM_API_KEY | Connecteam API key | - |
| CONNECTEAM_CLOCK_ID | Connecteam clock ID | - |
| ENABLE_AUTO_SYNC | Enable auto sync | false |

## API Endpoints

### Activities
- `GET /api/activities/` - List activities
- `GET /api/activities/recent` - Recent activities

### Dashboard
- `GET /api/dashboard/` - Dashboard summary
- `GET /api/dashboard/metrics` - Key metrics

### Connecteam
- `GET /api/connecteam/sync` - Trigger sync
- `GET /api/connecteam/status` - Sync status

### Gamification
- `GET /api/gamification/achievements` - User achievements
- `GET /api/gamification/leaderboard` - Rankings

## Running the Application

### Development
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```

### Production
Uses PM2 process manager:
- `flask-backend` - Main Flask app
- `podfactory-sync` - Production data sync

## Known Issues / Tech Debt
1. Large monolithic HTML files (manager.html: 219KB)
2. Multiple backup files need cleanup
3. Some hardcoded production IPs in config
4. .env files tracked in git (security concern)
