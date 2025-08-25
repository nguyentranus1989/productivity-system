#!/usr/bin/env python3
"""
Modify podfactory_sync.py to add auto-creation
"""

# Read the file
with open('podfactory_sync.py', 'r') as f:
    content = f.read()

# Add import at the top
import_line = "from employee_auto_creator import EmployeeAutoCreator"
if import_line not in content:
    # Find where to add the import (after other imports)
    import_pos = content.find("import logging")
    if import_pos != -1:
        # Add after the logging import
        end_of_line = content.find("\n", import_pos)
        content = content[:end_of_line+1] + import_line + "\n" + content[end_of_line+1:]

# Find the __init__ method to add auto_creator initialization
init_pos = content.find("def __init__(self):")
if init_pos != -1:
    # Find the end of __init__ setup (before logger.info)
    setup_end = content.find("logger.info", init_pos)
    if setup_end != -1:
        # Add auto_creator initialization
        auto_creator_init = """        
        # Initialize auto-creator for new employees
        self.auto_creator = EmployeeAutoCreator({
            'host': self.local_config['host'],
            'port': self.local_config['port'],
            'user': self.local_config['user'],
            'password': self.local_config['password'],
            'database': self.local_config['database']
        })
"""
        content = content[:setup_end] + auto_creator_init + "\n        " + content[setup_end:]

# Find where employees are skipped and modify
skip_pattern = """            if not employee:
                email = activity['user_email']
                if email not in skipped_emails:
                    skipped_emails[email] = 0
                skipped_emails[email] += 1
                skipped_count += 1
                continue"""

replacement = """            if not employee:
                # Try to auto-create employee if we have a name
                user_name = activity.get('user_name')
                if user_name:
                    logger.info(f"Attempting to auto-create employee: {user_name} ({activity['user_email']})")
                    employee = self.auto_creator.find_or_create_employee(user_name, activity['user_email'])
                    
                    if employee:
                        # Update name_mappings for future use in this sync
                        name_mappings[user_name.lower().strip()] = employee
                        logger.info(f"✅ Auto-created/found employee: {employee['name']} (ID: {employee['employee_id']})")
                    else:
                        logger.warning(f"Failed to auto-create employee: {user_name}")
                
                # If still no employee, skip
                if not employee:
                    email = activity['user_email']
                    if email not in skipped_emails:
                        skipped_emails[email] = 0
                    skipped_emails[email] += 1
                    skipped_count += 1
                    continue"""

content = content.replace(skip_pattern, replacement)

# Write the modified file
with open('podfactory_sync.py', 'w') as f:
    f.write(content)

print("✅ Modified podfactory_sync.py successfully!")
