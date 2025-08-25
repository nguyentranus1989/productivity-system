"""Add caching to key API endpoints"""

# Read dashboard.py
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    content = f.read()

# Add import if not present
if 'from simple_cache import' not in content:
    # Find a good place to add import (after other imports)
    import_line = 'from simple_cache import cache_api_result\n'
    
    # Add after the last import statement
    import_pos = content.rfind('\nimport ')
    if import_pos == -1:
        import_pos = content.rfind('\nfrom ')
    
    if import_pos != -1:
        # Find the end of that line
        newline_pos = content.find('\n', import_pos + 1)
        content = content[:newline_pos] + '\n' + import_line + content[newline_pos:]
        print("✅ Added cache import")

# Now wrap the actual data fetching in get_leaderboard
# This is a bit tricky, so let's be careful
lines = content.split('\n')
new_lines = []
in_leaderboard = False

for i, line in enumerate(lines):
    # Add caching decorator before specific functions
    if 'def get_leaderboard():' in line and i > 0:
        if '@cache_api_result' not in lines[i-1]:
            new_lines.append('@cache_api_result(seconds=10)')
            print("✅ Added caching to get_leaderboard")
    
    if 'def get_department_stats():' in line and i > 0:
        if '@cache_api_result' not in lines[i-1]:
            new_lines.append('@cache_api_result(seconds=15)')
            print("✅ Added caching to get_department_stats")
    
    new_lines.append(line)

# Save the updated file
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.write('\n'.join(new_lines))

print("✅ Caching added to dashboard API")
