#!/usr/bin/env python3

# Read the file
with open('integrations/connecteam_sync.py', 'r') as f:
    content = f.read()

fixes_applied = 0

# Fix 1: _update_live_cache function
old_cache = """        # Convert times to Central for cache
        clock_in_utc = shift.clock_in  # Already UTC from Connecteam
        
        cache_data = {"""

new_cache = """        # Convert times to Central for cache
        clock_in_utc = shift.clock_in  # Already UTC from Connecteam
        clock_in_central = self.convert_to_central(clock_in_utc)
        
        cache_data = {"""

if old_cache in content:
    content = content.replace(old_cache, new_cache)
    fixes_applied += 1
    print("✅ Fixed _update_live_cache function")

# Fix 2: _update_working_today_cache function  
old_working = """            clock_in_utc = shift.clock_in  # Already UTC from Connecteam
            clock_out_utc = shift.clock_out  # Already UTC from Connecteam if shift.clock_out else None
            
            working_data = {"""

new_working = """            clock_in_utc = shift.clock_in  # Already UTC from Connecteam
            clock_out_utc = shift.clock_out  # Already UTC from Connecteam if shift.clock_out else None
            clock_in_central = self.convert_to_central(clock_in_utc)
            clock_out_central = self.convert_to_central(clock_out_utc) if clock_out_utc else None
            
            working_data = {"""

if old_working in content:
    content = content.replace(old_working, new_working)
    fixes_applied += 1
    print("✅ Fixed _update_working_today_cache function")

# Write the fixed content back
if fixes_applied > 0:
    with open('integrations/connecteam_sync.py', 'w') as f:
        f.write(content)
    print(f"\n✅ Successfully applied {fixes_applied} fixes!")
else:
    print("❌ No changes needed or patterns not found")

# Verify all uses of clock_in_central now have definitions
print("\n🔍 Verification:")
import re
issues = []
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'clock_in_central' in line and 'clock_in_central =' not in line:
        # Look back 10 lines for definition
        found_def = False
        for j in range(max(0, i-11), i-1):
            if 'clock_in_central =' in lines[j]:
                found_def = True
                break
        if not found_def:
            issues.append(f"Line {i}: {line.strip()}")

if issues:
    print("❌ Still have undefined clock_in_central at:")
    for issue in issues:
        print(f"   {issue}")
else:
    print("✅ All clock_in_central variables are properly defined!")
