#!/usr/bin/env python3

with open('dashboard-api.js', 'r') as f:
    content = f.read()

# Find and replace the getCentralDate function
old_function = '''    getCentralDate() {
        const now = new Date();
        const centralDate = new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));
        return centralDate.toISOString().split('T')[0];
    }'''

new_function = '''    getCentralDate() {
        const now = new Date();
        // Get the date string directly in Central Time
        const centralDateStr = now.toLocaleDateString("en-US", {
            timeZone: "America/Chicago",
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
        // Convert MM/DD/YYYY to YYYY-MM-DD
        const [month, day, year] = centralDateStr.split('/');
        return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }'''

if old_function in content:
    content = content.replace(old_function, new_function)
    print("Fixed getCentralDate function")
else:
    # Try to find it another way
    import re
    pattern = r'getCentralDate\(\)\s*{\s*[^}]+\s*}'
    match = re.search(pattern, content)
    if match:
        content = re.sub(pattern, new_function.replace('    ', ''), content)
        print("Fixed getCentralDate function (regex)")
    else:
        print("Could not find getCentralDate function to fix")

with open('dashboard-api.js', 'w') as f:
    f.write(content)
