
#!/usr/bin/env python3
import re

# Read the dashboard.py file
with open('api/dashboard.py', 'r') as f:
    content = f.read()

# Store original for comparison
original = content

# Fix patterns
replacements = [
    # Fix CURDATE() to use Central Time
    (r"WHERE DATE\(clock_in\) = CURDATE\(\)",
     "WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"WHERE DATE\(window_start\) = CURDATE\(\)",
     "WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"WHERE DATE\(window_end\) = CURDATE\(\)",
     "WHERE DATE(CONVERT_TZ(window_end, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"WHERE DATE\(created_at\) = CURDATE\(\)",
     "WHERE DATE(CONVERT_TZ(created_at, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"WHERE DATE\(score_date\) = CURDATE\(\)",
     "WHERE DATE(score_date) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"AND DATE\(clock_in\) = CURDATE\(\)",
     "AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
    
    (r"AND DATE\(window_start\) = CURDATE\(\)",
     "AND DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))"),
     
    # Fix any remaining CURDATE() 
    (r"= CURDATE\(\)",
     "= DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))")
]

# Apply replacements
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

# Count changes
changes = sum(1 for i in range(len(original)) if i < len(content) and original[i:i+10] != content[i:i+10])

if content != original:
    # Write the fixed content
    with open('api/dashboard.py', 'w') as f:
        f.write(content)
    print(f"Fixed timezone issues in dashboard.py")
    print(f"Replaced {content.count('CONVERT_TZ') - original.count('CONVERT_TZ')} instances")
else:
    print("No changes needed or already fixed")

# Show a few examples of what was changed
import difflib
diff = difflib.unified_diff(original.splitlines()[:100], content.splitlines()[:100], lineterm='')
for line in list(diff)[:20]:
    if line.startswith('+') or line.startswith('-'):
        print(line)
