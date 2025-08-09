"""Common database queries"""

# Employee queries
GET_EMPLOYEE_BY_EMAIL = """
    SELECT e.*, rc.role_name 
    FROM employees e
    JOIN role_configs rc ON e.role_id = rc.id
    WHERE e.email = %s AND e.is_active = TRUE
"""

GET_ALL_ACTIVE_EMPLOYEES = """
    SELECT e.*, rc.role_name
    FROM employees e
    JOIN role_configs rc ON e.role_id = rc.id
    WHERE e.is_active = TRUE
    ORDER BY e.name
"""

CREATE_EMPLOYEE = """
    INSERT INTO employees (email, name, role_id, hire_date, grace_period_end)
    VALUES (%s, %s, %s, %s, %s)
"""

# Activity queries
INSERT_ACTIVITY = """
    INSERT INTO activity_logs (report_id, employee_id, role_id, items_count, window_start, window_end)
    VALUES (%s, %s, %s, %s, %s, %s)
"""

GET_ACTIVITIES_BY_DATE = """
    SELECT a.*, e.name as employee_name, rc.role_name
    FROM activity_logs a
    JOIN employees e ON a.employee_id = e.id
    JOIN role_configs rc ON a.role_id = rc.id
    WHERE DATE(a.window_start) = %s
    ORDER BY a.window_start
"""

# Daily score queries
GET_OR_CREATE_DAILY_SCORE = """
    INSERT INTO daily_scores (employee_id, score_date, items_processed, active_minutes, 
                             clocked_minutes, efficiency_rate, points_earned)
    VALUES (%s, %s, 0, 0, 0, 0.0, 0.0)
    ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
"""

UPDATE_DAILY_SCORE = """
    UPDATE daily_scores
    SET items_processed = %s, 
        active_minutes = %s,
        clocked_minutes = %s,
        efficiency_rate = %s,
        points_earned = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE employee_id = %s AND score_date = %s
"""

# Role config queries
GET_ALL_ROLES = """
    SELECT * FROM role_configs ORDER BY role_name
"""

GET_ROLE_BY_NAME = """
    SELECT * FROM role_configs WHERE role_name = %s
"""
