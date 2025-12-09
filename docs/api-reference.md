# API Reference

## Authentication
All API endpoints require the `X-API-Key` header:
```
X-API-Key: dev-api-key-123
```

## Base URLs
- **Development**: `http://localhost:5000`
- **Production**: `http://134.199.194.237:5000`

---

## Health & Status

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-08T22:00:00.000Z",
  "service": "Productivity Tracker API",
  "features": {
    "core": true,
    "analytics": true,
    "gamification": true,
    "team_metrics": true,
    "connecteam": true
  }
}
```

### GET /api/scheduler/status
Get scheduler job status.

**Response:**
```json
{
  "productivity_scheduler": {
    "status": "running",
    "jobs": [
      {
        "id": "realtime_updates",
        "name": "Update Real-time Scores",
        "next_run": "2025-12-08 10:42:06 PM CST",
        "active": true
      }
    ]
  },
  "background_scheduler": {
    "status": "running",
    "jobs": [...]
  }
}
```

---

## Dashboard API

### GET /api/dashboard/leaderboard
Get employee leaderboard for a date.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `date` | string | Date in YYYY-MM-DD format (default: today) |

**Response:**
```json
[
  {
    "rank": 1,
    "id": 24,
    "name": "dung duong",
    "department": "Packing and Shipping",
    "items_today": 1153,
    "items_per_hour": 112.1,
    "score": 922.4,
    "time_worked": "10:17",
    "is_clocked_in": 0,
    "clock_status": "🔴",
    "streak": 1,
    "badge": "🔥 Top Performer!",
    "activity_breakdown": "🎯 Picking: 211 - 🏷️ Labeling: 538..."
  }
]
```

### GET /api/dashboard/leaderboard/live
Get real-time leaderboard with live updates.

### GET /api/dashboard/activities/recent
Get recent activities.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Number of activities (default: 5) |

**Response:**
```json
[
  {
    "type": "clock_out",
    "employee_name": "Fannie Arredondo",
    "description": "Fannie Arredondo clocked out at 06:27 PM",
    "time_str": "06:27 PM",
    "timestamp": "Mon, 08 Dec 2025 18:27:15 GMT"
  }
]
```

### GET /api/dashboard/departments/stats
Get department statistics.

### GET /api/dashboard/analytics/date-range
Get analytics for a date range.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `start_date` | string | Start date (YYYY-MM-DD) |
| `end_date` | string | End date (YYYY-MM-DD) |

### GET /api/dashboard/clock-times/today
Get today's clock times for all employees.

### GET /api/dashboard/server-time
Get current server time.

### GET /api/dashboard/employees
Get all employees.

### GET /api/dashboard/employees/:id
Get specific employee details.

### GET /api/dashboard/employees/:id/stats
Get employee statistics.

### POST /api/dashboard/activities/activity
Create a single activity.

**Request Body:**
```json
{
  "employee_id": 1,
  "scan_type": "batch_scan",
  "quantity": 25,
  "department": "Picking",
  "timestamp": "2025-12-08T14:30:00Z",
  "window_end": "2025-12-08T14:39:59Z",
  "metadata": {
    "source": "podfactory",
    "podfactory_id": "12345",
    "action": "Picking",
    "role_id": 3
  }
}
```

### POST /api/dashboard/activities/bulk
Create multiple activities in batch.

**Request Body:**
```json
[
  { /* activity 1 */ },
  { /* activity 2 */ }
]
```

---

## Connecteam API

### GET /api/connecteam/status
Get Connecteam integration status.

**Response:**
```json
{
  "enabled": true,
  "sync_interval": 300,
  "clock_id": 7425182
}
```

### POST /api/connecteam/sync/employees
Trigger employee sync from Connecteam.

### GET /api/connecteam/sync
Trigger shift sync from Connecteam.

---

## Gamification API

### GET /api/gamification/achievements
Get employee achievements.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `employee_id` | int | Employee ID |

**Response:**
```json
{
  "total_achievements": 5,
  "total_points": 150,
  "current_streak": 3,
  "badge_level": "silver",
  "recent_achievements": [...],
  "all_achievements": [...],
  "completion_percentage": 41.7
}
```

### GET /api/gamification/leaderboard
Get gamification leaderboard.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `period` | string | "daily", "weekly", "monthly", "all" |

---

## Team Metrics API

### GET /api/team-metrics/
Get team performance metrics.

### GET /api/team-metrics/department/:name
Get metrics for specific department.

---

## Analytics Endpoints

### GET /api/dashboard/analytics/streak-leaders
Get employees with best streaks.

### GET /api/dashboard/analytics/achievement-ticker
Get recent achievement activity.

### GET /api/dashboard/analytics/hourly-heatmap
Get hourly activity heatmap data.

### GET /api/dashboard/analytics/hourly
Get hourly breakdown.

### GET /api/dashboard/analytics/team-metrics
Get team-level metrics.

---

## System Control API

### GET /api/system/health
Get detailed system health.

### GET /api/system/pm2-status
Get PM2 process status.

### POST /api/system/restart-service
Restart a specific service.

**Request Body:**
```json
{
  "service": "flask-backend"
}
```

### POST /api/system/force-sync
Force immediate sync.

**Request Body:**
```json
{
  "sync_type": "connecteam"
}
```

### POST /api/system/clear-sync-logs
Clear sync logs.

### GET /api/system/test-connection
Test database connection.

### POST /api/system/reset-connection-pool
Reset database connection pool.

### POST /api/system/restart-all
Restart all services.

---

## Idle Detection API

### GET /api/idle/current
Get currently idle employees.

### GET /api/idle/summary
Get idle summary for a date.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `date` | string | Date (YYYY-MM-DD) |

---

## Trends API

### GET /api/trends/
Get trend data.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `employee_id` | int | Employee ID (optional) |
| `days` | int | Number of days (default: 7) |

---

## Schedule API

### GET /api/schedule/weekly
Get weekly schedule.

### GET /api/schedule/predictions/weekly
Get schedule predictions.

### GET /api/schedule/employees
Get scheduled employees.

### GET /api/schedule/employees/all
Get all employees for scheduling.

### POST /api/schedule/save
Save schedule changes.

**Request Body:**
```json
{
  "schedule": {...},
  "week_start": "2025-12-09"
}
```

---

## Alerts API

### GET /api/dashboard/alerts/active
Get active alerts.

---

## Bottleneck Analysis

### GET /api/dashboard/bottleneck/current
Get current bottleneck analysis.

### GET /api/dashboard/bottleneck/history
Get bottleneck history.

### POST /api/dashboard/bottleneck/reassign
Reassign worker to address bottleneck.

---

## Station Performance

### GET /api/station-performance
Get employee performance by station.

**Response:**
```json
{
  "success": true,
  "data": {
    "Heat Press": [
      {
        "employee_id": 28,
        "employee_name": "Abraham Remirez",
        "avg_items_per_hour": 69.1
      }
    ],
    "Picking": [...],
    "Labeling": [...]
  }
}
```

---

## Error Responses

All errors follow this format:
```json
{
  "error": "Error message description"
}
```

### HTTP Status Codes
| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Resource not found |
| 500 | Internal server error |
