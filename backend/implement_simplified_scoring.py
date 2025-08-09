import mysql.connector
from datetime import datetime, date

# Database connection
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='Nicholasbin0116$',
    database='productivity_tracker'
)
cursor = conn.cursor(dictionary=True)

print("=== Implementing Simplified Scoring System ===\n")

# Step 1: Fix duration minutes to 10
print("1. Fixing duration minutes...")
cursor.execute("""
    UPDATE activity_logs 
    SET duration_minutes = 10 
    WHERE source = 'podfactory' 
    AND duration_minutes = 9
""")
print(f"   ✓ Updated {cursor.rowcount} records to 10 minutes\n")

# Step 2: Recalculate all daily scores with simplified formula
print("2. Recalculating daily scores with simplified formula...")

# Get today's date
today = date.today()

# Clear and recalculate
cursor.execute("""
    INSERT INTO daily_scores (employee_id, score_date, items_processed, points_earned, active_minutes, clocked_minutes, efficiency_rate)
    SELECT 
        al.employee_id,
        %s as score_date,
        SUM(al.items_count) as items_processed,
        ROUND(SUM(al.items_count * rc.multiplier), 2) as points_earned,
        0 as active_minutes,  -- Not used anymore
        COALESCE(
            TIMESTAMPDIFF(MINUTE, 
                MIN(ct.clock_in), 
                COALESCE(MAX(ct.clock_out), NOW())
            ), 0
        ) as clocked_minutes,
        0 as efficiency_rate  -- Not used anymore
    FROM activity_logs al
    JOIN employees e ON e.id = al.employee_id
    JOIN role_configs rc ON rc.id = e.role_id
    LEFT JOIN clock_times ct ON ct.employee_id = al.employee_id 
        AND DATE(ct.clock_in) = %s
    WHERE DATE(al.window_start) = %s
    AND al.source = 'podfactory'
    GROUP BY al.employee_id
    ON DUPLICATE KEY UPDATE
        items_processed = VALUES(items_processed),
        points_earned = VALUES(points_earned),
        clocked_minutes = VALUES(clocked_minutes),
        active_minutes = 0,
        efficiency_rate = 0,
        updated_at = NOW()
""", (today, today, today))

print(f"   ✓ Updated scores for {cursor.rowcount} employees\n")

# Step 3: Show the new leaderboard
print("3. Today's Leaderboard (Simplified Scoring):\n")
print(f"{'Rank':<5} {'Name':<20} {'Role':<20} {'Items':<8} {'Points':<8} {'Hours':<6}")
print("-" * 75)

cursor.execute("""
    SELECT 
        e.name,
        rc.role_name,
        ds.items_processed,
        ds.points_earned,
        ROUND(ds.clocked_minutes / 60, 1) as hours_worked,
        ROW_NUMBER() OVER (ORDER BY ds.points_earned DESC) as ranking
    FROM daily_scores ds
    JOIN employees e ON e.id = ds.employee_id
    JOIN role_configs rc ON rc.id = e.role_id
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
    
    print(f"{rank_display:<5} {row['name']:<20} {row['role_name']:<20} {row['items_processed']:<8} {row['points_earned']:<8.1f} {row['hours_worked']:<6.1f}")

# Step 4: Department Summary
print("\n\n4. Department Summary:\n")

cursor.execute("""
    SELECT 
        al.department,
        COUNT(DISTINCT al.employee_id) as workers,
        SUM(al.items_count) as total_items,
        ROUND(SUM(al.items_count * rc.multiplier), 1) as total_points
    FROM activity_logs al
    JOIN employees e ON e.id = al.employee_id
    JOIN role_configs rc ON rc.id = e.role_id
    WHERE DATE(al.window_start) = %s
    AND al.source = 'podfactory'
    GROUP BY al.department
    ORDER BY total_points DESC
""", (today,))

print(f"{'Department':<15} {'Workers':<10} {'Items':<10} {'Points':<10}")
print("-" * 50)

for dept in cursor.fetchall():
    print(f"{dept['department']:<15} {dept['workers']:<10} {dept['total_items']:<10} {dept['total_points']:<10.1f}")

# Step 5: Show role performance
print("\n\n5. Performance by Role:\n")

cursor.execute("""
    SELECT 
        rc.role_name,
        rc.multiplier,
        COUNT(DISTINCT al.employee_id) as workers,
        SUM(al.items_count) as total_items,
        ROUND(AVG(al.items_count), 1) as avg_items_per_worker,
        ROUND(SUM(al.items_count * rc.multiplier), 1) as total_points
    FROM activity_logs al
    JOIN employees e ON e.id = al.employee_id
    JOIN role_configs rc ON rc.id = e.role_id
    WHERE DATE(al.window_start) = %s
    AND al.source = 'podfactory'
    GROUP BY rc.id, rc.role_name, rc.multiplier
    ORDER BY total_points DESC
""", (today,))

print(f"{'Role':<20} {'Multi':<6} {'Workers':<8} {'Items':<8} {'Avg/Worker':<12} {'Points':<8}")
print("-" * 70)

for role in cursor.fetchall():
    print(f"{role['role_name']:<20} {role['multiplier']:<6} {role['workers']:<8} {role['total_items']:<8} {role['avg_items_per_worker']:<12.1f} {role['total_points']:<8.1f}")

conn.commit()
cursor.close()
conn.close()

print("\n\n✅ Simplified scoring system implemented successfully!")
print("\nNext steps:")
print("1. Update dashboard queries to use points_earned instead of efficiency calculations")
print("2. Update frontend to show simplified metrics")
print("3. Add gamification features")