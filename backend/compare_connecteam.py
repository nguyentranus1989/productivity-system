# compare_connecteam_fixed.py
import requests
import urllib3
from datetime import datetime
from database.db_manager import DatabaseManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = '9255ce96-70eb-4982-82ef-fc35a7651428'
CLOCK_ID = '7425182'

headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
}

def get_connecteam_shifts(start_date, end_date):
    """Get shifts directly from Connecteam API"""
    url = f'https://api.connecteam.com/time-clock/v1/time-clocks/{CLOCK_ID}/time-activities'
    params = {
        'startDate': start_date,
        'endDate': end_date
    }
    
    response = requests.get(url, headers=headers, params=params, verify=False)
    
    if response.status_code == 200:
        data = response.json()
        return data.get('data', {}).get('timeActivitiesByUsers', [])
    else:
        print(f"Error: {response.status_code}")
        return []

def compare_hours():
    db = DatabaseManager()
    
    # Date range
    start = '2025-08-15'
    end = '2025-08-27'
    
    print(f"Fetching Connecteam data for {start} to {end}...")
    users_data = get_connecteam_shifts(start, end)
    
    # Process Connecteam data - CORRECTED STRUCTURE
    connecteam_totals = {}
    for user in users_data:
        user_id = str(user.get('userId'))
        shifts = user.get('shifts', [])
        
        # Get employee name from database
        emp_data = db.execute_one(
            "SELECT name FROM employees WHERE connecteam_user_id = %s",
            (user_id,)
        )
        
        if emp_data and shifts:
            name = emp_data['name']
            for shift in shifts:
                if shift.get('start') and shift.get('end'):
                    # Convert timestamp to date
                    start_ts = shift['start']['timestamp']
                    date = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')
                    
                    # Calculate minutes
                    end_ts = shift['end']['timestamp']
                    minutes = (end_ts - start_ts) / 60
                    
                    key = f"{name}|{date}"
                    connecteam_totals[key] = connecteam_totals.get(key, 0) + minutes
    
    # Get database totals
    db_data = db.execute_query("""
        SELECT 
            e.name,
            DATE(ct.clock_in) as work_date,
            SUM(ct.total_minutes) as db_minutes
        FROM clock_times ct
        JOIN employees e ON ct.employee_id = e.id
        WHERE DATE(ct.clock_in) BETWEEN %s AND %s
        GROUP BY e.name, DATE(ct.clock_in)
    """, (start, end))
    
    # Compare
    print("\nComparison (DB vs Connecteam):")
    print("-" * 80)
    print(f"{'Employee':<25} {'Date':<12} {'DB Hours':<10} {'CT Hours':<10} {'Diff':<10}")
    print("-" * 80)
    
    total_db = 0
    total_ct = 0
    discrepancies = []
    
    for row in db_data:
        key = f"{row['name']}|{row['work_date']}"
        db_hours = float(row['db_minutes']) / 60 if row['db_minutes'] else 0
        ct_hours = connecteam_totals.get(key, 0) / 60
        diff = db_hours - ct_hours
        
        total_db += db_hours
        total_ct += ct_hours
        
        if abs(diff) > 0.1:
            discrepancies.append({
                'name': row['name'],
                'date': str(row['work_date']),
                'db_hours': db_hours,
                'ct_hours': ct_hours,
                'diff': diff
            })
            print(f"{row['name']:<25} {str(row['work_date']):<12} {db_hours:<10.2f} {ct_hours:<10.2f} {diff:<10.2f}")
    
    print("-" * 80)
    print(f"{'TOTALS':<25} {'':<12} {total_db:<10.2f} {total_ct:<10.2f} {(total_db - total_ct):<10.2f}")
    print(f"\nFound {len(discrepancies)} discrepancies out of {len(db_data)} records")
    
    # Show which employees have no Connecteam data
    db_employees = db.execute_query("""
        SELECT DISTINCT e.name, e.connecteam_user_id
        FROM employees e
        JOIN clock_times ct ON ct.employee_id = e.id
        WHERE DATE(ct.clock_in) BETWEEN %s AND %s
    """, (start, end))
    
    print("\nEmployees with missing Connecteam user IDs:")
    for emp in db_employees:
        if not emp['connecteam_user_id']:
            print(f"  - {emp['name']} (no connecteam_user_id)")

if __name__ == "__main__":
    compare_hours()