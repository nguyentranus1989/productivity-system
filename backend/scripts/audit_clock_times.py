"""
Audit clock_times table for data quality issues.
Finds invalid records where clock_out < clock_in (negative hours).

Usage:
    python scripts/audit_clock_times.py
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def find_invalid_shifts():
    """Find all records where clock_out < clock_in"""
    db = DatabaseManager()

    query = """
    SELECT
        ct.id,
        ct.employee_id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, ct.clock_out) as minutes_diff,
        ct.source
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE ct.clock_out IS NOT NULL
      AND ct.clock_out < ct.clock_in
    ORDER BY ct.clock_in DESC
    """

    results = db.fetch_all(query)

    print("=" * 100)
    print("INVALID CLOCK TIME RECORDS (clock_out < clock_in)")
    print("=" * 100)

    if not results:
        print("\nNo invalid records found!")
        return []

    print(f"\nFound {len(results)} invalid record(s):\n")
    print(f"{'ID':<8} {'Employee':<25} {'Clock In':<20} {'Clock Out':<20} {'Diff (min)':<12} {'Source'}")
    print("-" * 100)

    for row in results:
        print(f"{row['id']:<8} {row['name'][:24]:<25} {str(row['clock_in']):<20} {str(row['clock_out']):<20} {row['minutes_diff']:<12} {row.get('source', 'N/A')}")

    print("\n" + "=" * 100)

    # Summary by employee
    print("\nSUMMARY BY EMPLOYEE:")
    print("-" * 60)

    employee_summary = {}
    for row in results:
        name = row['name']
        if name not in employee_summary:
            employee_summary[name] = {'count': 0, 'total_negative_mins': 0}
        employee_summary[name]['count'] += 1
        employee_summary[name]['total_negative_mins'] += abs(row['minutes_diff'])

    for name, data in sorted(employee_summary.items()):
        print(f"  {name}: {data['count']} invalid shift(s), total {data['total_negative_mins']/60:.2f} negative hours")

    return results


def analyze_fixable_records():
    """Analyze which records can be auto-fixed"""
    db = DatabaseManager()

    query = """
    SELECT
        ct.id,
        ct.employee_id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        DATE(ct.clock_in) as clock_in_date,
        DATE(ct.clock_out) as clock_out_date,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, ct.clock_out) as original_diff,
        -- Simulated fix: add 1 day to clock_out
        TIMESTAMPDIFF(MINUTE, ct.clock_in, DATE_ADD(ct.clock_out, INTERVAL 1 DAY)) as fixed_diff,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, DATE_ADD(ct.clock_out, INTERVAL 1 DAY)) / 60 as fixed_hours
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE ct.clock_out IS NOT NULL
      AND ct.clock_out < ct.clock_in
    ORDER BY ct.clock_in DESC
    """

    results = db.fetch_all(query)

    print("\n" + "=" * 100)
    print("FIXABLE ANALYSIS (adding 1 day to clock_out)")
    print("=" * 100)

    fixable = []
    unfixable = []

    for row in results:
        fixed_hours = row['fixed_hours']
        # Reasonable shift is 0-16 hours
        if 0 < fixed_hours <= 16:
            fixable.append(row)
        else:
            unfixable.append(row)

    print(f"\nFIXABLE ({len(fixable)} records - shift would be 0-16 hours):")
    print("-" * 80)
    for row in fixable:
        print(f"  ID {row['id']}: {row['name']} - would become {row['fixed_hours']:.2f}h shift")

    print(f"\nUNFIXABLE ({len(unfixable)} records - shift would be >16 hours or invalid):")
    print("-" * 80)
    for row in unfixable:
        print(f"  ID {row['id']}: {row['name']} - would become {row['fixed_hours']:.2f}h shift (too long/invalid)")

    return fixable, unfixable


if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("CLOCK TIMES DATA QUALITY AUDIT")
    print("=" * 100)

    invalid = find_invalid_shifts()

    if invalid:
        fixable, unfixable = analyze_fixable_records()

        print("\n" + "=" * 100)
        print("RECOMMENDATIONS:")
        print("=" * 100)
        print(f"\n1. {len(fixable)} records can be auto-fixed by adding 1 day to clock_out")
        print(f"2. {len(unfixable)} records need manual review")
        print(f"\nTo fix, run: python scripts/fix_negative_hours.py --dry-run")
        print("Then: python scripts/fix_negative_hours.py --apply")
