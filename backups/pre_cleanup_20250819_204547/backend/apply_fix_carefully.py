#!/usr/bin/env python3
"""
Carefully apply the fix to calculate_active_time without breaking other methods
"""
import re

print("Reading productivity_calculator.py...")
with open('/var/www/productivity-system/backend/calculations/productivity_calculator.py', 'r') as f:
    content = f.read()

# Check if file has all required methods
required_methods = ['process_employee_day', 'calculate_today_scores', 'process_all_employees_for_date']
for method in required_methods:
    if f'def {method}' not in content:
        print(f"ERROR: Missing method {method}")
        exit(1)

print("All required methods found. File is complete.")

# Find the calculate_active_time method
pattern = r'(    def calculate_active_time\(self.*?\n)(.*?)((?=\n    def )|$)'
match = re.search(pattern, content, re.DOTALL)

if match:
    print(f"Found calculate_active_time at position {match.start()}")
    # Count lines in the original method
    original_method = match.group(0)
    original_lines = len(original_method.split('\n'))
    print(f"Original method has {original_lines} lines")
else:
    print("ERROR: Could not find calculate_active_time method")
    exit(1)

print("\nFile is ready for manual patching.")
print("The calculate_active_time method starts at the pattern match.")
print("\nTo apply the fix manually:")
print("1. Open the file with nano")
print("2. Search for 'def calculate_active_time'")
print("3. Carefully replace ONLY that method")
print("4. Make sure not to delete anything after it")
