"""
Create tables for published schedules feature.
Run this script to set up the database schema.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.db_manager import get_db

def create_tables():
    db = get_db()

    print("Creating published_schedules table...")
    try:
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS published_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                week_start_date DATE NOT NULL UNIQUE,
                status ENUM('draft', 'published', 'sent') DEFAULT 'published',
                created_by VARCHAR(100) DEFAULT 'Manager',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_week_start (week_start_date)
            )
        """)
        print("  [OK] published_schedules table created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  [SKIP] published_schedules table already exists")
        else:
            print(f"  [ERROR] {e}")

    print("Creating published_shifts table...")
    try:
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS published_shifts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                schedule_id INT NOT NULL,
                employee_id INT NOT NULL,
                shift_date DATE NOT NULL,
                station VARCHAR(50) NOT NULL,
                start_time TIME DEFAULT '06:00:00',
                end_time TIME DEFAULT '14:30:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (schedule_id) REFERENCES published_schedules(id) ON DELETE CASCADE,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                INDEX idx_schedule (schedule_id),
                INDEX idx_employee (employee_id),
                INDEX idx_date (shift_date)
            )
        """)
        print("  [OK] published_shifts table created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  [SKIP] published_shifts table already exists")
        else:
            print(f"  [ERROR] {e}")

    print("\nDone! Tables are ready for use.")

if __name__ == '__main__':
    create_tables()
