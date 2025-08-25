import fileinput
import sys

# Read the file and fix the order
with open('podfactory_sync.py', 'r') as f:
    content = f.read()

# Fix the problematic section
old_code = """            user_role = activity.get('user_role', '')
            department = ACTION_TO_DEPARTMENT_MAP.get(activity['action'], 'Unknown')
            scan_type = 'batch_scan' if role_id in [3, 4, 5] else 'item_scan'
            
            role_id = ACTION_TO_ROLE_ID.get(activity['action'], 3)
            if activity['action'] == 'QC Passed' and role_id == 3:
                logger.warning(f"WARNING: QC Passed getting role_id 3! Action value: '{activity['action']}'")
            user_role = activity.get('user_role', '')"""

new_code = """            user_role = activity.get('user_role', '')
            
            # Set role_id FIRST based on action
            role_id = ACTION_TO_ROLE_ID.get(activity['action'], 3)
            if activity['action'] == 'QC Passed' and role_id == 3:
                logger.warning(f"WARNING: QC Passed getting role_id 3! Action value: '{activity['action']}'")
            
            department = ACTION_TO_DEPARTMENT_MAP.get(activity['action'], 'Unknown')
            scan_type = 'batch_scan' if role_id in [3, 4, 5] else 'item_scan'"""

content = content.replace(old_code, new_code)

with open('podfactory_sync.py', 'w') as f:
    f.write(content)

print("Fixed the code order!")
