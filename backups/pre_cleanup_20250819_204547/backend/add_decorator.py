# Read dashboard.py
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Find get_leaderboard and add decorator
for i in range(len(lines)):
    if 'def get_leaderboard():' in lines[i]:
        # Check if decorator already exists
        if i > 0 and 'cached_endpoint' not in lines[i-1]:
            lines.insert(i, '@cached_endpoint(ttl_seconds=10)\n')
            print("Added cache decorator to get_leaderboard")
        break

# Save
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)
