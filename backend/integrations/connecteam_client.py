# backend/integrations/connecteam_client.py

import requests
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import urllib3

# Disable SSL warnings (if needed in your environment)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

@dataclass
class ConnecteamShift:
    """Represents a work shift from Connecteam"""
    user_id: str
    employee_name: str
    employee_email: str
    title: str
    clock_in: datetime
    clock_out: Optional[datetime]
    total_minutes: Optional[float]
    is_active: bool
    breaks: List[Dict] = None

    def __post_init__(self):
        if self.breaks is None:
            self.breaks = []

@dataclass
class ConnecteamEmployee:
    """Represents an employee from Connecteam"""
    user_id: str
    first_name: str
    last_name: str
    email: str
    title: str
    is_archived: bool
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class ConnecteamClient:
    """Client for interacting with Connecteam API"""
    
    def __init__(self, api_key: str, clock_id: int):
        self.api_key = api_key
        self.base_url = "https://api.connecteam.com"
        self.clock_id = clock_id
        self.headers = {
            "accept": "application/json",
            "X-API-KEY": api_key
        }
        self._employee_cache = {}
        
    def get_all_employees(self, include_archived: bool = True) -> Dict[str, ConnecteamEmployee]:
        """Fetch all employees from Connecteam with pagination"""
        try:
            employees = {}

            # Get active users with pagination
            offset = 0
            limit = 100
            total_active = 0

            while True:
                response = requests.get(
                    f"{self.base_url}/users/v1/users",
                    headers=self.headers,
                    params={'limit': limit, 'offset': offset},
                    timeout=30,
                    verify=False
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch users: {response.status_code}")
                    break

                data = response.json()
                users = data.get('data', {}).get('users', [])

                if not users:
                    break

                for user in users:
                    emp = self._parse_employee(user)
                    employees[emp.user_id] = emp

                total_active += len(users)

                # Check if we got fewer than limit (last page)
                if len(users) < limit:
                    break

                offset += limit

            logger.info(f"Retrieved {total_active} active users from Connecteam")

            # Get archived users if requested (also with pagination)
            if include_archived:
                try:
                    offset = 0
                    total_archived = 0

                    while True:
                        archived_response = requests.get(
                            f"{self.base_url}/users/v1/users",
                            headers=self.headers,
                            params={'userStatus': 'archived', 'limit': limit, 'offset': offset},
                            timeout=30,
                            verify=False
                        )

                        if archived_response.status_code != 200:
                            break

                        archived_data = archived_response.json()
                        archived_users = archived_data.get('data', {}).get('users', [])

                        if not archived_users:
                            break

                        for user in archived_users:
                            emp = self._parse_employee(user)
                            employees[emp.user_id] = emp

                        total_archived += len(archived_users)

                        if len(archived_users) < limit:
                            break

                        offset += limit

                    logger.info(f"Retrieved {total_archived} archived users")
                except Exception as e:
                    logger.warning(f"Could not fetch archived users: {e}")

            self._employee_cache = employees
            return employees

        except Exception as e:
            logger.error(f"Error fetching employees: {e}")
            return {}
    
    def _parse_employee(self, user_data: Dict) -> ConnecteamEmployee:
        """Parse employee data from API response"""
        # Extract title from custom fields
        title = "No Title"
        for field in user_data.get('customFields', []):
            if field.get('name') == 'Title':
                title = field.get('value', 'No Title')
                break
        
        return ConnecteamEmployee(
            user_id=user_data.get('userId'),
            first_name=user_data.get('firstName', ''),
            last_name=user_data.get('lastName', ''),
            email=user_data.get('email', ''),
            title=title,
            is_archived=user_data.get('isArchived', False)
        )
    
    def get_employee_by_id(self, user_id: str) -> Optional[ConnecteamEmployee]:
        """Get specific employee details"""
        # Check cache first
        if user_id in self._employee_cache:
            return self._employee_cache[user_id]
        
        try:
            response = requests.get(
                f"{self.base_url}/users/v1/users",
                headers=self.headers,
                params={'userIds': [user_id]},
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('data', {}).get('users', [])
                if users:
                    emp = self._parse_employee(users[0])
                    self._employee_cache[user_id] = emp
                    return emp
        except Exception as e:
            logger.error(f"Error fetching employee {user_id}: {e}")
        
        return None
    
    def get_todays_shifts(self) -> List[ConnecteamShift]:
        """Get all shifts for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.get_shifts_for_date(today)
    
    def get_shifts_for_date(self, date: str) -> List[ConnecteamShift]:
        """Get all shifts for a specific date"""
        try:
            params = {
                'startDate': date,
                'endDate': date
            }
            
            url = f"{self.base_url}/time-clock/v1/time-clocks/{self.clock_id}/time-activities"
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30,
                verify=False
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get shifts: {response.status_code}")
                return []
            
            data = response.json()
            time_activities = data.get('data', {}).get('timeActivitiesByUsers', [])
            
            shifts = []
            for user_activity in time_activities:
                user_id = user_activity.get('userId')
                user_shifts = user_activity.get('shifts', [])
                
                # Skip users with no shifts
                if not user_shifts:
                    continue
                
                # Get employee info
                employee = self.get_employee_by_id(user_id)
                if not employee:
                    logger.warning(f"Could not find employee data for user {user_id}")
                    employee_name = f"Unknown User {user_id}"
                    employee_email = ""
                    title = "Unknown"
                else:
                    employee_name = employee.full_name
                    employee_email = employee.email
                    title = employee.title
                
                # Process each shift
                for shift in user_shifts:
                    shift_obj = self._parse_shift(
                        shift, user_id, employee_name, employee_email, title
                    )
                    if shift_obj:
                        shifts.append(shift_obj)
            
            logger.info(f"Retrieved {len(shifts)} shifts for {date}")
            return shifts
            
        except Exception as e:
            logger.error(f"Error getting shifts for {date}: {e}")
            return []
    
    def _parse_shift(self, shift_data: Dict, user_id: str, 
                     employee_name: str, employee_email: str, title: str) -> Optional[ConnecteamShift]:
        """Parse shift data from API response"""
        try:
            # Get clock in time
            start_info = shift_data.get('start', {})
            clock_in_timestamp = start_info.get('timestamp')
            
            if not clock_in_timestamp:
                return None
            
            # Store in UTC explicitly for consistent timezone handling
            clock_in = datetime.fromtimestamp(clock_in_timestamp, tz=timezone.utc).replace(tzinfo=None)
            
            # Get clock out time (if exists)
            end_info = shift_data.get('end')
            clock_out = None
            total_minutes = None
            is_active = True
            
            if end_info and end_info.get('timestamp'):
                clock_out_timestamp = end_info.get('timestamp')
                # Store in UTC explicitly for consistent timezone handling
                clock_out = datetime.fromtimestamp(clock_out_timestamp, tz=timezone.utc).replace(tzinfo=None)
                total_minutes = (clock_out_timestamp - clock_in_timestamp) / 60
                is_active = False

                # Validate: clock_out must be after clock_in
                if clock_out < clock_in:
                    logger.warning(
                        f"Invalid shift for {employee_name}: clock_out ({clock_out}) before clock_in ({clock_in}). "
                        f"Raw timestamps: start={clock_in_timestamp}, end={clock_out_timestamp}"
                    )
                    # Auto-correct: if clock_out is same day but earlier, assume next day
                    if clock_out.date() == clock_in.date():
                        from datetime import timedelta
                        clock_out = clock_out + timedelta(days=1)
                        total_minutes = (clock_out - clock_in).total_seconds() / 60
                        logger.info(f"Auto-corrected clock_out to next day: {clock_out}")
                    else:
                        # Can't auto-fix, skip this shift
                        logger.error(f"Cannot auto-correct shift for {employee_name} - dates differ. Skipping.")
                        return None
            else:
                # Still working - calculate current duration using UTC
                current_time = datetime.now(timezone.utc).timestamp()
                total_minutes = (current_time - clock_in_timestamp) / 60
            
            # Parse breaks - store in UTC
            breaks = []
            for break_data in shift_data.get('breaks', []):
                break_start = break_data.get('start', {}).get('timestamp')
                break_end = break_data.get('end', {}).get('timestamp')

                if break_start:
                    break_info = {
                        'start': datetime.fromtimestamp(break_start, tz=timezone.utc).replace(tzinfo=None),
                        'end': datetime.fromtimestamp(break_end, tz=timezone.utc).replace(tzinfo=None) if break_end else None,
                        'duration_minutes': (break_end - break_start) / 60 if break_end else None
                    }
                    breaks.append(break_info)
            
            return ConnecteamShift(
                user_id=user_id,
                employee_name=employee_name,
                employee_email=employee_email,
                title=title,
                clock_in=clock_in,
                clock_out=clock_out,
                total_minutes=total_minutes,
                is_active=is_active,
                breaks=breaks
            )
            
        except Exception as e:
            logger.error(f"Error parsing shift: {e}")
            return None
    
    def get_currently_working(self) -> List[ConnecteamShift]:
        """Get list of employees currently clocked in"""
        all_shifts = self.get_todays_shifts()
        return [shift for shift in all_shifts if shift.is_active]
    
    def get_shift_history(self, user_id: str, start_date: str, end_date: str) -> List[ConnecteamShift]:
        """Get shift history for a specific employee"""
        try:
            params = {
                'startDate': start_date,
                'endDate': end_date,
                'userIds': [user_id]
            }
            
            url = f"{self.base_url}/time-clock/v1/time-clocks/{self.clock_id}/time-activities"
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30,
                verify=False
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get shift history: {response.status_code}")
                return []
            
            data = response.json()
            time_activities = data.get('data', {}).get('timeActivitiesByUsers', [])
            
            shifts = []
            for user_activity in time_activities:
                if user_activity.get('userId') != user_id:
                    continue
                
                employee = self.get_employee_by_id(user_id)
                if not employee:
                    continue
                
                for shift in user_activity.get('shifts', []):
                    shift_obj = self._parse_shift(
                        shift, user_id, employee.full_name, 
                        employee.email, employee.title
                    )
                    if shift_obj:
                        shifts.append(shift_obj)
            
            return sorted(shifts, key=lambda s: s.clock_in)
            
        except Exception as e:
            logger.error(f"Error getting shift history: {e}")
            return []
    
    def get_time_off(self, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
        """Get time off records for date range"""
        # This would need to be implemented based on Connecteam's time-off API
        # For now, returning empty dict
        logger.warning("Time off API not yet implemented")
        return {}


# Example usage and testing
if __name__ == "__main__":
    # Initialize client
    client = ConnecteamClient(
        api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
        clock_id=7425182
    )
    
    # Test: Get all employees
    print("Fetching all employees...")
    employees = client.get_all_employees()
    print(f"Found {len(employees)} employees")
    
    # Test: Get today's shifts
    print("\nGetting today's shifts...")
    shifts = client.get_todays_shifts()
    for shift in shifts:
        status = "Working" if shift.is_active else "Completed"
        print(f"{shift.employee_name} ({shift.title}) - {status} - {shift.total_minutes:.1f} minutes")
    
    # Test: Get currently working
    print("\nCurrently working:")
    working = client.get_currently_working()
    for shift in working:
        print(f"- {shift.employee_name}: {shift.total_minutes:.1f} minutes so far")
