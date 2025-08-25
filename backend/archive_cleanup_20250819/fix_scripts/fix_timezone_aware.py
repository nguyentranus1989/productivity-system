#!/usr/bin/env python3
"""
Fix timezone awareness issues in compare_shifts method
"""
import re

with open('auto_reconciliation.py', 'r') as f:
    content = f.read()

# Find the compare_shifts method and fix it
# We need to make sure both datetimes are timezone-aware or both are naive

# Add this after getting ct_clock_in_utc
old_pattern = r"ct_clock_in_utc = ct_shift.clock_in  # Already UTC"
new_pattern = """ct_clock_in_utc = ct_shift.clock_in  # Already UTC
        # Make sure it's timezone-aware
        if ct_clock_in_utc and ct_clock_in_utc.tzinfo is None:
            ct_clock_in_utc = self.utc_tz.localize(ct_clock_in_utc)"""

content = content.replace(old_pattern, new_pattern, 1)

# Do the same for db_clock_in
old_db = r"db_clock_in = db_shift\['clock_in'\]"
new_db = """db_clock_in = db_shift['clock_in']
        # Make sure it's timezone-aware
        if db_clock_in and db_clock_in.tzinfo is None:
            db_clock_in = self.utc_tz.localize(db_clock_in)"""

content = re.sub(old_db, new_db, content)

# Also fix the shift times in import_day_from_connecteam
old_import = """            # IMPORTANT: Connecteam returns times in UTC already!
            # No conversion needed - just use them directly
            clock_in_utc = shift.clock_in
            clock_out_utc = shift.clock_out"""

new_import = """            # IMPORTANT: Connecteam returns times in UTC already!
            # No conversion needed - just use them directly
            clock_in_utc = shift.clock_in
            clock_out_utc = shift.clock_out
            
            # Make sure they're timezone-aware
            if clock_in_utc and clock_in_utc.tzinfo is None:
                clock_in_utc = self.utc_tz.localize(clock_in_utc)
            if clock_out_utc and clock_out_utc.tzinfo is None:
                clock_out_utc = self.utc_tz.localize(clock_out_utc)"""

content = content.replace(old_import, new_import)

with open('auto_reconciliation.py', 'w') as f:
    f.write(content)

print("✓ Fixed timezone awareness issues")
