# Fix the sync query to use created_at instead of window_start
with open('/var/www/productivity-system/backend/podfactory_sync.py', 'r') as f:
    content = f.read()

# Find and replace the WHERE clause
old_where = "WHERE window_start > %s"
new_where = "WHERE created_at > %s"

if old_where in content:
    content = content.replace(old_where, new_where)
    print("✅ Fixed: Changed query from 'window_start > last_sync' to 'created_at > last_sync'")
    print("This will catch all newly CREATED records, regardless of when the work was done")
    
    with open('/var/www/productivity-system/backend/podfactory_sync.py', 'w') as f:
        f.write(content)
else:
    print("❌ Could not find the WHERE clause to fix")
