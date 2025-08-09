#!/usr/bin/env python3
import re

with open('api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Find the recent activities endpoint
for i, line in enumerate(lines):
    if '/activities/recent' in line:
        print(f"Found endpoint at line {i+1}")
        
        # Look for the time formatting in the next 50 lines
        for j in range(i, min(i+50, len(lines))):
            if 'strftime' in lines[j] and '%I:%M %p' in lines[j]:
                print(f"Found time formatting at line {j+1}: {lines[j].strip()}")
                
                # Check if it's using timezone conversion
                if 'CONVERT_TZ' not in lines[j-5:j+5]:
                    print("  - Missing timezone conversion!")
                    
                    # If it's formatting clock_in or clock_out, fix it
                    if 'clock_in' in lines[j] or 'clock_out' in lines[j]:
                        # Replace the line to use Central Time
                        if '.strftime' in lines[j]:
                            # Add timezone conversion before strftime
                            lines[j] = lines[j].replace(
                                '.strftime',
                                '.astimezone(pytz.timezone("America/Chicago")).strftime'
                            )
                            print(f"  - Fixed to use Central timezone")

# Also look for the SQL query that gets the times
for i, line in enumerate(lines):
    if 'SELECT' in line and 'clock_in' in lines[i:i+10]:
        for j in range(i, min(i+20, len(lines))):
            if 'clock_out' in lines[j] and 'FROM clock_times' in lines[i:j+5]:
                # Check if using CONVERT_TZ
                if 'CONVERT_TZ' not in lines[i:j+5]:
                    print(f"Found query at line {i+1} without timezone conversion")

# Write the fixed file
with open('api/dashboard.py', 'w') as f:
    f.writelines(lines)

print("\nNow checking for the actual formatting code...")
