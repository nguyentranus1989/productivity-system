# recalculate_august.py
from datetime import date, timedelta
from calculations.productivity_calculator import ProductivityCalculator

calc = ProductivityCalculator()

# Process all of August
start_date = date(2025, 8, 1)
end_date = date(2025, 8, 27)  # Skip Aug 28 since it's incomplete

current = start_date
success_count = 0
error_count = 0

print("Starting recalculation with fixed timezone handling...")

while current <= end_date:
    print(f"Processing {current}...")
    try:
        result = calc.process_all_employees_for_date(current)
        print(f"  Processed {result['processed']} employees")
        success_count += result['processed']
    except Exception as e:
        print(f"  Error: {e}")
        error_count += 1
    current += timedelta(days=1)

print(f"\nComplete! Processed {success_count} employee-days with {error_count} errors")