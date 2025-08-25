"""Input validation for API endpoints"""
from datetime import datetime
from typing import Dict, List, Optional

VALID_ROLES = ['Heat Pressing', 'Packing and Shipping', 'Picker', 'Labeler', 'Film Matching']

def validate_activity_data(data: Dict) -> Optional[str]:
    """Validate single activity data"""
    required_fields = ['report_id', 'user_email', 'user_name', 'user_role', 
                      'items_count', 'window_start', 'window_end']
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return f"Missing required field: {field}"
    
    # Validate report_id format
    if not data['report_id'] or len(data['report_id']) > 100:
        return "Invalid report_id"
    
    # Validate email
    if '@' not in data['user_email'] or len(data['user_email']) > 255:
        return "Invalid email format"
    
    # Validate role
    if data['user_role'] not in VALID_ROLES:
        return f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"
    
    # Validate items_count
    try:
        items = int(data['items_count'])
        if items < 0:
            return "Items count cannot be negative"
        if items > 10000:
            return "Items count seems too high (max 10000)"
    except (ValueError, TypeError):
        return "Invalid items_count"
    
    # Validate timestamps
    try:
        start = datetime.strptime(data['window_start'], '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(data['window_end'], '%Y-%m-%d %H:%M:%S')
        
        if end <= start:
            return "Window end must be after window start"
        
        # Check window duration (should be around 10 minutes)
        duration = (end - start).total_seconds() / 60
        if duration < 5 or duration > 15:
            return f"Invalid window duration: {duration:.1f} minutes (expected 10)"
            
    except ValueError:
        return "Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS"
    
    return None


def validate_batch_activities(activities: List[Dict]) -> List[Dict]:
    """Validate batch of activities"""
    errors = []
    
    for idx, activity in enumerate(activities):
        error = validate_activity_data(activity)
        if error:
            errors.append({
                'index': idx,
                'report_id': activity.get('report_id', 'unknown'),
                'error': error
            })
    
    return errors


def validate_date(date_string):
    """Validate date string format YYYY-MM-DD"""
    try:
        from datetime import datetime
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False
