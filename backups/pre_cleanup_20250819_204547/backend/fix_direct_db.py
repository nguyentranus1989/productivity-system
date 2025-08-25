# Fix the write_direct_to_db method to handle the actual data structure
with open('/var/www/productivity-system/backend/podfactory_sync.py', 'r') as f:
    lines = f.readlines()

# Find and replace the write_direct_to_db method
for i in range(len(lines)):
    if 'def write_direct_to_db(self, activities_batch):' in lines[i]:
        # Find the values.append section
        for j in range(i, min(i+50, len(lines))):
            if 'values.append((' in lines[j]:
                # Replace the next ~10 lines with correct field mapping
                lines[j] = '''                # Extract from nested structure
                metadata = activity.get('metadata', {})
                values.append((
                    activity.get('employee_id'),
                    activity.get('activity_type'),
                    metadata.get('role_id', 3),
                    activity.get('items_count', 0),
                    metadata.get('window_start'),
                    metadata.get('window_end'),
                    activity.get('department'),
                    'podfactory',
                    metadata.get('podfactory_id'),
                    metadata.get('duration_minutes', 0)
'''
                # Remove the old lines
                for k in range(j+1, j+11):
                    if k < len(lines):
                        lines[k] = ''
                break
        break

with open('/var/www/productivity-system/backend/podfactory_sync.py', 'w') as f:
    f.writelines(lines)

print("Fixed direct DB method to handle nested data structure")
