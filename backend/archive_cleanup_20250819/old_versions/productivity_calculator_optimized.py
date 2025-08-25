def calculate_active_time(self, activities: List[Dict], role_config = None) -> int:
    """
    Calculate active time by checking ALL gaps including clock-in/out
    Optimized version that caches role configs
    """
    if not activities:
        return 0
    
    # Get employee_id and date from first activity
    employee_id = activities[0].get('employee_id')
    if not employee_id:
        return len(activities) * 10  # Fallback
    
    process_date = activities[0]['window_start']
    if isinstance(process_date, str):
        process_date = datetime.fromisoformat(process_date).date()
    else:
        process_date = process_date.date()
    
    # Get ALL clock sessions for the day
    clock_sessions = self.db.execute_query("""
        SELECT 
            clock_in,
            clock_out,
            TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())) as session_minutes
        FROM clock_times
        WHERE employee_id = %s
        AND DATE(clock_in) = %s
        ORDER BY clock_in
    """, (employee_id, process_date))
    
    if not clock_sessions:
        return 0
    
    # Pre-load all role configs to avoid repeated queries
    role_configs = {}
    for activity in activities:
        role_id = activity.get('role_id', 1)
        if role_id not in role_configs and role_id not in self._role_cache:
            role_data = self.db.execute_one(
                "SELECT * FROM role_configs WHERE id = %s", (role_id,)
            )
            if role_data:
                role_configs[role_id] = role_data
    
    total_clocked = sum(s['session_minutes'] for s in clock_sessions)
    total_idle = 0
    
    # Process each clock session
    for session in clock_sessions:
        session_start = session['clock_in']
        session_end = session['clock_out'] or datetime.now()
        
        # Get activities within this session
        session_activities = [
            a for a in activities 
            if a['window_start'] >= session_start and 
               (a['window_end'] <= session_end if session['clock_out'] else True)
        ]
        
        if not session_activities:
            # Entire session is idle (minus grace period)
            grace_period = 10
            session_idle = max(0, session['session_minutes'] - grace_period)
            total_idle += session_idle
            continue
        
        # Check gap from clock-in to first activity (15 min grace)
        first_activity = session_activities[0]
        gap_start = (first_activity['window_start'] - session_start).total_seconds() / 60
        if gap_start > 15:  # 15 minutes setup time
            total_idle += (gap_start - 15)
        
        # Check gaps between activities
        for i in range(len(session_activities) - 1):
            curr = session_activities[i]
            next_act = session_activities[i + 1]
            
            gap = (next_act['window_start'] - curr['window_end']).total_seconds() / 60
            
            # Get threshold from cached role configs
            curr_role_id = curr.get('role_id', 1)
            if curr_role_id in self._role_cache:
                curr_role = self._role_cache[curr_role_id].__dict__
            else:
                curr_role = role_configs.get(curr_role_id, {'role_type': 'continuous', 'idle_threshold_minutes': 5})
            
            if curr_role.get('role_type') == 'batch':
                # Dynamic threshold for batch work
                items = curr.get('items_count', 0)
                expected = float(curr_role.get('expected_per_hour', 200))
                if expected > 0:
                    threshold = max(3, items * (60.0 / expected) * 1.05)
                else:
                    threshold = 10
            else:
                # Fixed threshold for continuous work
                threshold = float(curr_role.get('idle_threshold_minutes', 5))
            
            if gap > threshold:
                total_idle += (gap - threshold)
        
        # Check gap from last activity to clock-out (15 min grace)
        last_activity = session_activities[-1]
        gap_end = (session_end - last_activity['window_end']).total_seconds() / 60
        if gap_end > 15:  # 15 minutes cleanup time
            total_idle += (gap_end - 15)
    
    # Return active minutes
    active_minutes = max(0, total_clocked - total_idle)
    return int(active_minutes)
