#!/usr/bin/env python3
"""
Recalculate productivity scores for August 1-19, 2025
"""
from calculations.productivity_calculator import ProductivityCalculator
from database.db_manager import DatabaseManager
from datetime import date, timedelta
import time

def main():
    calc = ProductivityCalculator()
    db = DatabaseManager()
    
    # Date range
    start_date = date(2025, 8, 1)
    end_date = date(2025, 8, 19)
    
    print("=" * 60)
    print(f"RECALCULATING SCORES: {start_date} to {end_date}")
    print("=" * 60)
    
    # Track totals
    total_processed = 0
    total_errors = 0
    
    # Process each day
    current_date = start_date
    while current_date <= end_date:
        print(f"\nProcessing {current_date}...")
        
        try:
            # Get all employees for this date
            result = calc.process_all_employees_for_date(current_date)
            
            processed = result.get('processed', 0)
            errors = result.get('errors', 0)
            
            print(f"  ✓ Processed: {processed} employees")
            if errors > 0:
                print(f"  ✗ Errors: {errors}")
            
            total_processed += processed
            total_errors += errors
            
            # Brief pause to avoid overloading
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ERROR processing {current_date}: {e}")
            total_errors += 1
        
        current_date += timedelta(days=1)
    
    print("\n" + "=" * 60)
    print("RECALCULATION COMPLETE")
    print(f"Total days processed: {(end_date - start_date).days + 1}")
    print(f"Total employee-days processed: {total_processed}")
    print(f"Total errors: {total_errors}")
    print("=" * 60)
    
    # Show sample of results
    print("\nSample Results (Low Efficiency Employees):")
    sample = db.execute_query("""
        SELECT 
            e.name,
            ds.score_date,
            ds.active_minutes,
            ds.clocked_minutes,
            ROUND(ds.efficiency_rate * 100, 1) as eff_pct,
            ds.items_processed
        FROM daily_scores ds
        JOIN employees e ON e.id = ds.employee_id
        WHERE ds.score_date >= %s
        AND ds.score_date <= %s
        AND ds.efficiency_rate < 0.3
        AND ds.clocked_minutes > 60
        ORDER BY ds.efficiency_rate ASC
        LIMIT 10
    """, (start_date, end_date))
    
    print(f"\n{'Date':<12} {'Employee':<20} {'Active':<8} {'Clocked':<8} {'Eff%':<6} {'Items':<6}")
    print("-" * 70)
    for row in sample:
        print(f"{row['score_date']} {row['name']:<20} {row['active_minutes']:<8} {row['clocked_minutes']:<8} {row['eff_pct']:<6} {row['items_processed']:<6}")

if __name__ == "__main__":
    main()
