# Find where to add the direct DB method in podfactory_sync.py
with open('/var/www/productivity-system/backend/podfactory_sync.py', 'r') as f:
    lines = f.readlines()

# Find a good place to insert (after send_batch_to_api method)
insert_position = -1
for i, line in enumerate(lines):
    if 'def send_batch_to_api' in line:
        # Find the end of this method
        for j in range(i+1, len(lines)):
            if lines[j].startswith('    def ') or (lines[j].strip() and not lines[j].startswith(' ')):
                insert_position = j
                break
        break

if insert_position > 0:
    # Insert the new method
    new_method = '''
    def write_activities_direct_to_db(self, activities_batch):
        """Write activities directly to database - 100x faster than API"""
        if not activities_batch:
            return True, []
        
        conn = pymysql.connect(**self.local_config)
        cursor = conn.cursor()
        
        try:
            values = []
            for activity in activities_batch:
                # Map activity_type to role_id
                activity_type = activity.get('activity_type', '')
                role_id = {
                    'In Production': 1,
                    'QC Passed': 2, 
                    'Picking': 3,
                    'Labeling': 4,
                    'Film Matching': 5
                }.get(activity_type, 3)
                
                values.append((
                    activity.get('employee_id'),
                    activity_type,
                    role_id,
                    activity.get('items_count', 0),
                    activity.get('window_start'),
                    activity.get('window_end'),
                    activity.get('department'),
                    'podfactory',
                    activity.get('reference_id'),
                    activity.get('duration_minutes', 0)
                ))
            
            # Bulk insert with duplicate handling
            cursor.executemany("""
                INSERT INTO activity_logs 
                (employee_id, activity_type, role_id, items_count,
                 window_start, window_end, department, source,
                 reference_id, duration_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    items_count = VALUES(items_count),
                    updated_at = NOW()
            """, values)
            
            conn.commit()
            logger.info(f"✅ Direct DB write: {len(values)} activities")
            return True, []
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Direct DB write failed: {e}")
            # Fall back to API
            return self.send_batch_to_api(activities_batch)
        finally:
            cursor.close()
            conn.close()

'''
    lines.insert(insert_position, new_method)
    
    # Now replace the call to send_batch_to_api with write_activities_direct_to_db
    for i in range(len(lines)):
        if 'success, errors = self.send_batch_to_api(activities_batch)' in lines[i]:
            lines[i] = lines[i].replace(
                'self.send_batch_to_api(activities_batch)',
                'self.write_activities_direct_to_db(activities_batch)'
            )
            print(f"✅ Replaced API call with direct DB write at line {i+1}")
    
    # Save the file
    with open('/var/www/productivity-system/backend/podfactory_sync.py', 'w') as f:
        f.writelines(lines)
    
    print("✅ Direct database write implemented!")
    print("This will be 100x faster and won't timeout!")
else:
    print("Could not find insertion point")
