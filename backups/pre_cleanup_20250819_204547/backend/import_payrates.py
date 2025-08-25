import csv
import mysql.connector
from datetime import datetime

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Nicholasbin0116$",
    database="productivity_tracker"
)
cursor = db.cursor()

def import_rates(csv_file):
    with open(csv_file, 'r') as file:
        csv_reader = csv.DictReader(file)
        
        success_count = 0
        error_count = 0
        
        for row in csv_reader:
            try:
                # Get employee ID
                cursor.execute("SELECT id FROM employees WHERE name = %s", (row['employee_name'],))
                result = cursor.fetchone()
                
                if result:
                    employee_id = result[0]
                    pay_type = row.get('pay_type', 'hourly').lower()
                    pay_rate = float(row['pay_rate'])
                    notes = row.get('notes', '')
                    
                    # Insert rate
                    cursor.execute("""
                        INSERT INTO employee_payrates (employee_id, pay_type, pay_rate, notes)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        pay_type = VALUES(pay_type),
                        pay_rate = VALUES(pay_rate),
                        notes = VALUES(notes)
                    """, (employee_id, pay_type, pay_rate, notes))
                    
                    if pay_type == 'salary':
                        daily_rate = pay_rate / 260
                        print(f"✓ {row['employee_name']}: ${pay_rate:,.0f}/year (${daily_rate:.2f}/day)")
                    else:
                        print(f"✓ {row['employee_name']}: ${pay_rate}/hour")
                    
                    success_count += 1
                else:
                    print(f"✗ Employee not found: {row['employee_name']}")
                    error_count += 1
                    
            except Exception as e:
                print(f"✗ Error with {row['employee_name']}: {str(e)}")
                error_count += 1
        
        db.commit()
        print(f"\n✅ Import complete! Success: {success_count}, Errors: {error_count}")

def verify_import():
    print("\n📊 Current Pay Rates:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT name, pay_type, pay_rate, effective_hourly_rate, daily_rate
        FROM employee_hourly_costs
        ORDER BY pay_type DESC, name
    """)
    
    print(f"{'Employee':<25} {'Type':<8} {'Rate':<12} {'Hourly':<8} {'Daily':<8}")
    print("-" * 60)
    
    for name, pay_type, pay_rate, hourly, daily in cursor.fetchall():
        if pay_type == 'salary':
            print(f"{name:<25} {pay_type:<8} ${pay_rate:>10,.0f} ${hourly:>6.2f} ${daily:>6.2f}")
        else:
            print(f"{name:<25} {pay_type:<8} ${pay_rate:>10.2f} ${hourly:>6.2f} {'-':>8}")

if __name__ == "__main__":
    import_rates('employee_rates.csv')
    verify_import()
    
cursor.close()
db.close()