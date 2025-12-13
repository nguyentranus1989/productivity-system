# Cost Analysis Data Flow Diagrams

## Current Architecture (Problematic)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER CLICKS TAB                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  showSection('cost')                                             │
│  ├─ No cache check                                               │
│  ├─ No loading indicator                                         │
│  └─ Immediately calls loadCostAnalysisData()                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ⏱️ 0ms - User sees stale/blank screen
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  API Request: /dashboard/cost-analysis                           │
│  ├─ No timeout configured                                        │
│  └─ Single blocking call                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ⏱️ 100-300ms - Network RTT
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND: Dashboard.py                                           │
│  ├─ Check 30s cache (low hit rate)                               │
│  └─ Execute queries if cache miss:                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────┴────────────────────┐
        │                                         │
        ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│  Query 1:        │                    │  Query 2:        │
│  employee_hours  │                    │  employee_       │
│  CTE             │                    │  activities CTE  │
│  (8 params)      │                    │  (2 params)      │
│                  │                    │                  │
│  Scans:          │                    │  Scans:          │
│  - clock_times   │                    │  - daily_scores  │
│  - employees     │                    │                  │
│  - payrates      │                    │  Aggregates      │
│                  │                    │  items/hours     │
│  ⏱️ 500-1000ms   │                    │  ⏱️ 200-500ms    │
└────────┬─────────┘                    └────────┬─────────┘
         │                                       │
         └────────────────┬──────────────────────┘
                          │
                          ▼
                 ⏱️ 1000-1500ms elapsed
                          │
                          ▼
         ┌────────────────────────────────────┐
         │  Main Query: JOIN CTEs              │
         │  Returns ~20-50 employee records    │
         │  ⏱️ +100-200ms                      │
         └────────────┬───────────────────────┘
                      │
                      ▼
         ┌────────────────────────────────────┐
         │  FOR EACH EMPLOYEE (N=20-50):      │
         │                                     │
         │  Query: activity_breakdown          │
         │  ├─ Scan activity_logs              │
         │  ├─ Group by activity_type          │
         │  └─ Sum items_count                 │
         │                                     │
         │  ⏱️ 30-50ms × N = 600-2500ms        │
         └────────────┬───────────────────────┘
                      │
                      ▼
         ┌────────────────────────────────────┐
         │  Query: department_costs            │
         │  ⏱️ +200-400ms                      │
         └────────────┬───────────────────────┘
                      │
                      ▼
         ┌────────────────────────────────────┐
         │  Query: qc_passed                   │
         │  ⏱️ +100-200ms                      │
         └────────────┬───────────────────────┘
                      │
                      ▼
         ┌────────────────────────────────────┐
         │  Python: Calculate metrics          │
         │  - Cost per item                    │
         │  - Utilization rates                │
         │  - Daily averages                   │
         │  - Top performers                   │
         │  ⏱️ +50-100ms                       │
         └────────────┬───────────────────────┘
                      │
                      ▼
              ⏱️ 2000-5000ms total backend
                      │
                      ▼
         ┌────────────────────────────────────┐
         │  Serialize ~400KB JSON              │
         │  ⏱️ +50ms                           │
         └────────────┬───────────────────────┘
                      │
                      ▼
              ⏱️ 100-300ms - Network transfer
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND: Parse JSON                                            │
│  ⏱️ +50-100ms                                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
         ┌───────────────────┴────────────────────┐
         │                                        │
         ▼                                        ▼
┌──────────────────┐                    ┌──────────────────┐
│ updateCost       │                    │ updateCostTable  │
│ Metrics()        │                    │ ()               │
│                  │                    │                  │
│ Update 6 cards   │                    │ Render 50+ rows  │
│ ⏱️ 10ms          │                    │ Complex HTML     │
└──────────────────┘                    │ ⏱️ 100-300ms     │
                                        └──────────────────┘
         │                                        │
         ▼                                        ▼
┌──────────────────┐                    ┌──────────────────┐
│ updateDept       │                    │ updateCost       │
│ Costs()          │                    │ Champions()      │
│ ⏱️ 20ms          │                    │ ⏱️ 10ms          │
└──────────────────┘                    └──────────────────┘
         │                                        │
         └────────────────┬───────────────────────┘
                          │
                          ▼
                 ⏱️ 150-400ms rendering
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    USER SEES DATA                                │
│              TOTAL TIME: 2500-5500ms                             │
│           (2.5 - 5.5 SECONDS OF BLANK SCREEN)                    │
└─────────────────────────────────────────────────────────────────┘


TOTAL DATABASE QUERIES: 23-53
TOTAL NETWORK CALLS: 1
CACHE HIT RATE: ~10-20% (30s TTL, varying params)
USER FEEDBACK: NONE until complete
FAILURE MODE: Timeout after 30-120s (browser default)
```

---

## Recommended Architecture (Optimized)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER CLICKS TAB                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  showSection('cost')                                             │
│  ├─ Check client cache (5min TTL)                                │
│  ├─ Show loading skeleton UI                                     │
│  └─ Call loadCostAnalysisData()                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ⏱️ 0ms - User sees skeleton
                             │
              ┌──────────────┴──────────────┐
              │                             │
      Cache HIT? (30-40%)          Cache MISS? (60-70%)
              │                             │
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────────────┐
    │ Return cached    │         │ Fetch from API           │
    │ data immediately │         │ (with 10s timeout)       │
    │ ⏱️ <10ms         │         └──────────┬───────────────┘
    └────────┬─────────┘                    │
             │                              ▼
             │                    ┌──────────────────────────┐
             │                    │ PARALLEL REQUESTS:       │
             │                    │                          │
             │              ┌─────┼─ /cost-summary           │
             │              │     │    ⏱️ 200-500ms          │
             │              │     │    (Basic metrics only)  │
             │              │     │                          │
             │              └─────┼─ /cost-details           │
             │                    │    ⏱️ 1000-2000ms        │
             │                    │    (Full employee data)  │
             │                    └──────────┬───────────────┘
             │                               │
             └───────────────────────────────┘
                                  ▼
                         ⏱️ 200-500ms - Summary arrives
                                  │
                                  ▼
         ┌────────────────────────────────────────────┐
         │  Update Metrics Cards                      │
         │  - Show summary immediately                │
         │  - Table shows skeleton with row count     │
         │  ⏱️ User sees partial data at 200-500ms    │
         └────────────────┬───────────────────────────┘
                          │
                          ▼
                 ⏱️ +500-1500ms - Details arrive
                          │
                          ▼
         ┌────────────────────────────────────────────┐
         │  Update Table (Virtual Scrolling)          │
         │  - Render only visible rows (~10-15)       │
         │  - Lazy load on scroll                     │
         │  ⏱️ +50-100ms                              │
         └────────────────┬───────────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────────┐
         │  Update Charts & Champions                 │
         │  ⏱️ +20ms                                  │
         └────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FULLY INTERACTIVE                             │
│        PERCEIVED TIME: 200-500ms (with cache: <10ms)             │
│        TOTAL TIME: 700-2100ms (with cache: 10ms)                 │
└─────────────────────────────────────────────────────────────────┘


TOTAL DATABASE QUERIES: 3-4 (optimized joins)
TOTAL NETWORK CALLS: 1-2 (summary + details)
CACHE HIT RATE: ~30-40% (5min TTL client + 5min TTL server)
USER FEEDBACK: Immediate (skeleton, progressive loading)
FAILURE MODE: 10s timeout with retry button
```

---

## Backend Query Optimization

### Before (N+1 Pattern)

```
Main Query (employee_hours + employee_activities)
    ⏱️ 1000-1500ms
    Returns 20-50 employees

FOR EACH employee (20-50 iterations):
    Query activity_breakdown
    ⏱️ 30-50ms each
    = 600-2500ms total

Query department_costs
    ⏱️ 200-400ms

Query qc_passed
    ⏱️ 100-200ms

TOTAL: 1900-4600ms
QUERIES: 23-53
```

### After (Optimized JOIN)

```
Single Query with 3 CTEs:
    ├─ employee_hours
    ├─ employee_activities
    └─ activity_breakdown (ALL employees, grouped)
        GROUP BY employee_id, activity_type

Main SELECT:
    JOIN all CTEs
    Pivot activity_breakdown

    ⏱️ 400-800ms

Query department_costs (unchanged)
    ⏱️ 200-400ms

Query qc_passed (unchanged)
    ⏱️ 100-200ms

TOTAL: 700-1400ms (50-70% faster)
QUERIES: 3
```

---

## Progressive Loading Flow

```
Tab Click
    │
    ├─ Show skeleton UI (0ms)
    │
    ├─ Check cache
    │   └─ If HIT: render immediately
    │
    └─ If MISS:
        │
        ├─ Phase 1: Summary (200-500ms)
        │   ├─ Total labor cost
        │   ├─ Total items
        │   ├─ Avg cost per item
        │   ├─ Utilization %
        │   └─ Update metric cards
        │       ⏱️ User sees useful data
        │
        ├─ Phase 2: Table Data (parallel, 1-2s)
        │   ├─ Load in background
        │   ├─ Show loading spinner on table
        │   └─ When ready:
        │       ├─ Virtual scroller initializes
        │       ├─ Render visible rows only
        │       └─ Lazy load on scroll
        │           ⏱️ Smooth, responsive
        │
        └─ Phase 3: Charts (parallel, 1-2s)
            ├─ Department breakdown
            ├─ Top performers
            └─ Update charts
                ⏱️ Complete picture
```

---

## Timeout & Retry Strategy

```
User Action
    │
    ├─ API Call with AbortController
    │   ├─ Timeout: 10 seconds
    │   └─ If timeout:
    │       ├─ Show friendly error:
    │       │   "Request is taking longer than usual.
    │       │    This might be due to large dataset."
    │       │
    │       ├─ Options:
    │       │   [Retry] [Use Smaller Date Range]
    │       │
    │       └─ Track retry count (max 3)
    │
    ├─ If network error:
    │   └─ Show offline message
    │       "Unable to connect. Check your network."
    │       [Retry]
    │
    └─ If server error (500):
        └─ Show technical error
            "Server error. Our team has been notified."
            [Report Issue]
```

---

## Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT CACHE                             │
│                                                              │
│  Map<dateRange, data>                                        │
│  TTL: 5 minutes                                              │
│  Max Size: 20 entries                                        │
│  Eviction: LRU                                               │
│                                                              │
│  Example:                                                    │
│  "2025-08-14_2025-08-14" → { data, timestamp }              │
│  "2025-08-01_2025-08-14" → { data, timestamp }              │
│                                                              │
│  Hit Rate: ~30-40% (users switch tabs, re-check data)       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼ (cache miss)
┌─────────────────────────────────────────────────────────────┐
│                     NETWORK REQUEST                          │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     SERVER CACHE (Flask)                     │
│                                                              │
│  @cached_endpoint(ttl_seconds=300)  # 5 min                 │
│  Key: request.full_path (includes all params)               │
│                                                              │
│  Hit Rate: ~20-30% (lower due to varying params)            │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼ (cache miss)
┌─────────────────────────────────────────────────────────────┐
│                     DATABASE QUERY                           │
│                                                              │
│  If date in past (historical):                              │
│    Cache for 24 hours (immutable data)                      │
│                                                              │
│  If date is today:                                           │
│    Cache for 5 minutes (changing data)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Virtual Scrolling Implementation

```
┌────────────────────────────────────────────────────┐
│  Cost Analysis Table                               │
│  Total Rows: 50                                    │
│  Visible Area: 10 rows                             │
├────────────────────────────────────────────────────┤
│  [Virtual Buffer Top]                              │
│  - Not rendered (just spacer div)                  │
│  - Height: rowHeight × topRowCount                 │
│                                                    │
├────────────────────────────────────────────────────┤
│  Row 15 | John Doe    | $120  | 200 items | ...   │  ← Rendered
│  Row 16 | Jane Smith  | $115  | 180 items | ...   │  ← Rendered
│  Row 17 | Bob Jones   | $110  | 190 items | ...   │  ← Rendered
│  Row 18 | Alice Wong  | $108  | 195 items | ...   │  ← Rendered
│  Row 19 | ...                                      │  ← Rendered
│  Row 20 | ...                                      │  ← Rendered
│  Row 21 | ...                                      │  ← Rendered
│  Row 22 | ...                                      │  ← Rendered
│  Row 23 | ...                                      │  ← Rendered
│  Row 24 | ...                                      │  ← Rendered
├────────────────────────────────────────────────────┤
│  [Virtual Buffer Bottom]                           │
│  - Not rendered (just spacer div)                  │
│  - Height: rowHeight × bottomRowCount              │
│                                                    │
└────────────────────────────────────────────────────┘
      ▲
      │
      └─ On Scroll: Recalculate visible range
         - Destroy old rows
         - Render new rows
         - Update buffer heights
         ⏱️ 16ms (60fps smooth scrolling)

Performance:
- DOM nodes: 10-15 (constant)
- Memory: O(visible rows) not O(total rows)
- Initial render: 50ms
- Scroll performance: 60fps
```

---

**End of Diagrams**
