# Algorithms & Business Logic Documentation

## Table of Contents
1. [Productivity Score Calculation](#1-productivity-score-calculation)
2. [Active Time Calculation](#2-active-time-calculation)
3. [Idle Detection System](#3-idle-detection-system)
4. [Role Configuration](#4-role-configuration)
5. [Gamification System](#5-gamification-system)
6. [Data Sync Integrations](#6-data-sync-integrations)
7. [Database Schema](#7-database-schema)

---

## 1. Productivity Score Calculation

### Overview
The productivity system calculates employee performance based on **items processed** multiplied by **role-specific multipliers**. The scoring is **activity-based**, meaning an employee's role is determined by their activities each day, not a fixed assignment.

### Core Formula
```
Points = Σ (items_count × role_multiplier)
```

Where:
- `items_count` = number of items processed in an activity
- `role_multiplier` = multiplier from `role_configs` table based on activity type

### Implementation (`productivity_calculator.py:290-300`)
```python
points_earned_result = self.db.execute_one(
    """
    SELECT COALESCE(SUM(al.items_count * rc.multiplier), 0) as total_points
    FROM activity_logs al
    JOIN role_configs rc ON rc.id = al.role_id
    WHERE al.employee_id = %s
    AND DATE(al.window_start) = %s
    """,
    (employee_id, process_date)
)
```

### Daily Score Components
| Metric | Description |
|--------|-------------|
| `items_processed` | Total items processed across all activities |
| `active_minutes` | Time actively working (clocked - idle) |
| `clocked_minutes` | Total time clocked in |
| `efficiency_rate` | active_minutes / clocked_minutes |
| `points_earned` | Sum of (items × multiplier) |

---

## 2. Active Time Calculation

### Overview
Active time is calculated by **subtracting excess idle time** from total clocked time. This captures actual productive work time.

### Algorithm (`productivity_calculator.py:45-197`)

```
Active Time = Clocked Time - Total Excess Idle

Where Total Excess Idle includes:
1. Start-of-day idle (gap between clock-in and first activity > 15 min)
2. Between-activity gaps (exceeding threshold)
3. End-of-day idle (gap between last activity and clock-out)
```

### Step-by-Step Process

#### Step 1: Get Clock Data
```sql
SELECT
    MIN(clock_in) as first_clock_in,
    MAX(COALESCE(clock_out, NOW())) as last_clock_out,
    TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, NOW()))) as total_minutes
FROM clock_times
WHERE employee_id = ? AND clock_in >= ? AND clock_in < ?
```

#### Step 2: Calculate Start-of-Day Idle
```python
start_gap = (first_activity_start - clock_in).total_seconds() / 60
start_threshold = 15  # 15 minutes to get settled
if start_gap > start_threshold:
    total_excess_idle += (start_gap - start_threshold)
```

#### Step 3: Calculate Between-Activity Gaps
For each consecutive pair of activities:
```python
gap_minutes = (curr_start - prev_end).total_seconds() / 60

# Dynamic threshold for batch work
if role_type == 'batch':
    time_per_item = 60.0 / expected_per_hour
    threshold = max(3, items_count * time_per_item * 1.05)
else:
    threshold = idle_threshold_minutes  # Fixed for continuous work

if gap_minutes > threshold:
    excess = gap_minutes - threshold
    total_excess_idle += excess
```

#### Step 4: Calculate End-of-Day Idle
```python
end_gap = (clock_out - last_activity_end).total_seconds() / 60

# If clocked out (not still working)
if clocked_out:
    end_threshold = base_threshold + 15  # 15 min cleanup allowance
else:
    end_threshold = base_threshold

if end_gap > end_threshold:
    total_excess_idle += (end_gap - end_threshold)
```

#### Step 5: Final Calculation
```python
active_minutes = max(0, total_clocked - total_excess_idle)
efficiency_rate = active_minutes / clocked_minutes  # Capped at 1.0
```

---

## 3. Idle Detection System

### Overview
The system monitors employee activity gaps in real-time and records idle periods that exceed role-specific thresholds.

### Dynamic Idle Threshold (`idle_detector.py:16-51`)

#### For Continuous Work (e.g., Heat Pressing)
```python
threshold = role_config.idle_threshold_minutes  # Fixed value (e.g., 5-10 min)
```

#### For Batch Work (e.g., Picking, Labeling)
```python
# Time per item in minutes
time_per_item = 60.0 / expected_per_hour

# Dynamic threshold with 5% buffer
dynamic_threshold = items_count * time_per_item * 1.05

# Minimum 3 minutes
threshold = max(3, dynamic_threshold)
```

### Real-Time Idle Check (`idle_detector.py:53-181`)
```python
def check_real_time_idle(employee_id):
    # 1. Get employee info and role config
    # 2. Check if currently clocked in
    # 3. Get last activity
    # 4. Calculate idle threshold based on last activity's role
    # 5. If idle time > threshold:
    #    - Record idle period in database
    #    - Create alert (warning or critical)
```

### Alert Severity Levels
| Level | Condition |
|-------|-----------|
| `warning` | idle_minutes > threshold |
| `critical` | idle_minutes > threshold × 1.5 |

---

## 4. Role Configuration

### Role Types

#### Continuous Work
- **Heat Pressing** (role_id: 1)
- **Packing/Shipping** (role_id: 2)
- Fixed idle threshold
- Expected output measured per hour

#### Batch Work
- **Picker** (role_id: 3)
- **Labeler** (role_id: 4)
- **Film Matching** (role_id: 5)
- Dynamic idle threshold based on batch size
- Variable processing time per item

### Role Configuration Fields (`models/role.py`)
```python
@dataclass
class RoleConfig:
    id: int
    role_name: str
    role_type: str           # 'continuous' or 'batch'
    multiplier: float        # Points multiplier (e.g., 1.0, 1.2)
    expected_per_hour: int   # Expected items/hour
    idle_threshold_minutes: int  # Base idle threshold
    monthly_target: int      # Monthly points target
    seconds_per_item: int    # For batch workers only
```

### Action to Role Mapping (PodFactory)
```python
ACTION_TO_ROLE_ID = {
    'In Production': 1,      # Heat Pressing
    'QC Passed': 2,          # Packing and Shipping
    'Picking': 3,            # Picker
    'Labeling': 4,           # Labeler
    'Film Matching': 5       # Film Matching
}
```

---

## 5. Gamification System

### Achievement Types (`gamification_engine.py`)

| Type | Trigger | Example |
|------|---------|---------|
| `daily` | Daily conditions | Meet daily target, 90%+ efficiency |
| `weekly` | Weekly conditions | 5-day consistency |
| `streak` | Consecutive days | 3/7/30-day streaks |
| `milestone` | Cumulative totals | 1,000/10,000 points |
| `special` | Special conditions | Zero idle, team goals |

### Achievement Definitions
```python
achievements = {
    "daily_target_met": {"points": 10, "icon": "🎯"},
    "perfect_efficiency": {"points": 15, "icon": "⚡"},  # 90%+ efficiency
    "early_bird": {"points": 5, "icon": "🌅"},          # Start before 7:30 AM
    "streak_3": {"points": 20, "icon": "🔥"},
    "streak_7": {"points": 75, "icon": "⚔️"},
    "streak_30": {"points": 500, "icon": "🏆"},
    "first_1000_points": {"points": 25, "icon": "💎"},
    "first_10000_points": {"points": 100, "icon": "💫"},
    "zero_idle": {"points": 25, "icon": "🚀"},
}
```

### Badge Levels
```python
def calculate_badge_level(points):
    if points >= 5000: return "diamond"
    if points >= 2000: return "platinum"
    if points >= 1000: return "gold"
    if points >= 500:  return "silver"
    if points >= 100:  return "bronze"
    return "none"
```

### Streak Calculation
```python
# Calculate consecutive days meeting target
for i, score in enumerate(scores):
    expected_date = today - timedelta(days=i)
    if score.date == expected_date and score.points >= daily_target:
        current_streak += 1
    else:
        break
```

---

## 6. Data Sync Integrations

### 6.1 Connecteam Integration (Time Clock)

#### Sync Schedule
| Job | Interval |
|-----|----------|
| `connecteam_shifts_sync` | Every 5 minutes |
| `connecteam_employee_sync` | Daily at 2:00 AM |

#### Sync Process (`connecteam_sync.py`)
```
1. Get today's shifts from Connecteam API
2. For each shift:
   a. Find employee by connecteam_user_id
   b. Convert times: UTC (API) → UTC (database)
   c. Update or create clock_times record
   d. Handle duplicates (within 5-minute window = same shift)
   e. Update live cache for active employees
3. Log sync status
```

#### Duplicate Prevention
```python
# Records within 5 minutes are considered the same shift
if seconds_diff < 300:  # 5 minutes
    # Update existing record
else:
    # Create new record (legitimate second shift)
```

#### Timezone Handling
```python
# All times stored in UTC
# Convert to Central Time only for display
clock_in_central = convert_to_central(clock_in_utc)
display_time = clock_in_central.strftime('%I:%M %p')  # "08:30 AM"
```

### 6.2 PodFactory Integration (Production Data)

#### Sync Process (`podfactory_sync.py`)
```
1. Get last sync time
2. Fetch new activities from PodFactory database (report_actions table)
3. Check for existing activities (prevent duplicates)
4. For each new activity:
   a. Match employee by name/email (fuzzy matching)
   b. Map action to role_id
   c. Keep times in UTC
   d. Write to activity_logs table
5. Trigger score recalculation if any activities synced
```

#### Employee Name Matching
```python
def find_employee_by_name(email, name_mappings, user_name):
    # Try exact match on normalized name
    # Try variations: dot-separated, underscore-separated
    # Try partial match on significant name parts (>3 chars)
    # Try fuzzy match (all parts must exist in mapping)
    # Fall back to email-based matching
    # Auto-create employee if not found
```

#### Action to Department Mapping
```python
ACTION_TO_DEPARTMENT_MAP = {
    'In Production': 'Heat Press',
    'Picking': 'Picking',
    'Labeling': 'Labeling',
    'Film Matching': 'Film Matching',
    'QC Passed': 'Packing'
}
```

---

## 7. Database Schema

### Core Tables

#### `employees`
```sql
- id (PK)
- name
- email
- connecteam_user_id (FK to Connecteam)
- is_active
- achievement_points
- current_streak
- hire_date
- created_at, updated_at
```

#### `role_configs`
```sql
- id (PK)
- role_name
- role_type ('continuous' | 'batch')
- multiplier
- expected_per_hour
- idle_threshold_minutes
- monthly_target
- seconds_per_item
```

#### `activity_logs`
```sql
- id (PK)
- report_id (unique identifier)
- employee_id (FK)
- role_id (FK)
- activity_type
- items_count
- window_start (UTC)
- window_end (UTC)
- department
- source ('podfactory')
- reference_id (PodFactory ID)
- duration_minutes
```

#### `clock_times`
```sql
- id (PK)
- employee_id (FK)
- clock_in (UTC)
- clock_out (UTC)
- total_minutes
- break_minutes
- is_active
- source ('connecteam')
```

#### `daily_scores`
```sql
- id (PK)
- employee_id (FK)
- score_date
- items_processed
- active_minutes
- clocked_minutes
- efficiency_rate
- points_earned
- created_at, updated_at
```

#### `idle_periods`
```sql
- id (PK)
- employee_id (FK)
- start_time
- end_time
- duration_minutes
```

#### `achievements`
```sql
- id (PK)
- employee_id (FK)
- achievement_key
- achievement_name
- description
- points_awarded
- achievement_type
- earned_date
```

#### `alerts`
```sql
- id (PK)
- employee_id (FK)
- alert_type
- severity ('warning' | 'critical')
- message
- created_at
```

### Sync/Log Tables

#### `connecteam_sync_log`
```sql
- id (PK)
- sync_type
- records_synced
- status
- details (JSON)
- synced_at
```

#### `podfactory_sync_log`
```sql
- id (PK)
- sync_time
- records_synced
- status
- notes
```

---

## Timezone Handling

### Storage Convention
- **All times stored in UTC** in the database
- Convert to **Central Time (America/Chicago)** only for display

### Conversion Functions
```python
# Get current Central Time
def get_central_date():
    return datetime.now(pytz.timezone('America/Chicago')).date()

# UTC to Central for display
def convert_to_central(utc_dt):
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(pytz.timezone('America/Chicago'))

# Central date to UTC range for queries
def ct_date_to_utc_range(central_date):
    # Returns (utc_start, utc_end) for querying a Central Time date
```

---

## Scheduler Jobs

### APScheduler Configuration (`app.py`, `scheduler.py`)

| Job ID | Interval | Description |
|--------|----------|-------------|
| `realtime_updates` | 1 min | Update live scores |
| `process_activities` | 5 min | Process recent activities |
| `check_idle` | 5 min | Check for idle employees |
| `connecteam_shifts_sync` | 5 min | Sync Connecteam shifts |
| `connecteam_employee_sync` | Daily 2 AM | Sync Connecteam employees |
| `daily_reset` | Daily 12 AM | Reset daily data |
| `finalize_daily` | Daily 6 PM | Finalize daily scores |
| `daily_reports` | Daily 6:30 PM | Generate daily reports |
