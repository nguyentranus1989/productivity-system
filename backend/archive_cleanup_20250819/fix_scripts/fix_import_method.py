#!/usr/bin/env python3
"""
Fix the import_day_from_connecteam method - Connecteam returns UTC, not Central!
"""

with open('auto_reconciliation.py', 'r') as f:
    content = f.read()

# Find and replace the entire problematic section
old_section = """            # IMPORTANT: Connecteam returns times in Central Time
            # We need to convert them to UTC for storage
            # First, make them timezone-aware as Central Time
            clock_in_central = shift.clock_in
            if clock_in_central.tzinfo is None:
                clock_in_central = self.central_tz.localize(clock_in_central)
            
            clock_out_central = None
            if shift.clock_out:
                clock_out_central = shift.clock_out
                if clock_out_central.tzinfo is None:
                    clock_out_central = self.central_tz.localize(clock_out_central)
            
            # Now convert to UTC for storage
            clock_in_utc = clock_in_central.astimezone(self.utc_tz)
            clock_out_utc = clock_out_central.astimezone(self.utc_tz) if clock_out_central else None"""

new_section = """            # IMPORTANT: Connecteam returns times in UTC already!
            # No conversion needed - just use them directly
            clock_in_utc = shift.clock_in
            clock_out_utc = shift.clock_out"""

content = content.replace(old_section, new_section)

with open('auto_reconciliation.py', 'w') as f:
    f.write(content)

print("✓ Fixed import_day_from_connecteam method")
print("✓ Connecteam times are now correctly handled as UTC")
