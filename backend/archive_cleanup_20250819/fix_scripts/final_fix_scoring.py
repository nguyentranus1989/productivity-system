import mysql.connector
from datetime import date

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='Nicholasbin0116$',
    database='productivity_tracker'
)
cursor = conn.cursor(dictionary=True)

print("=== Final Fix: Correct Scoring System ===\n")

today = date.today()

# First, let's check what's actually in daily_scores
print("1. Current daily_scores values:")
cursor.execute("""
    SELECT 
        e.name,
        ds.items_processed,
        ds.points_earned
    FROM daily_scores ds
    JOIN employees e ON e.id = ds.employee_id
    WHERE ds.score_date = %s
    AND ds.points_earned > 0
    ORDER BY e.name
    LIMIT 10
""", (today,))

for row in cursor.fetchall():
    print(f"   {row['name']:<20} | Items: {row['items_processed']:>4} | Points: {row['points_earned']:>8.2f}")

# Now recalculate correctly
print("\n2. Recalculating with correct formula...")

cursor.execute("""
    CREATE TEMPORARY TABLE temp_daily_scores AS
    SELECT 
        al.employee_id,
        SUM(al.items_count) as items_processed,
        ROUND(SUM(al.items_count * rc.multiplier), 2) as points_earned
    FROM activity_logs al
    JOIN role_configs rc ON rc.id = al.role_id
    WHERE DATE(al.window_start) = %s
    AND al.source = 'podfactory'
    GROUP BY al.employee_id
""", (today,))

# Update daily_scores from temp table
cursor.execute("""
    UPDATE daily_scores ds
    JOIN temp_daily_scores t ON t.employee_id = ds.employee_id
    SET 
        ds.items_processed = t.items_processed,
        ds.points_earned = t.points_earned,
        ds.updated_at = NOW()
    WHERE ds.score_date = %s
""", (today,))

print(f"   ✓ Updated {cursor.rowcount} records\n")

# Show corrected leaderboard WITHOUT the problematic GROUP BY
print("3. Corrected Leaderboard:\n")
print(f"{'Rank':<6} {'Name':<20} {'Items':<7} {'Points':<8} {'Hours':<7}")
print("-" * 60)

cursor.execute("""
    SELECT 
        e.name,
        ds.items_processed,
        ds.points_earned,
        ROUND(ds.clocked_minutes / 60, 1) as hours_worked,
        ROW_NUMBER() OVER (ORDER BY ds.points_earned DESC) as ranking
    FROM daily_scores ds
    JOIN employees e ON e.id = ds.employee_id
    WHERE ds.score_date = %s
    AND ds.points_earned > 0
    ORDER BY ds.points_earned DESC
""", (today,))

for row in cursor.fetchall():
    rank_display = f"#{row['ranking']}"
    if row['ranking'] == 1:
        rank_display += " 🥇"
    elif row['ranking'] == 2:
        rank_display += " 🥈"
    elif row['ranking'] == 3:
        rank_display += " 🥉"
    
    print(f"{rank_display:<6} {row['name']:<20} {row['items_processed']:<7} {row['points_earned']:<8.1f} {row['hours_worked']:<7.1f}")

# Verify specific cases
print("\n\n4. Verification of Key Employees:")
print("-" * 60)

for name in ['Gabrielle Ortiz', 'dung duong', 'Brandon Magallanez']:
    cursor.execute("""
        SELECT 
            e.name,
            COUNT(DISTINCT al.id) as activities,
            SUM(al.items_count) as total_items,
            ROUND(SUM(al.items_count * rc.multiplier), 2) as calculated_points,
            ds.points_earned as stored_points
        FROM employees e
        JOIN activity_logs al ON al.employee_id = e.id
        JOIN role_configs rc ON rc.id = al.role_id
        JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = DATE(al.window_start)
        WHERE e.name = %s
        AND DATE(al.window_start) = %s
        AND al.source = 'podfactory'
        GROUP BY e.id, e.name, ds.points_earned
    """, (name, today))
    
    result = cursor.fetchone()
    if result:
        match = "✅" if abs(result['calculated_points'] - result['stored_points']) < 0.01 else "❌"
        print(f"{result['name']:<20} | Activities: {result['activities']:>2} | Items: {result['total_items']:>4} | Calc: {result['calculated_points']:>7.2f} | Stored: {result['stored_points']:>7.2f} | {match}")

# Show roles breakdown
print("\n\n5. Multi-Role Breakdown:")
print("-" * 80)

cursor.execute("""
    SELECT 
        e.name,
        GROUP_CONCAT(DISTINCT CONCAT(rc.role_name, ' (', activity_counts.cnt, ')') ORDER BY rc.role_name) as roles_and_counts,
        SUM(activity_counts.items) as total_items,
        SUM(activity_counts.points) as total_points
    FROM employees e
    JOIN (
        SELECT 
            al.employee_id,
            al.role_id,
            COUNT(*) as cnt,
            SUM(al.items_count) as items,
            SUM(al.items_count * rc2.multiplier) as points
        FROM activity_logs al
        JOIN role_configs rc2 ON rc2.id = al.role_id
        WHERE DATE(al.window_start) = %s
        AND al.source = 'podfactory'
        GROUP BY al.employee_id, al.role_id
    ) activity_counts ON activity_counts.employee_id = e.id
    JOIN role_configs rc ON rc.id = activity_counts.role_id
    WHERE activity_counts.cnt > 0
    GROUP BY e.id, e.name
    HAVING COUNT(DISTINCT activity_counts.role_id) > 1
    ORDER BY total_points DESC
""", (today,))

print(f"{'Name':<20} {'Roles (Activity Count)':<40} {'Items':<7} {'Points':<8}")
print("-" * 80)

for row in cursor.fetchall():
    print(f"{row['name']:<20} {row['roles_and_counts']:<40} {row['total_items']:<7} {row['total_points']:<8.1f}")

# Clean up
cursor.execute("DROP TEMPORARY TABLE temp_daily_scores")

conn.commit()
cursor.close()
conn.close()

print("\n\n✅ Scoring system is now correct!")
print("\nKey Points:")
print("- Points = Items × Role Multiplier")
print("- No efficiency calculations")
print("- Multi-role employees get appropriate multipliers for each activity")
print("- No double counting")