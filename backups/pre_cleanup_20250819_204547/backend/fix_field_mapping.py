# Fix the field mapping in write_direct_to_db
with open('/var/www/productivity-system/backend/podfactory_sync.py', 'r') as f:
    lines = f.readlines()

# Find and fix the values.append section
for i in range(len(lines)):
    if 'values.append((' in lines[i] and 'metadata.get(' in lines[i+4]:
        # Replace the mapping
        lines[i:i+11] = [
            '                metadata = activity.get("metadata", {})\n',
            '                values.append((\n',
            '                    activity.get("employee_id"),\n',
            '                    metadata.get("action", ""),  # activity_type from metadata\n',
            '                    metadata.get("role_id", 3),\n',
            '                    activity.get("quantity", 0),  # items_count is called quantity\n',
            '                    activity.get("timestamp"),  # window_start is called timestamp\n',
            '                    activity.get("window_end"),\n',
            '                    activity.get("department"),\n',
            '                    "podfactory",\n',
            '                    metadata.get("podfactory_id"),\n',
            '                    metadata.get("duration_minutes", 0)\n',
            '                ))\n'
        ]
        break

with open('/var/www/productivity-system/backend/podfactory_sync.py', 'w') as f:
    f.writelines(lines)

print("Fixed field mapping")
