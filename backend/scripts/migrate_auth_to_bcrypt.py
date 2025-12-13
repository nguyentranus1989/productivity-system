"""
Authentication Migration Script
Migrates plain text PINs to bcrypt hashes and creates shop_floor_settings table

Run with: python scripts/migrate_auth_to_bcrypt.py [--dry-run]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
import argparse
from dotenv import load_dotenv
load_dotenv()

from database.db_manager import get_db

def hash_pin(pin):
    """Hash PIN using bcrypt (10 rounds)"""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(10)).decode()

def is_bcrypt_hash(value):
    """Check if value is already a bcrypt hash"""
    return value and value.startswith('$2')

def create_shop_floor_table(dry_run=False):
    """Create shop_floor_settings table if not exists"""
    print("\n=== Creating shop_floor_settings table ===")

    db = get_db()

    # Check if table exists
    result = db.execute_one("""
        SELECT COUNT(*) as cnt
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name = 'shop_floor_settings'
    """)

    if result and result['cnt'] > 0:
        print("  Table already exists, skipping...")
        return

    if dry_run:
        print("  [DRY RUN] Would create shop_floor_settings table")
        print("  [DRY RUN] Would insert default PIN (bcrypt hash of '1234')")
        return

    # Create table
    db.execute_query("""
        CREATE TABLE shop_floor_settings (
            id INT PRIMARY KEY DEFAULT 1,
            pin_hash VARCHAR(255) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    print("  Table created successfully")

    # Insert default PIN (hash of '1234')
    default_pin_hash = hash_pin('1234')
    db.execute_query("""
        INSERT INTO shop_floor_settings (id, pin_hash)
        VALUES (1, %s)
    """, (default_pin_hash,))
    print("  Default PIN (1234) set successfully")

def add_pin_set_at_column(dry_run=False):
    """Add pin_set_at column to employee_auth if not exists"""
    print("\n=== Adding pin_set_at column to employee_auth ===")

    db = get_db()

    # Check if column exists
    result = db.execute_one("""
        SELECT COUNT(*) as cnt
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        AND table_name = 'employee_auth'
        AND column_name = 'pin_set_at'
    """)

    if result and result['cnt'] > 0:
        print("  Column already exists, skipping...")
        return

    if dry_run:
        print("  [DRY RUN] Would add pin_set_at column")
        return

    db.execute_query("""
        ALTER TABLE employee_auth
        ADD COLUMN pin_set_at DATETIME
    """)
    print("  Column added successfully")

def ensure_pin_column_size(dry_run=False):
    """Ensure pin column can hold bcrypt hashes (60 chars)"""
    print("\n=== Checking pin column size ===")

    db = get_db()

    result = db.execute_one("""
        SELECT COLUMN_TYPE
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        AND table_name = 'employee_auth'
        AND column_name = 'pin'
    """)

    if not result:
        print("  ERROR: pin column not found")
        return

    col_type = result['COLUMN_TYPE']
    print(f"  Current type: {col_type}")

    # bcrypt hashes are 60 chars, ensure at least 255
    if 'varchar' in col_type.lower():
        # Extract size
        import re
        match = re.search(r'\((\d+)\)', col_type)
        if match and int(match.group(1)) >= 60:
            print("  Column size adequate, skipping...")
            return

    if dry_run:
        print("  [DRY RUN] Would resize pin column to VARCHAR(255)")
        return

    db.execute_query("ALTER TABLE employee_auth MODIFY COLUMN pin VARCHAR(255)")
    print("  Column resized to VARCHAR(255)")

def migrate_employee_pins(dry_run=False):
    """Migrate plain text PINs to bcrypt hashes"""
    print("\n=== Migrating employee PINs to bcrypt ===")

    db = get_db()

    # Get all employees with PINs
    employees = db.execute_query("""
        SELECT ea.employee_id, ea.pin, e.name
        FROM employee_auth ea
        JOIN employees e ON ea.employee_id = e.id
        WHERE ea.pin IS NOT NULL
    """)

    if not employees:
        print("  No employees with PINs found")
        return

    migrated = 0
    skipped = 0

    for emp in employees:
        pin = emp['pin']

        if is_bcrypt_hash(pin):
            print(f"  [{emp['employee_id']}] {emp['name']}: Already bcrypt, skipping")
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] [{emp['employee_id']}] {emp['name']}: Would hash PIN '{pin[:2]}**'")
            migrated += 1
            continue

        # Hash the plain text PIN
        hashed_pin = hash_pin(pin)

        # Update in database
        db.execute_query("""
            UPDATE employee_auth
            SET pin = %s, pin_set_at = NOW()
            WHERE employee_id = %s
        """, (hashed_pin, emp['employee_id']))

        print(f"  [{emp['employee_id']}] {emp['name']}: Migrated successfully")
        migrated += 1

    print(f"\n  Summary: {migrated} migrated, {skipped} already bcrypt")

def verify_migration():
    """Verify all PINs are now bcrypt hashes"""
    print("\n=== Verifying migration ===")

    db = get_db()

    # Check for any remaining plain text PINs
    result = db.execute_one("""
        SELECT COUNT(*) as plain_count
        FROM employee_auth
        WHERE pin IS NOT NULL
        AND pin NOT LIKE '$2%%'
    """)

    plain_count = result['plain_count'] if result else 0

    if plain_count > 0:
        print(f"  WARNING: {plain_count} PINs are still in plain text!")
        return False

    # Count bcrypt PINs
    result = db.execute_one("""
        SELECT COUNT(*) as bcrypt_count
        FROM employee_auth
        WHERE pin LIKE '$2%%'
    """)

    bcrypt_count = result['bcrypt_count'] if result else 0
    print(f"  All {bcrypt_count} PINs are bcrypt hashed")

    # Check shop_floor_settings
    result = db.execute_one("""
        SELECT pin_hash FROM shop_floor_settings WHERE id = 1
    """)

    if result and is_bcrypt_hash(result['pin_hash']):
        print("  Shop floor PIN is bcrypt hashed")
    else:
        print("  WARNING: Shop floor PIN is not properly set")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description='Migrate authentication to bcrypt')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    if args.dry_run:
        print("=" * 50)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 50)

    print("\n" + "=" * 50)
    print("Authentication Migration Script")
    print("=" * 50)

    try:
        # Step 1: Create shop_floor_settings table
        create_shop_floor_table(args.dry_run)

        # Step 2: Add pin_set_at column
        add_pin_set_at_column(args.dry_run)

        # Step 3: Ensure pin column can hold bcrypt hashes
        ensure_pin_column_size(args.dry_run)

        # Step 4: Migrate employee PINs
        migrate_employee_pins(args.dry_run)

        # Step 4: Verify (only if not dry run)
        if not args.dry_run:
            success = verify_migration()
            if success:
                print("\n" + "=" * 50)
                print("Migration completed successfully!")
                print("=" * 50)
            else:
                print("\n" + "=" * 50)
                print("Migration completed with warnings - please review")
                print("=" * 50)
                sys.exit(1)
        else:
            print("\n" + "=" * 50)
            print("Dry run completed - run without --dry-run to apply changes")
            print("=" * 50)

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
