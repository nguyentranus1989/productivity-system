# System Architecture

## High-Level Overview

```
                    ┌─────────────────┐
                    │   Web Browser   │
                    └────────┬────────┘
                             │ HTTP
                             ▼
┌────────────────────────────────────────────────────────────┐
│                    NGINX (Reverse Proxy)                    │
│                    Production: 134.199.194.237              │
└────────────────────────────┬───────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Static HTML │  │  Flask API   │  │   PM2 Jobs   │
   │   Frontend   │  │   :5000      │  │              │
   └──────────────┘  └──────┬───────┘  └──────┬───────┘
                           │                  │
                           └────────┬─────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       ┌──────────┐          ┌──────────┐          ┌──────────┐
       │  MySQL   │          │  Redis   │          │ External │
       │ Database │          │  Cache   │          │   APIs   │
       └──────────┘          └──────────┘          └──────────┘
                                                        │
                              ┌──────────────────────────┤
                              │                          │
                              ▼                          ▼
                       ┌──────────────┐          ┌──────────────┐
                       │  Connecteam  │          │  PodFactory  │
                       └──────────────┘          └──────────────┘
```

## Component Details

### 1. Web Server Layer
- **NGINX**: Reverse proxy, static file serving
- **Port**: 80 (HTTP), 443 (HTTPS)
- **Static Files**: HTML, JS, CSS from `/frontend/`

### 2. Application Layer
- **Flask**: Python web framework
- **Port**: 5000
- **CORS**: Enabled for API routes
- **Auth**: API key + session-based

### 3. Background Jobs (PM2)
| Process | Script | Interval |
|---------|--------|----------|
| flask-backend | app.py | Always running |
| podfactory-sync | sync_wrapper.py | Continuous |

### 4. Scheduler (APScheduler)
| Job | Trigger | Purpose |
|-----|---------|---------|
| connecteam_shifts_sync | Every 5 min | Sync time clock |
| connecteam_employee_sync | Daily 2 AM | Sync employees |
| productivity_calculation | Configurable | Update scores |

### 5. Database Layer

#### MySQL Schema
```sql
-- Core tables (inferred)
employees
├── id (PK)
├── name
├── connecteam_id
├── email
└── role

activity_logs
├── id (PK)
├── employee_id (FK)
├── activity_type
├── items_count
├── duration_minutes
├── window_start
└── window_end

connecteam_shifts
├── id (PK)
├── employee_id (FK)
├── clock_in
├── clock_out
└── total_hours

daily_scores
├── id (PK)
├── employee_id (FK)
├── date
├── productivity_score
├── active_time
└── clocked_hours
```

### 6. Cache Layer (Redis)
- Session storage
- API response caching
- Rate limiting data

### 7. External Integrations

#### Connecteam
- **Purpose**: Time clock data
- **Sync**: Every 5 minutes
- **Data**: Clock in/out times, shift hours

#### PodFactory
- **Purpose**: Production activity data
- **Sync**: Continuous via sync_wrapper.py
- **Data**: Items produced, activity types

## Data Flow

### 1. Productivity Score Calculation
```
PodFactory API → activity_logs table
                        ↓
Connecteam API → connecteam_shifts table
                        ↓
            ProductivityCalculator
                        ↓
               daily_scores table
                        ↓
                 Dashboard API
                        ↓
                   Frontend
```

### 2. Real-time Updates
```
APScheduler triggers → Calculations run
                              ↓
                    Redis cache invalidated
                              ↓
                    Next API call fetches fresh data
```

## Security Considerations

### Current State
- API key authentication
- Session-based auth for frontend
- CORS configured for API routes
- bcrypt for password hashing

### Concerns
- .env files tracked in git
- Hardcoded production IP
- No HTTPS enforcement in config

## Scalability Notes

### Current Limits
- Single server deployment
- No load balancing
- MySQL single instance

### Potential Improvements
- Add read replicas for MySQL
- Redis cluster for caching
- Container orchestration (K8s)
