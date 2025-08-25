#!/usr/bin/env python3
import re

# Read the original file
with open('/var/www/productivity-system/backend/calculations/productivity_calculator.py', 'r') as f:
    content = f.read()

# The new calculate_active_time method
new_method = '''    def calculate_active_time(self, activities: List[Dict], role_config = None) -> int:
        """
        Calculate active time by subtracting excess idle from clocked time
        Now includes idle time at start and end of day
        """
        if not activities:
            return 0
        
        # Get employee_id from first activity
        employee_id = activities[0].get('employee_id')
        if not employee_id:
            return len(activities) * 10
        
        # Get clocked minutes and clock times for this period
        process_date = activities[0]['window_start']
        if isinstance(process_date, str):
            process_date = datetime.fromisoformat(process_date).date()
        else:
            process_date = process_date.date()
        
        clock_data = self.db.execute_one(
            """
            SELECT 
                MIN(clock_in) as first_clock_in,
                MAX(COALESCE(clock_out, NOW())) as last_clock_out,
                TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, NOW()))) as total_minutes
            FROM clock_times
            WHERE employee_id = %s 
            AND DATE(clock_in) = %s
            """,
            (employee_id, process_date)
        )
        
        if not clock_data or not clock_data['total_minutes']:
            return len(activities) * 10
        
        total_clocked = clock_data['total_minutes']
        total_excess_idle = 0
        
        # Sort activities by window_start to ensure proper order
        sorted_activities = sorted(activities, key=lambda x: x['window_start'])
        
        # 1. Check idle at START of day
        if clock_data['first_clock_in']:
            first_activity_start = sorted_activities[0]['window_start']
            if isinstance(first_activity_start, str):
                first_activity_start = datetime.fromisoformat(first_activity_start)
            
            clock_in = clock_data['first_clock_in']
            if isinstance(clock_in, str):
                clock_in = datetime.fromisoformat(clock_in)
                
            start_gap = (first_activity_start - clock_in).total_seconds() / 60
            
            # Allow 15 minutes to get settled at start of day
            start_threshold = 15
            if start_gap > start_threshold:
                total_excess_idle += (start_gap - start_threshold)
                logger.debug(f"Start of day idle: {start_gap:.1f} min, excess: {start_gap - start_threshold:.1f} min")
        
        # 2. Check gaps BETWEEN activities (existing logic)
        prev_activity = None
        for activity in sorted_activities:
            if prev_activity:
                prev_end = prev_activity['window_end']
                curr_start = activity['window_start']
                
                if isinstance(prev_end, str):
                    prev_end = datetime.fromisoformat(prev_end)
                if isinstance(curr_start, str):
                    curr_start = datetime.fromisoformat(curr_start)
                
                gap_minutes = (curr_start - prev_end).total_seconds() / 60
                
                # Get PREVIOUS activity's role for threshold
                prev_role_id = prev_activity.get('role_id', 1)
                prev_role = self._role_cache.get(prev_role_id, role_config)
                
                # Calculate threshold based on PREVIOUS activity
                if hasattr(prev_role, 'role_type') and prev_role.role_type == 'batch':
                    # Dynamic threshold for batch work
                    prev_items = prev_activity.get('items_count', 0)
                    expected = prev_role.expected_per_hour if prev_role.expected_per_hour > 0 else 200
                    time_per_item = 60.0 / expected
                    threshold = max(3, float(prev_items) * float(time_per_item) * 1.05)
                else:
                    # Fixed threshold for continuous work
                    threshold = float(getattr(prev_role, 'idle_threshold_minutes', 5.0))
                
                # Calculate excess idle
                if gap_minutes > threshold:
                    excess = gap_minutes - threshold
                    total_excess_idle += excess
                    logger.debug(f"Gap idle: {gap_minutes:.1f} min, threshold: {threshold:.1f}, excess: {excess:.1f}")
            
            prev_activity = activity
        
        # 3. Check idle at END of day
        last_activity = sorted_activities[-1]
        last_activity_end = last_activity['window_end']
        if isinstance(last_activity_end, str):
            last_activity_end = datetime.fromisoformat(last_activity_end)
        
        clock_out = clock_data['last_clock_out']
        if isinstance(clock_out, str):
            clock_out = datetime.fromisoformat(clock_out)
        
        end_gap = (clock_out - last_activity_end).total_seconds() / 60
        
        # Calculate threshold based on LAST activity
        last_role_id = last_activity.get('role_id', 1)
        last_role = self._role_cache.get(last_role_id, role_config)
        
        if hasattr(last_role, 'role_type') and last_role.role_type == 'batch':
            # Dynamic threshold for batch work
            last_items = last_activity.get('items_count', 0)
            expected = last_role.expected_per_hour if last_role.expected_per_hour > 0 else 200
            time_per_item = 60.0 / expected
            end_threshold = max(5, float(last_items) * float(time_per_item) * 1.05)
        else:
            # Fixed threshold for continuous work
            end_threshold = float(getattr(last_role, 'idle_threshold_minutes', 5.0))
        
        # Check if this is actually end of day (they clocked out)
        # clock_out will be different from NOW() if they actually clocked out
        current_time = datetime.now()
        if clock_out < current_time - timedelta(minutes=5):  # They clocked out (not just NOW())
            # This is true end of day - add 15 minutes for cleanup
            end_threshold_with_cleanup = end_threshold + 15
            if end_gap > end_threshold_with_cleanup:
                excess = end_gap - end_threshold_with_cleanup
                total_excess_idle += excess
                logger.debug(f"End of day idle: {end_gap:.1f} min, threshold with cleanup: {end_threshold_with_cleanup:.1f}, excess: {excess:.1f}")
        else:
            # They're still clocked in - use normal threshold
            if end_gap > end_threshold:
                excess = end_gap - end_threshold
                total_excess_idle += excess
                logger.debug(f"End of day idle (still clocked in): {end_gap:.1f} min, threshold: {end_threshold:.1f}, excess: {excess:.1f}")
        
        # Active time = clocked time - total excess idle
        active_minutes = max(0, int(total_clocked - total_excess_idle))
        
        # Log summary for debugging
        logger.info(f"Employee {employee_id}: Clocked {total_clocked} min, "
                    f"Total excess idle {total_excess_idle:.1f} min, "
                    f"Active {active_minutes} min ({active_minutes/total_clocked*100:.1f}%)")
        
        return active_minutes'''

# Find and replace the calculate_active_time method
pattern = r'(\s*)def calculate_active_time\(self.*?\n(?:\1.*\n)*?\1\s*return\s+\w+'
match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

if match:
    # Replace the old method with the new one
    new_content = content[:match.start()] + new_method + content[match.end():]
    
    # Write the updated content back
    with open('/var/www/productivity-system/backend/calculations/productivity_calculator.py', 'w') as f:
        f.write(new_content)
    
    print("Successfully replaced calculate_active_time method!")
else:
    print("Could not find calculate_active_time method to replace")
