import sys
import os
sys.path.append('/var/www/productivity-system/backend')

from datetime import datetime, date
from database.db_manager import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductivityCalculatorFixed:
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate_dynamic_threshold(self, role_type, items_count, expected_per_hour, idle_threshold_minutes):
        """
        Calculate threshold based on work type
        - Continuous work: Fixed threshold (5 minutes)
        - Batch work: Dynamic based on items processed
        """
        if role_type == 'batch':
            # Dynamic threshold for batch work
            if items_count and expected_per_hour and expected_per_hour > 0:
                # Time needed to process items + 5% buffer
                dynamic_threshold = items_count * (60.0 / expected_per_hour) * 1.05
                # Use the larger of dynamic or minimum threshold
                return max(dynamic_threshold, 3.0)  # Minimum 3 minutes
            else:
                return 10.0  # Default for batch with no items
        else:
            # Fixed threshold for continuous work
            return idle_threshold_minutes or 5.0
    
    def calculate_active_time_fixed(self, employee_id, process_date):
        """
        Calculate active time properly including gaps from clock-in/out
        Handles both batch and continuous workers
        """
        
        # Get all clock sessions for the day
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
            return 0, 0, 0  # active_minutes, clocked_minutes, efficiency
        
        # Get all activities for the day with role details
        activities = self.db.execute_query("""
            SELECT 
                al.window_start,
                al.window_end,
                al.items_count,
                al.activity_type,
                al.role_id,
                rc.role_type,
                rc.idle_threshold_minutes,
                rc.expected_per_hour
            FROM activity_logs al
            LEFT JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.employee_id = %s
            AND DATE(al.window_start) = %s
            ORDER BY al.window_start
        """, (employee_id, process_date))
        
        total_clocked = sum(s['session_minutes'] for s in clock_sessions)
        total_idle = 0
        
        # Get employee name for logging
        emp_name = self.db.execute_one(
            "SELECT name FROM employees WHERE id = %s", (employee_id,)
        )
        emp_name = emp_name['name'] if emp_name else f"ID {employee_id}"
        
        print(f"\n{'='*60}")
        print(f"Employee: {emp_name}")
        print(f"  Total clocked: {total_clocked} minutes")
        print(f"  Sessions: {len(clock_sessions)}")
        print(f"  Activities: {len(activities)}")
        
        # Process each clock session
        for session_num, session in enumerate(clock_sessions, 1):
            session_start = session['clock_in']
            session_end = session['clock_out'] or datetime.now()
            
            print(f"\n  Session {session_num}: {session_start.strftime('%H:%M')} to {session_end.strftime('%H:%M')}")
            
            # Get activities within this session
            session_activities = [
                a for a in activities 
                if a['window_start'] >= session_start and 
                   (a['window_end'] <= session_end if session['clock_out'] else True)
            ]
            
            if not session_activities:
                # Entire session is idle (minus a small grace period)
                grace_period = 10  # 10 minutes grace for setup/cleanup
                session_idle = max(0, session['session_minutes'] - grace_period)
                total_idle += session_idle
                print(f"    No activities - Idle: {session_idle} min (after {grace_period} min grace)")
                continue
            
            # Calculate idle at START of session (clock-in to first activity)
            first_activity = session_activities[0]
            gap_start = (first_activity['window_start'] - session_start).total_seconds() / 60
            
            # For gap at start, use a fixed threshold (setup time)
            threshold_start = 15  # 15 minutes for setup/prep at start of shift
            idle_start = max(0, float(gap_start) - float(threshold_start))
            if gap_start > 0:
                print(f"    Start gap: {gap_start:.0f} min - {threshold_start} min setup = {idle_start:.0f} min idle")
                total_idle += idle_start
            
            # Calculate idle BETWEEN activities
            for i in range(len(session_activities) - 1):
                curr = session_activities[i]
                next_act = session_activities[i + 1]
                
                gap = (next_act['window_start'] - curr['window_end']).total_seconds() / 60
                
                # Use PREVIOUS activity's threshold (based on what they just completed)
                threshold = self.calculate_dynamic_threshold(
                    curr['role_type'],
                    curr['items_count'],
                    curr['expected_per_hour'],
                    curr['idle_threshold_minutes']
                )
                
                idle_gap = max(0, float(gap) - float(threshold))
                if gap > 0:
                    activity_desc = f"{curr['activity_type']} ({curr['items_count']} items)"
                    if curr['role_type'] == 'batch':
                        print(f"    After {activity_desc}: gap {gap:.0f} min - dynamic threshold {threshold:.0f} min = {idle_gap:.0f} min idle")
                    else:
                        print(f"    After {activity_desc}: gap {gap:.0f} min - fixed threshold {threshold:.0f} min = {idle_gap:.0f} min idle")
                    total_idle += idle_gap
            
            # Calculate idle at END of session (last activity to clock-out)
            last_activity = session_activities[-1]
            gap_end = (session_end - last_activity['window_end']).total_seconds() / 60
            
            # For gap at end, use last activity's threshold
            threshold_end = self.calculate_dynamic_threshold(
                last_activity['role_type'],
                last_activity['items_count'],
                last_activity['expected_per_hour'],
                last_activity['idle_threshold_minutes']
            )
            
            # But cap end-of-shift threshold at 30 minutes (cleanup time)
            threshold_end = 15
            idle_end = max(0, float(gap_end) - float(threshold_end))
            if gap_end > 0:
                print(f"    End gap: {gap_end:.0f} min - {threshold_end:.0f} min cleanup = {idle_end:.0f} min idle")
                total_idle += idle_end
        
        # Calculate final metrics
        active_minutes = max(0, total_clocked - total_idle)
        efficiency = round((active_minutes / total_clocked * 100) if total_clocked > 0 else 0, 1)
        
        print(f"\n  SUMMARY:")
        print(f"    Clocked: {total_clocked} min")
        print(f"    Total Idle: {total_idle:.0f} min")
        print(f"    Active: {active_minutes:.0f} min")
        print(f"    Efficiency: {efficiency}%")
        print(f"    BEFORE: Efficiency was {self.get_current_efficiency(employee_id, process_date)}%")
        
        return active_minutes, total_clocked, efficiency
    
    def get_current_efficiency(self, employee_id, process_date):
        """Get current efficiency from daily_scores for comparison"""
        result = self.db.execute_one("""
            SELECT efficiency_rate 
            FROM daily_scores 
            WHERE employee_id = %s AND score_date = %s
        """, (employee_id, process_date))
        if result and result['efficiency_rate']:
            return round(result['efficiency_rate'] * 100, 1)
        return 0

# Test the fix
if __name__ == "__main__":
    calc = ProductivityCalculatorFixed()
    
    print("=" * 60)
    print("TESTING FIXED CALCULATION WITH BATCH WORKER LOGIC")
    print("=" * 60)
    
    # Test Huu Nguyen (ID 33) - Continuous worker with Heat Press
    print("\n### HUU NGUYEN (Heat Press - Continuous) ###")
    active, clocked, eff = calc.calculate_active_time_fixed(33, date.today())
    
    # Test dung duong - Batch worker
    employee_id = calc.db.execute_one(
        "SELECT id FROM employees WHERE name = 'dung duong'"
    )
    if employee_id:
        print("\n### DUNG DUONG (Mixed Batch/Continuous) ###")
        active, clocked, eff = calc.calculate_active_time_fixed(employee_id['id'], date.today())
    
    # Test another batch worker
    employee_id = calc.db.execute_one(
        "SELECT id FROM employees WHERE name = 'Nathan Gonzales'"
    )
    if employee_id:
        print("\n### NATHAN GONZALES ###")
        active, clocked, eff = calc.calculate_active_time_fixed(employee_id['id'], date.today())
