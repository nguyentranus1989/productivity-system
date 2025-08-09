#!/usr/bin/env python3
"""
Force productivity calculation
Run this to manually trigger score calculations
"""

from calculations.productivity_calculator import ProductivityCalculator
from database.db_manager import DatabaseManager
from datetime import datetime

def main():
    print("=" * 60)
    print("PRODUCTIVITY CALCULATION FORCE RUN")
    print("=" * 60)
    
    # Create instances
    calc = ProductivityCalculator()
    db = DatabaseManager()
    
    # Check current status
    result = db.execute_query("SELECT MAX(updated_at) as last FROM daily_scores WHERE score_date = CURDATE()")
    last_update = result[0]['last']
    print(f"\nLast calculation: {last_update}")
    
    if last_update:
        # Calculate time since last update
        time_diff = datetime.now() - last_update
        hours = time_diff.total_seconds() / 3600
        print(f"Time since last update: {hours:.1f} hours")
    
    # Force calculation
    print("\nRunning calculations...")
    print("-" * 40)
    
    result = calc.calculate_today_scores()
    
    print(f"\n✅ Processed {result['processed']} employees")
    print(f"❌ Errors: {result['errors']}")
    
    # Check if it updated
    result = db.execute_query("SELECT MAX(updated_at) as last FROM daily_scores WHERE score_date = CURDATE()")
    new_update = result[0]['last']
    print(f"\nNew calculation time: {new_update}")
    
    # Show top 10 leaderboard
    print("\n" + "=" * 60)
    print("CURRENT LEADERBOARD")
    print("=" * 60)
    
    result = db.execute_query("""
        SELECT 
            e.name, 
            ds.points_earned, 
            ds.items_processed,
            ds.efficiency_rate,
            ds.active_minutes,
            ds.clocked_minutes
        FROM daily_scores ds
        JOIN employees e ON e.id = ds.employee_id
        WHERE ds.score_date = CURDATE()
        ORDER BY ds.points_earned DESC
        LIMIT 10
    """)
    
    print(f"\n{'Rank':<5} {'Name':<20} {'Points':<10} {'Items':<10} {'Efficiency':<12} {'Active/Clocked'}")
    print("-" * 80)
    
    for i, r in enumerate(result, 1):
        efficiency = f"{float(r['efficiency_rate']) * 100:.0f}%"
        time_ratio = f"{r['active_minutes']}/{r['clocked_minutes']}"
        print(f"{i:<5} {r['name']:<20} {r['points_earned']:<10} {r['items_processed']:<10} {efficiency:<12} {time_ratio}")
    
    # Check sync status
    print("\n" + "=" * 60)
    print("SYNC STATUS")
    print("=" * 60)
    
    result = db.execute_query("""
        SELECT * FROM podfactory_sync_log 
        ORDER BY id DESC 
        LIMIT 1
    """)
    
    if result:
        last_sync = result[0]
        print(f"Last sync: {last_sync['sync_time']}")
        print(f"Records synced: {last_sync['records_synced']}")
        print(f"Status: {last_sync['status']}")
        if last_sync['notes']:
            print(f"Notes: {last_sync['notes']}")
    
    print("\n✅ Calculation complete! Dashboard should now show updated data.")

if __name__ == "__main__":
    main()