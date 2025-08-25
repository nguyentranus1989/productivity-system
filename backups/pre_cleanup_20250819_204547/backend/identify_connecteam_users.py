#!/usr/bin/env python3
"""
Script to identify unmapped Connecteam users by pulling their profile data
"""
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import pymysql

load_dotenv()

class ConnecteamUserIdentifier:
    def __init__(self):
        self.api_key = os.getenv('CONNECTEAM_API_KEY')
        self.clock_id = os.getenv('CONNECTEAM_CLOCK_ID')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
    def get_user_details(self, user_id):
        """Get user details from Connecteam API"""
        # Try the users endpoint
        url = f'https://api.connecteam.com/api/v1/users/{user_id}'
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            try:
                data = response.json()
                return {
                    'id': user_id,
                    'firstName': data.get('firstName', ''),
                    'lastName': data.get('lastName', ''),
                    'email': data.get('email', ''),
                    'phone': data.get('phone', '')
                }
            except:
                pass
        
        # Try getting from shifts endpoint
        return self.get_user_from_shifts(user_id)
    
    def get_user_from_shifts(self, user_id):
        """Try to get user info from their shift data"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Try to get shift details
        url = f'https://api.connecteam.com/api/v1/timeclock/{self.clock_id}/shifts'
        params = {
            'fromDate': today,
            'toDate': today,
            'userId': user_id
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            try:
                data = response.json()
                shifts = data.get('shifts', [])
                if shifts:
                    shift = shifts[0]
                    return {
                        'id': user_id,
                        'firstName': shift.get('firstName', ''),
                        'lastName': shift.get('lastName', ''),
                        'email': '',  # Not available in shift data
                        'phone': ''
                    }
            except:
                pass
        
        return None
    
    def check_unmapped_users(self):
        """Check for unmapped Connecteam users in today's clock times"""
        # Connect to database
        conn = pymysql.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        cursor = conn.cursor()
        
        # Get all unique Connecteam user IDs from recent clock times
        cursor.execute("""
            SELECT DISTINCT source_id 
            FROM clock_times 
            WHERE source = 'connecteam' 
            AND source_id IS NOT NULL
            AND DATE(clock_in) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            AND source_id NOT IN (
                SELECT connecteam_user_id 
                FROM employees 
                WHERE connecteam_user_id IS NOT NULL
            )
        """)
        
        unmapped_ids = cursor.fetchall()
        
        if not unmapped_ids:
            print("No unmapped Connecteam users found in recent clock times.")
            
            # Let's check the sync logs for errors
            print("\nChecking Connecteam sync logs for unmapped users...")
            # This would check your sync logs for any "Employee not found" errors
            
        cursor.close()
        conn.close()
        
        return [row[0] for row in unmapped_ids]

# Main execution
if __name__ == "__main__":
    identifier = ConnecteamUserIdentifier()
    
    # Check specific user
    print("Checking user 12132089...")
    user_details = identifier.get_user_details('12132089')
    
    if user_details:
        print(f"\nFound user details:")
        print(f"ID: {user_details['id']}")
        print(f"Name: {user_details['firstName']} {user_details['lastName']}")
        print(f"Email: {user_details['email']}")
        print(f"Phone: {user_details['phone']}")
    else:
        print("Could not retrieve user details from API")
    
    # Check for all unmapped users
    print("\n\nChecking for all unmapped Connecteam users...")
    unmapped = identifier.check_unmapped_users()
    
    if unmapped:
        print(f"Found {len(unmapped)} unmapped users:")
        for user_id in unmapped:
            details = identifier.get_user_details(user_id)
            if details:
                print(f"- {user_id}: {details['firstName']} {details['lastName']}")
            else:
                print(f"- {user_id}: Could not retrieve details")
