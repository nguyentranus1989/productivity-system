"""
This shows the SQL change needed in api/dashboard.py to display employees 
even if they haven't clocked in yet
"""

# The current query probably looks like this (showing only clocked-in employees):
OLD_QUERY = """
WHERE e.is_active = 1
AND e.id IN (
    SELECT employee_id FROM clock_times 
    WHERE DATE(clock_in) = %s
)
"""

# Change it to show anyone with activities OR clock times:
NEW_QUERY = """
WHERE e.is_active = 1
AND (
    -- Has clocked in today
    e.id IN (
        SELECT employee_id FROM clock_times 
        WHERE DATE(clock_in) = %s
    )
    OR
    -- Has activities today (even without clocking in)
    e.id IN (
        SELECT employee_id FROM activity_logs 
        WHERE DATE(window_start) = %s
    )
)
"""

print("Update needed in /api/dashboard.py leaderboard endpoint:")
print("Change the WHERE clause to include employees with activities even without clock times")
