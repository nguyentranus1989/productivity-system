"""Check cost summary table for Dec 1 data."""
import pymysql
from dotenv import load_dotenv
import sys
sys.path.insert(0, 'C:/Users/12104/Projects/Productivity_system/backend')
load_dotenv('C:/Users/12104/Projects/Productivity_system/backend/.env')
from config import config

conn = pymysql.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME,
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

# Check Dec 1 summary
cursor.execute("""
    SELECT COUNT(*) as cnt, SUM(clocked_hours) as total_hours
    FROM daily_cost_summary
    WHERE summary_date = '2025-12-01'
""")
result = cursor.fetchone()
print(f"Dec 1 cost summary records: {result['cnt']}, total hours: {result['total_hours']}")

# Check Adrianna specifically
cursor.execute("""
    SELECT e.name, dcs.clocked_hours, dcs.total_cost
    FROM daily_cost_summary dcs
    JOIN employees e ON dcs.employee_id = e.id
    WHERE dcs.summary_date = '2025-12-01'
    AND e.name LIKE '%Adrianna%'
""")
adrianna = cursor.fetchone()
if adrianna:
    print(f"Adrianna: {adrianna['clocked_hours']} hours, ${adrianna['total_cost']}")
else:
    print("Adrianna not found in cost summary for Dec 1")

# Check if table has any data at all
cursor.execute("SELECT COUNT(*) as cnt FROM daily_cost_summary")
total = cursor.fetchone()
print(f"Total records in daily_cost_summary: {total['cnt']}")

# Check recent dates
cursor.execute("""
    SELECT summary_date, COUNT(*) as cnt, SUM(clocked_hours) as total_hours
    FROM daily_cost_summary
    GROUP BY summary_date
    ORDER BY summary_date DESC
    LIMIT 5
""")
for row in cursor.fetchall():
    print(f"  {row['summary_date']}: {row['cnt']} records, {row['total_hours']} hours")

cursor.close()
conn.close()
