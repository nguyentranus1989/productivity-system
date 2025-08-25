#!/usr/bin/env python3
"""
Fix the duplicate and wrongly indented lines
"""

with open('auto_reconciliation.py', 'r') as f:
    lines = f.readlines()

# Remove the wrongly indented duplicate lines around 190-195
new_lines = []
skip_next = 0

for i, line in enumerate(lines):
    if skip_next > 0:
        skip_next -= 1
        continue
    
    # Skip the wrongly indented duplicate lines
    if i >= 189 and i <= 194:
        if line.strip().startswith('# Make sure') and i == 190:
            # Skip this and the next 2 lines (they're duplicates)
            skip_next = 2
            continue
        elif line.strip() == 'if db_clock_in.tzinfo is None:' and not line.startswith('                    '):
            # Skip this wrongly indented line
            continue
        elif line.strip() == 'db_clock_in = self.utc_tz.localize(db_clock_in)' and not line.startswith('                        '):
            # Skip this wrongly indented line
            continue
    
    new_lines.append(line)

with open('auto_reconciliation.py', 'w') as f:
    f.writelines(new_lines)

print("✓ Fixed indentation and removed duplicates")
