# Code Review Report: Schedule API Performance Analysis

**Date**: 2025-12-13
**Reviewer**: Code Review Agent
**Focus**: Backend Schedule API Performance Issues

---

## Code Review Summary

### Scope
- Files reviewed:
  - `backend/api/schedule.py` (682 lines)
  - `backend/database/db_manager.py` (140 lines)
- Review focus: Performance issues in save-draft and publish endpoints
- Lines analyzed: ~822 LOC

### Overall Assessment

Found **CRITICAL performance bottleneck** in `publish_schedule()` endpoint with N+1 query pattern. The `save_draft()` endpoint correctly uses batch insert, but publish endpoint does not. Additionally, both endpoints missing transaction management for multi-statement operations.

---

## Critical Issues

### 1. **N+1 Query Problem in `publish_schedule()` (Lines 83-100)**

**Severity**: CRITICAL
**Impact**: For 100 shifts, executes 100 individual INSERT queries instead of 1 batch query. Causes severe performance degradation with large schedules.

**Current Code (SLOW):**
```python
# Insert shifts
shift_count = 0
for station_id, dates in schedule_data.items():
    for date_str, shifts in dates.items():
        for shift in shifts:
            db.execute_query("""
                INSERT INTO published_shifts
                (schedule_id, employee_id, shift_date, station, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                schedule_id,
                shift.get('employee_id'),
                date_str,
                station_id,
                shift.get('start_time', '06:00'),
                shift.get('end_time', '14:30')
            ))
            shift_count += 1
```

**Problem**: Each iteration calls `db.execute_query()` which:
- Gets new cursor
- Executes single INSERT
- Commits immediately
- Total: 100 DB round-trips for 100 shifts

**Recommended Fix:**
```python
# Collect all shifts for batch insert
shift_values = []
for station_id, dates in schedule_data.items():
    for date_str, shifts in dates.items():
        for shift in shifts:
            shift_values.append((
                schedule_id,
                shift.get('employee_id'),
                date_str,
                station_id,
                shift.get('start_time', '06:00'),
                shift.get('end_time', '14:30')
            ))

# Batch insert all shifts in one query
if shift_values:
    db.execute_many("""
        INSERT INTO published_shifts
        (schedule_id, employee_id, shift_date, station, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, shift_values)

shift_count = len(shift_values)
```

**Performance Gain**: 100x reduction in DB operations (1 query vs 100 queries)

---

## High Priority Findings

### 2. **Missing Transaction Boundaries (Lines 15-111, 114-213)**

**Severity**: HIGH
**Impact**: Data inconsistency if partial failures occur. No rollback on errors during multi-step operations.

**Problem**: Both `publish_schedule()` and `save_draft()` perform multiple DB operations:
1. Check existing schedule
2. Delete old shifts (if exists)
3. Update/Insert schedule record
4. Validate employees
5. Insert new shifts

Current implementation commits after each step. If step 5 fails, steps 1-4 already committed → inconsistent state.

**Current Code Pattern:**
```python
# Each execute_query/execute_update auto-commits
existing = db.execute_one(...)  # Auto-commit
db.execute_query("DELETE...")    # Auto-commit
db.execute_query("UPDATE...")    # Auto-commit
db.execute_many(...)             # Auto-commit
```

**Recommended Fix:**
```python
@schedule_bp.route('/api/schedule/publish', methods=['POST'])
def publish_schedule():
    try:
        data = request.json
        week_start = data.get('week_start')
        schedule_data = data.get('schedule', {})

        if not week_start:
            return jsonify({'success': False, 'message': 'week_start required'}), 400

        db = get_db()

        # Use connection context for transaction
        with db.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            try:
                # Check if schedule exists
                cursor.execute("""
                    SELECT id FROM published_schedules WHERE week_start_date = %s
                """, (week_start,))
                existing = cursor.fetchone()

                if existing:
                    # Delete old shifts
                    cursor.execute("""
                        DELETE FROM published_shifts WHERE schedule_id = %s
                    """, (existing['id'],))
                    schedule_id = existing['id']

                    # Update status
                    cursor.execute("""
                        UPDATE published_schedules
                        SET status = 'published', updated_at = NOW()
                        WHERE id = %s
                    """, (schedule_id,))
                else:
                    # Create new schedule
                    cursor.execute("""
                        INSERT INTO published_schedules (week_start_date, status, created_by)
                        VALUES (%s, 'published', 'Manager')
                    """, (week_start,))

                    cursor.execute("""
                        SELECT id FROM published_schedules WHERE week_start_date = %s
                    """, (week_start,))
                    result = cursor.fetchone()
                    schedule_id = result['id']

                # Validate employees (optimization: single query)
                all_employee_ids = set()
                for station_id, dates in schedule_data.items():
                    for date_str, shifts in dates.items():
                        for shift in shifts:
                            if shift.get('employee_id'):
                                all_employee_ids.add(shift.get('employee_id'))

                if all_employee_ids:
                    placeholders = ','.join(['%s'] * len(all_employee_ids))
                    cursor.execute(f"""
                        SELECT id FROM employees WHERE id IN ({placeholders})
                    """, tuple(all_employee_ids))
                    valid_ids = {e['id'] for e in cursor.fetchall()}
                    invalid_ids = all_employee_ids - valid_ids

                    if invalid_ids:
                        conn.rollback()
                        return jsonify({
                            'success': False,
                            'error': f'Invalid employee IDs: {list(invalid_ids)}'
                        }), 400

                # Batch insert shifts
                shift_values = []
                for station_id, dates in schedule_data.items():
                    for date_str, shifts in dates.items():
                        for shift in shifts:
                            shift_values.append((
                                schedule_id,
                                shift.get('employee_id'),
                                date_str,
                                station_id,
                                shift.get('start_time', '06:00'),
                                shift.get('end_time', '14:30')
                            ))

                if shift_values:
                    cursor.executemany("""
                        INSERT INTO published_shifts
                        (schedule_id, employee_id, shift_date, station, start_time, end_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, shift_values)

                # Commit all changes atomically
                conn.commit()

                return jsonify({
                    'success': True,
                    'schedule_id': schedule_id,
                    'shifts_saved': len(shift_values),
                    'message': f'Schedule published with {len(shift_values)} shifts'
                })

            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()

    except Exception as e:
        print(f"Error publishing schedule: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Benefits**:
- All-or-nothing operation (atomic)
- Rollback on any failure
- Data consistency guaranteed

---

### 3. **Inefficient Connection Reuse (Multiple Endpoints)**

**Severity**: MEDIUM-HIGH
**Impact**: Creating new DB connections for each `get_db()` call wastes resources.

**Problem**: Lines 26, 125, 220, 282, 546, 593, 642 all call `get_db()` which returns singleton manager but each query gets new cursor unnecessarily.

**Current Pattern:**
```python
db = get_db()
result1 = db.execute_one(query1)  # Gets cursor, commits, closes
result2 = db.execute_query(query2) # Gets cursor, commits, closes
db.execute_update(query3)         # Gets cursor, commits, closes
```

**Issue**: 3 separate cursor acquisitions instead of reusing connection.

**Better Pattern (Already shown in transaction fix above):**
Use `with db.get_connection()` context manager to reuse connection across multiple operations.

---

### 4. **Unnecessary Query in Schedule Creation (Lines 48-57, 147-156)**

**Severity**: MEDIUM
**Impact**: Extra DB round-trip after INSERT to fetch generated ID.

**Current Code:**
```python
# Insert new schedule
db.execute_query("""
    INSERT INTO published_schedules (week_start_date, status, created_by)
    VALUES (%s, 'published', 'Manager')
""", (week_start,))

# Fetch the schedule_id by week_start_date (unique)
result = db.execute_one("""
    SELECT id FROM published_schedules WHERE week_start_date = %s
""", (week_start,))
schedule_id = result['id']
```

**Problem**: `execute_query()` doesn't return lastrowid. Need to query again.

**Recommended Fix:**
```python
# Use execute_update which returns lastrowid
schedule_id = db.execute_update("""
    INSERT INTO published_schedules (week_start_date, status, created_by)
    VALUES (%s, 'published', 'Manager')
""", (week_start,))
```

**Note**: This already works correctly in `save_schedule()` line 405. Apply same pattern to publish/draft endpoints.

---

## Medium Priority Improvements

### 5. **Missing Index Recommendations**

**Severity**: MEDIUM
**Impact**: Query performance degradation as data grows.

**Recommended Indexes:**
```sql
-- For schedule lookups by week
CREATE INDEX idx_published_schedules_week
ON published_schedules(week_start_date, status);

-- For shift queries by schedule
CREATE INDEX idx_published_shifts_schedule
ON published_shifts(schedule_id, shift_date);

-- For employee schedule lookups
CREATE INDEX idx_published_shifts_employee
ON published_shifts(employee_id, shift_date);

-- For shift joins (if not already exists)
CREATE INDEX idx_published_shifts_station
ON published_shifts(station, shift_date);
```

**Verify Existing Indexes:**
```sql
SHOW INDEX FROM published_schedules;
SHOW INDEX FROM published_shifts;
```

---

### 6. **Error Handling Lacks Specificity (Lines 109-111, 212-213)**

**Severity**: MEDIUM
**Impact**: Generic error handling makes debugging difficult.

**Current Code:**
```python
except Exception as e:
    print(f"Error publishing schedule: {str(e)}")
    return jsonify({'success': False, 'error': str(e)}), 500
```

**Issue**: Catches all exceptions, exposes internal errors to client.

**Recommended Fix:**
```python
except ValueError as e:
    # Client error (validation)
    return jsonify({'success': False, 'error': str(e)}), 400
except mysql.connector.Error as e:
    # Database error
    logger.error(f"Database error publishing schedule: {str(e)}")
    return jsonify({'success': False, 'error': 'Database error occurred'}), 500
except Exception as e:
    # Unexpected error
    logger.exception(f"Unexpected error publishing schedule: {str(e)}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

### 7. **Redundant Employee Validation Query (Lines 168-180)**

**Severity**: LOW-MEDIUM
**Impact**: Minor performance overhead.

**Observation**: `save_draft()` validates employees exist before inserting shifts. Good practice, but consider:
- If employee deleted between validation and insert, FK constraint will catch it
- Validation query adds overhead

**Options**:
1. Keep validation for better error messages (current approach - OK)
2. Rely on FK constraint, catch `IntegrityError` for faster path
3. Use `INSERT IGNORE` or `ON DUPLICATE KEY UPDATE` patterns

**Current approach is acceptable** for user experience, but note this adds 1 extra query per save operation.

---

## Low Priority Suggestions

### 8. **Magic Numbers for Default Times (Lines 97-98, 193-194)**

**Severity**: LOW
**Impact**: Maintainability.

**Current Code:**
```python
shift.get('start_time', '06:00'),
shift.get('end_time', '14:30')
```

**Suggestion**: Extract to module-level constants:
```python
DEFAULT_SHIFT_START = '06:00'
DEFAULT_SHIFT_END = '14:30'
```

---

### 9. **Inconsistent `db` Retrieval Pattern**

**Severity**: LOW
**Impact**: Code consistency.

**Observation**: Some endpoints call `db = get_db()` at start, others inline. Standardize for readability.

**Preferred Pattern:**
```python
@schedule_bp.route('/api/endpoint', methods=['POST'])
def endpoint():
    try:
        data = request.json
        # ... validation ...

        db = get_db()  # Always early in function
        # ... use db ...
```

---

### 10. **Missing Query Parameter Logging**

**Severity**: LOW
**Impact**: Debugging difficulty.

**Suggestion**: Add query logging for slow query analysis:
```python
import time

def execute_query_with_timing(db, query, params):
    start = time.time()
    result = db.execute_query(query, params)
    duration = time.time() - start
    if duration > 1.0:  # Log slow queries
        logger.warning(f"Slow query ({duration:.2f}s): {query[:100]}")
    return result
```

---

## Positive Observations

1. **`save_draft()` correctly uses batch insert** (lines 182-202) - Good pattern!
2. **Connection pooling in `db_manager.py`** - Excellent design with context managers
3. **Parameterized queries throughout** - Prevents SQL injection
4. **Employee validation** - Good data integrity check before insert
5. **Clear endpoint separation** - draft vs publish logic well organized
6. **Default value handling** - Good use of `.get()` with defaults

---

## Recommended Actions (Prioritized)

### Immediate (Critical - Do First)
1. **Fix N+1 query in `publish_schedule()`** - Change lines 83-100 to batch insert pattern (copy from `save_draft()`)
2. **Add transaction boundaries** - Wrap multi-step operations in `with db.get_connection()` context

### Short-term (High Priority - This Week)
3. **Use `execute_update()` for INSERT with lastrowid** - Eliminate extra SELECT after INSERT (lines 48-57, 147-156)
4. **Add database indexes** - Run recommended index creation queries
5. **Improve error handling** - Distinguish DB errors from validation errors

### Medium-term (Next Sprint)
6. **Add query performance logging** - Track slow queries
7. **Extract magic constants** - DEFAULT_SHIFT_START/END
8. **Standardize db retrieval pattern** - Consistent placement of `db = get_db()`

### Nice-to-have
9. **Add integration tests** - Test transaction rollback scenarios
10. **Add query metrics** - Track query counts per endpoint

---

## Performance Impact Estimates

### Before Optimization (100-shift schedule publish):
- **Queries**: ~103 (1 check + 1 update + 1 select + 100 inserts)
- **Time**: ~500-1000ms (depends on network latency)
- **Commits**: 103

### After Optimization (100-shift schedule publish):
- **Queries**: ~4 (1 check + 1 update + 1 validation + 1 batch insert)
- **Time**: ~50-100ms
- **Commits**: 1
- **Speedup**: **10-20x faster**

---

## Database Schema Assumptions

Based on code analysis, assumed schema:
```sql
CREATE TABLE published_schedules (
    id INT PRIMARY KEY AUTO_INCREMENT,
    week_start_date DATE UNIQUE,
    status ENUM('draft', 'published'),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE published_shifts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    schedule_id INT,
    employee_id INT,
    shift_date DATE,
    station VARCHAR(50),
    start_time TIME,
    end_time TIME,
    FOREIGN KEY (schedule_id) REFERENCES published_schedules(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

**Verify indexes exist** on foreign keys and frequently queried columns.

---

## Unresolved Questions

1. **Are there indexes on `published_schedules.week_start_date` and `published_shifts.schedule_id`?**
   - Query: `SHOW INDEX FROM published_schedules;`

2. **What is typical schedule size?** (Number of shifts per week)
   - Affects batch insert optimization priority

3. **Is there concurrent schedule editing?**
   - May need optimistic locking (version field)

4. **Are there foreign key constraints on `published_shifts.employee_id`?**
   - Affects whether validation query is redundant

5. **What is `autocommit` setting in production?**
   - Check `db_manager.py` line 31: currently `autocommit=False` (good)

---

## Metrics

- **Total Endpoints Reviewed**: 10
- **Critical Issues**: 1 (N+1 query)
- **High Priority**: 3 (transactions, connection reuse, unnecessary queries)
- **Medium Priority**: 4 (indexes, error handling, validation optimization, constants)
- **Low Priority**: 3 (magic numbers, consistency, logging)
- **Positive Patterns**: 6

---

## Summary

**Main bottleneck**: `publish_schedule()` uses individual INSERTs instead of batch insert. Fix reduces 100 queries to 1.

**Critical missing**: Transaction boundaries leave data vulnerable to partial failures.

**Quick wins**:
1. Copy batch insert pattern from `save_draft()` to `publish_schedule()`
2. Use `execute_update()` to get lastrowid instead of SELECT after INSERT
3. Wrap operations in transaction context manager

**Estimated total improvement**: 10-20x faster schedule publishing with proper data consistency guarantees.
