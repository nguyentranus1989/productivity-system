"""Activity flag system for detecting anomalies"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from database.db_manager import get_db

logger = logging.getLogger(__name__)

class ActivityFlagger:
    """Detect and flag suspicious or anomalous activities"""
    
    def __init__(self):
        self.db = get_db()
        self.flag_types = {
            'SUSPICIOUS': 'suspicious',
            'DUPLICATE': 'duplicate',
            'OUT_OF_RANGE': 'out_of_range',
            'MISSING_CLOCK': 'missing_clock',
            'UNUSUAL_PATTERN': 'unusual_pattern'
        }
    
    def check_activity(self, activity_data: Dict) -> List[Dict]:
        """Check an activity for various flag conditions"""
        flags = []
        
        # Check for suspicious item count
        suspicious_flag = self._check_suspicious_count(activity_data)
        if suspicious_flag:
            flags.append(suspicious_flag)
        
        # Check for out of range
        range_flag = self._check_out_of_range(activity_data)
        if range_flag:
            flags.append(range_flag)
        
        # Check for missing clock
        clock_flag = self._check_missing_clock(activity_data)
        if clock_flag:
            flags.append(clock_flag)
        
        # Check for unusual patterns
        pattern_flags = self._check_unusual_patterns(activity_data)
        flags.extend(pattern_flags)
        
        return flags
    
    def _check_suspicious_count(self, activity: Dict) -> Optional[Dict]:
        """Check if item count is suspiciously high"""
        # Get role configuration
        role = self.db.execute_one(
            """
            SELECT rc.* FROM role_configs rc
            WHERE rc.id = %s
            """,
            (activity['role_id'],)
        )
        
        if not role:
            return None
        
        # Calculate expected max for 10-minute window
        expected_max = role['expected_per_hour'] / 6  # 10 minutes = 1/6 hour
        
        # Flag if more than 2x expected
        if activity['items_count'] > expected_max * 2:
            return {
                'type': self.flag_types['SUSPICIOUS'],
                'reason': f"Item count {activity['items_count']} exceeds 2x expected maximum {expected_max:.0f} for 10-minute window",
                'severity': 'high'
            }
        
        # Warning if more than 1.5x expected
        elif activity['items_count'] > expected_max * 1.5:
            return {
                'type': self.flag_types['SUSPICIOUS'],
                'reason': f"Item count {activity['items_count']} exceeds 1.5x expected maximum {expected_max:.0f} for 10-minute window",
                'severity': 'medium'
            }
        
        return None
    
    def _check_out_of_range(self, activity: Dict) -> Optional[Dict]:
        """Check if activity is outside normal working hours"""
        window_start = activity['window_start']
        
        # Check if outside normal hours (6 AM - 6 PM)
        if window_start.hour < 6 or window_start.hour >= 18:
            return {
                'type': self.flag_types['OUT_OF_RANGE'],
                'reason': f"Activity at {window_start.strftime('%H:%M')} is outside normal working hours (6:00-18:00)",
                'severity': 'low'
            }
        
        # Check if on weekend
        if window_start.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return {
                'type': self.flag_types['OUT_OF_RANGE'],
                'reason': f"Activity on {window_start.strftime('%A')} (weekend)",
                'severity': 'medium'
            }
        
        return None
    
    def _check_missing_clock(self, activity: Dict) -> Optional[Dict]:
        """Check if employee has clock time for the activity"""
        # Check for clock time within 30 minutes of activity
        clock_check = self.db.execute_one(
            """
            SELECT id FROM clock_times
            WHERE employee_id = %s
            AND clock_in <= %s
            AND (clock_out IS NULL OR clock_out >= %s)
            """,
            (activity['employee_id'], 
             activity['window_start'] + timedelta(minutes=30),
             activity['window_start'] - timedelta(minutes=30))
        )
        
        if not clock_check:
            return {
                'type': self.flag_types['MISSING_CLOCK'],
                'reason': "No clock-in found within 30 minutes of activity",
                'severity': 'high'
            }
        
        return None
    
    def _check_unusual_patterns(self, activity: Dict) -> List[Dict]:
        """Check for unusual activity patterns"""
        flags = []
        
        # Check for rapid consecutive activities
        recent_activities = self.db.execute_query(
            """
            SELECT * FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s
            AND window_start < %s
            AND id != %s
            ORDER BY window_start DESC
            """,
            (activity['employee_id'],
             activity['window_start'] - timedelta(hours=1),
             activity['window_start'],
             activity.get('id', -1))
        )
        
        # Check for too many activities in short time
        if len(recent_activities) >= 5:  # 5+ activities in last hour
            flags.append({
                'type': self.flag_types['UNUSUAL_PATTERN'],
                'reason': f"High frequency: {len(recent_activities) + 1} activities in last hour",
                'severity': 'medium'
            })
        
        # Check for identical consecutive counts
        if recent_activities:
            last_activity = recent_activities[0]
            if last_activity['items_count'] == activity['items_count']:
                # Check if multiple activities have same count
                same_count = sum(1 for a in recent_activities[:3] 
                               if a['items_count'] == activity['items_count'])
                
                if same_count >= 2:
                    flags.append({
                        'type': self.flag_types['UNUSUAL_PATTERN'],
                        'reason': f"Repeated identical count ({activity['items_count']}) in {same_count + 1} consecutive activities",
                        'severity': 'medium'
                    })
        
        return flags
    
    def create_flags(self, activity_log_id: int, flags: List[Dict]) -> int:
        """Create flag records in database"""
        created = 0
        
        for flag in flags:
            try:
                # Check if flag already exists
                existing = self.db.execute_one(
                    """
                    SELECT id FROM activity_flags
                    WHERE activity_log_id = %s
                    AND flag_type = %s
                    """,
                    (activity_log_id, flag['type'])
                )
                
                if not existing:
                    self.db.execute_update(
                        """
                        INSERT INTO activity_flags 
                        (activity_log_id, flag_type, flag_reason)
                        VALUES (%s, %s, %s)
                        """,
                        (activity_log_id, flag['type'], flag['reason'])
                    )
                    created += 1
                    
                    # Create alert for high severity flags
                    if flag.get('severity') == 'high':
                        self._create_flag_alert(activity_log_id, flag)
                        
            except Exception as e:
                logger.error(f"Error creating flag: {e}")
        
        return created
    
    def _create_flag_alert(self, activity_log_id: int, flag: Dict):
        """Create alert for high-severity flags"""
        # Get activity details
        activity = self.db.execute_one(
            """
            SELECT a.*, e.name as employee_name
            FROM activity_logs a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.id = %s
            """,
            (activity_log_id,)
        )
        
        if activity:
            message = f"Activity flagged for {activity['employee_name']}: {flag['reason']}"
            
            self.db.execute_update(
                """
                INSERT INTO alerts (employee_id, alert_type, severity, message)
                VALUES (%s, 'system', 'warning', %s)
                """,
                (activity['employee_id'], message)
            )
    
    def get_unreviewed_flags(self, limit: int = 50) -> List[Dict]:
        """Get unreviewed activity flags"""
        return self.db.execute_query(
            """
            SELECT 
                af.*,
                a.report_id,
                a.items_count,
                a.window_start,
                e.name as employee_name,
                rc.role_name
            FROM activity_flags af
            JOIN activity_logs a ON af.activity_log_id = a.id
            JOIN employees e ON a.employee_id = e.id
            JOIN role_configs rc ON a.role_id = rc.id
            WHERE af.is_reviewed = FALSE
            ORDER BY af.created_at DESC
            LIMIT %s
            """,
            (limit,)
        )
    
    def review_flag(self, flag_id: int, reviewer_id: int, 
                    review_notes: str = None) -> bool:
        """Mark a flag as reviewed"""
        try:
            self.db.execute_update(
                """
                UPDATE activity_flags
                SET is_reviewed = TRUE,
                    reviewed_by = %s,
                    reviewed_at = NOW(),
                    review_notes = %s
                WHERE id = %s
                """,
                (reviewer_id, review_notes, flag_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error reviewing flag: {e}")
            return False
