"""
Create department_targets table and seed with initial values
"""
import sys
sys.path.insert(0, 'C:/Users/12104/Projects/Productivity_system/backend')
import pymysql
from dotenv import load_dotenv
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

# Create table
print('Creating department_targets table...')
cursor.execute("""
    CREATE TABLE IF NOT EXISTS department_targets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        department_name VARCHAR(100) UNIQUE NOT NULL,
        target_rate_per_person DECIMAL(10,2) DEFAULT 15.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
""")

# Insert initial values (from current hardcoded values)
print('Inserting initial targets...')
initial_targets = [
    ('Picking', 20.0),
    ('Packing', 16.0),
    ('Heat Press', 6.0),
    ('Labeling', 20.0),
    ('Film Matching', 15.0),
    ('Unknown', 15.0)
]

for dept, rate in initial_targets:
    cursor.execute("""
        INSERT INTO department_targets (department_name, target_rate_per_person)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE target_rate_per_person = VALUES(target_rate_per_person)
    """, (dept, rate))
    print(f"  {dept}: {rate} items/min/person")

conn.commit()

# Verify
print('\nVerifying...')
cursor.execute("SELECT * FROM department_targets ORDER BY department_name")
for row in cursor.fetchall():
    print(f"  {row['department_name']}: {row['target_rate_per_person']}")

conn.close()
print('\nDone!')
