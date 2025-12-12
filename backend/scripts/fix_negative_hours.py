"""
Fix invalid clock_times records where clock_out < clock_in.
Auto-corrects by adding 1 day to clock_out when the resulting shift is reasonable (0-16 hours).

Usage:
    python scripts/fix_negative_hours.py --dry-run    # Preview changes
    python scripts/fix_negative_hours.py --apply      # Apply fixes
"""
import sys
import os
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def get_fixable_records(db):
    """Get records that can be auto-fixed"""
    query = """
    SELECT
        ct.id,
        ct.employee_id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, ct.clock_out) as original_minutes,
        DATE_ADD(ct.clock_out, INTERVAL 1 DAY) as fixed_clock_out,
        TIMESTAMPDIFF(MINUTE, ct.clock_in, DATE_ADD(ct.clock_out, INTERVAL 1 DAY)) as fixed_minutes
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE ct.clock_out IS NOT NULL
      AND ct.clock_out < ct.clock_in
    ORDER BY ct.clock_in DESC
    """

    results = db.fetch_all(query)

    fixable = []
    unfixable = []

    for row in results:
        fixed_hours = row['fixed_minutes'] / 60 if row['fixed_minutes'] else 0
        # Reasonable shift is 0-16 hours
        if 0 < fixed_hours <= 16:
            fixable.append(row)
        else:
            unfixable.append(row)

    return fixable, unfixable


def apply_fixes(db, fixable_records, dry_run=True):
    """Apply fixes to database"""
    if dry_run:
        print("\n[DRY RUN] Would apply the following fixes:\n")
    else:
        print("\n[APPLYING] Fixing records:\n")

    fixed_count = 0

    for row in fixable_records:
        original_hours = abs(row['original_minutes']) / 60
        fixed_hours = row['fixed_minutes'] / 60

        print(f"  ID {row['id']}: {row['name']}")
        print(f"    clock_in:  {row['clock_in']}")
        print(f"    clock_out: {row['clock_out']} -> {row['fixed_clock_out']}")
        print(f"    hours:     -{original_hours:.2f}h -> {fixed_hours:.2f}h")
        print()

        if not dry_run:
            try:
                db.execute_query("""
                    UPDATE clock_times
                    SET clock_out = DATE_ADD(clock_out, INTERVAL 1 DAY),
                        total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, DATE_ADD(clock_out, INTERVAL 1 DAY)),
                        updated_at = NOW()
                    WHERE id = %s
                """, (row['id'],))
                fixed_count += 1
            except Exception as e:
                print(f"    ERROR: {e}")

    return fixed_count


def main():
    parser = argparse.ArgumentParser(description='Fix negative hours in clock_times table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply fixes to database')

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Error: Must specify --dry-run or --apply")
        print("\nUsage:")
        print("  python scripts/fix_negative_hours.py --dry-run    # Preview")
        print("  python scripts/fix_negative_hours.py --apply      # Apply")
        sys.exit(1)

    db = DatabaseManager()

    print("\n" + "=" * 100)
    print("FIX NEGATIVE HOURS IN CLOCK_TIMES")
    print("=" * 100)

    fixable, unfixable = get_fixable_records(db)

    print(f"\nFound {len(fixable)} fixable records (shift becomes 0-16 hours)")
    print(f"Found {len(unfixable)} unfixable records (need manual review)\n")

    if unfixable:
        print("UNFIXABLE RECORDS (manual review needed):")
        print("-" * 80)
        for row in unfixable:
            fixed_hours = row['fixed_minutes'] / 60 if row['fixed_minutes'] else 0
            print(f"  ID {row['id']}: {row['name']} - would become {fixed_hours:.2f}h")
        print()

    if not fixable:
        print("No fixable records found!")
        return

    fixed_count = apply_fixes(db, fixable, dry_run=args.dry_run)

    if args.apply:
        print("=" * 100)
        print(f"DONE: Fixed {fixed_count} records")
        print("=" * 100)

        # Verify
        remaining_fixable, remaining_unfixable = get_fixable_records(db)
        print(f"\nVerification: {len(remaining_fixable)} fixable records remaining")
        if remaining_fixable:
            print("WARNING: Some records were not fixed!")
    else:
        print("=" * 100)
        print(f"DRY RUN COMPLETE: {len(fixable)} records would be fixed")
        print("Run with --apply to make changes")
        print("=" * 100)


if __name__ == "__main__":
    main()
