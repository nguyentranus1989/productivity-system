"""Test cost summary query directly."""
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

# Test the exact query the API uses
employee_query = """
SELECT
    employee_id as id,
    employee_name as name,
    MAX(hourly_rate) as hourly_rate,
    SUM(clocked_hours) as clocked_hours,
    SUM(total_cost) as total_cost,
    SUM(total_items) as items_processed,
    COUNT(DISTINCT summary_date) as days_worked
FROM daily_cost_summary
WHERE summary_date BETWEEN %s AND %s
GROUP BY employee_id, employee_name
ORDER BY employee_name
"""

start_date = '2025-12-01'
end_date = '2025-12-01'

cursor.execute(employee_query, (start_date, end_date))
results = cursor.fetchall()

print(f"Query returned {len(results)} employees")
for emp in results[:5]:  # First 5
    print(f"  {emp['name']}: {emp['clocked_hours']} hrs, ${emp['total_cost']}")

cursor.close()
conn.close()
