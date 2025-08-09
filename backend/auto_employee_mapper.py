#!/usr/bin/env python3
"""
Automated Employee Mapping System
- Detects new employees from both Connecteam and PodFactory
- Attempts intelligent mapping
- Alerts for manual review when needed
- Allows employees to show on dashboard even without clock times
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pymysql
from dotenv import load_dotenv
import re
from difflib import SequenceMatcher

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/employee_mapper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoEmployeeMapper:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('DB_HOST'),
            'port': int(os.getenv('DB_PORT')),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME')
        }
        
    def get_db_connection(self):
        return pymysql.connect(**self.db_config)
    
    def normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        # Remove special characters, convert to lowercase
        name = re.sub(r'[^a-zA-Z\s]', '', name).lower().strip()
        return ' '.join(name.split())  # Remove extra spaces
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names"""
        name1 = self.normalize_name(name1)
        name2 = self.normalize_name(name2)
        
        # Direct match
        if name1 == name2:
            return 1.0
            
        # Check if one is nickname of other (Eddie/Eduardo)
        if name1 in name2 or name2 in name1:
            return 0.9
            
        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, name1, name2).ratio()
    
    def find_unmapped_connecteam_users(self) -> List[Dict]:
        """Find Connecteam users not mapped to employees"""
        conn = self.get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get unmapped Connecteam users from recent shifts
        cursor.execute("""
            SELECT DISTINCT 
                ct.connecteam_id as user_id,
                MAX(ct.clock_in) as last_seen,
                COUNT(*) as shift_count
            FROM clock_times ct
            WHERE ct.connecteam_id IS NOT NULL
            AND ct.connecteam_id NOT IN (
                SELECT connecteam_user_id 
                FROM employees 
                WHERE connecteam_user_id IS NOT NULL
            )
            AND ct.clock_in >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY ct.connecteam_id
        """)
        
        unmapped = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return unmapped
    
    def find_unmapped_podfactory_users(self) -> List[Dict]:
        """Find PodFactory users not mapped to employees"""
        conn = self.get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get unique emails from PodFactory data
        cursor.execute("""
            SELECT 
                user_email,
                user_name,
                COUNT(*) as activity_count,
                SUM(items_count) as total_items,
                MAX(window_start) as last_activity
            FROM `pod-report-stag`.report_actions
            WHERE DATE(created_at) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            AND user_email NOT IN (
                SELECT podfactory_email 
                FROM productivity_tracker.employee_podfactory_mapping_v2
            )
            AND user_email IS NOT NULL
            AND user_email != ''
            GROUP BY user_email, user_name
            HAVING activity_count > 5  -- Only consider active users
        """)
        
        unmapped = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return unmapped
    
    def find_employees_without_mappings(self) -> List[Dict]:
        """Find active employees without Connecteam or PodFactory mappings"""
        conn = self.get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                e.id,
                e.name,
                e.email,
                e.connecteam_user_id,
                COUNT(DISTINCT epf.podfactory_email) as podfactory_mappings
            FROM employees e
            LEFT JOIN employee_podfactory_mapping_v2 epf ON e.id = epf.employee_id
            WHERE e.is_active = 1
            GROUP BY e.id
            HAVING e.connecteam_user_id IS NULL OR podfactory_mappings = 0
        """)
        
        employees = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return employees
    
    def attempt_auto_mapping(self, unmapped_connecteam, unmapped_podfactory, employees_without_mappings):
        """Attempt to automatically map users based on name similarity"""
        mappings = {
            'confident': [],  # High confidence mappings (>0.8 similarity)
            'possible': [],   # Medium confidence (0.6-0.8)
            'manual_review': []  # Low confidence or conflicts
        }
        
        # Try to map PodFactory users to employees
        for pf_user in unmapped_podfactory:
            best_match = None
            best_score = 0
            
            for employee in employees_without_mappings:
                score = self.calculate_name_similarity(pf_user['user_name'], employee['name'])
                if score > best_score:
                    best_score = score
                    best_match = employee
            
            if best_match and best_score > 0.8:
                mappings['confident'].append({
                    'type': 'podfactory',
                    'employee_id': best_match['id'],
                    'employee_name': best_match['name'],
                    'podfactory_email': pf_user['user_email'],
                    'podfactory_name': pf_user['user_name'],
                    'confidence': best_score,
                    'activities': pf_user['activity_count'],
                    'items': pf_user['total_items']
                })
            elif best_match and best_score > 0.6:
                mappings['possible'].append({
                    'type': 'podfactory',
                    'employee_id': best_match['id'],
                    'employee_name': best_match['name'],
                    'podfactory_email': pf_user['user_email'],
                    'podfactory_name': pf_user['user_name'],
                    'confidence': best_score,
                    'activities': pf_user['activity_count'],
                    'items': pf_user['total_items']
                })
            else:
                mappings['manual_review'].append({
                    'type': 'podfactory_unmapped',
                    'email': pf_user['user_email'],
                    'name': pf_user['user_name'],
                    'activities': pf_user['activity_count'],
                    'items': pf_user['total_items'],
                    'last_activity': pf_user['last_activity']
                })
        
        return mappings
    
    def create_provisional_employees(self, unmapped_users):
        """Create provisional employee records for unmapped users"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        created = []
        for user in unmapped_users:
            if user['type'] == 'podfactory_unmapped':
                # Check if employee might already exist with different email
                cursor.execute("""
                    SELECT id, name FROM employees 
                    WHERE name LIKE %s AND is_active = 1
                """, (f"%{user['name'].split()[0]}%",))
                
                existing = cursor.fetchone()
                if not existing:
                    # Create provisional employee
                    cursor.execute("""
                        INSERT INTO employees (name, email, is_active, hire_date, notes)
                        VALUES (%s, %s, 1, CURDATE(), 'Auto-created from PodFactory - needs review')
                    """, (user['name'], user['email']))
                    
                    employee_id = cursor.lastrowid
                    
                    # Add PodFactory mapping
                    cursor.execute("""
                        INSERT INTO employee_podfactory_mapping_v2 
                        (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified)
                        VALUES (%s, %s, %s, 1.0, 'provisional', 0)
                    """, (employee_id, user['email'], user['name']))
                    
                    created.append({
                        'id': employee_id,
                        'name': user['name'],
                        'email': user['email'],
                        'source': 'PodFactory'
                    })
                    
                    logger.info(f"Created provisional employee: {user['name']} ({user['email']})")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return created
    
    def generate_admin_report(self, mappings, provisional_employees):
        """Generate report for admin review"""
        report = []
        report.append("=" * 80)
        report.append(f"EMPLOYEE MAPPING REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        # Confident mappings
        if mappings['confident']:
            report.append("\n✅ HIGH CONFIDENCE MAPPINGS (Auto-applied):")
            for m in mappings['confident']:
                report.append(f"  - {m['employee_name']} → {m['podfactory_name']} ({m['podfactory_email']})")
                report.append(f"    Confidence: {m['confidence']:.2%}, Activities: {m['activities']}, Items: {m['items']}")
        
        # Possible mappings
        if mappings['possible']:
            report.append("\n⚠️  POSSIBLE MAPPINGS (Need Review):")
            for m in mappings['possible']:
                report.append(f"  - {m['employee_name']} → {m['podfactory_name']} ({m['podfactory_email']})")
                report.append(f"    Confidence: {m['confidence']:.2%}, Activities: {m['activities']}, Items: {m['items']}")
        
        # Provisional employees
        if provisional_employees:
            report.append("\n🆕 PROVISIONAL EMPLOYEES CREATED:")
            for emp in provisional_employees:
                report.append(f"  - {emp['name']} ({emp['email']}) - ID: {emp['id']}")
                report.append(f"    Source: {emp['source']} - NEEDS CONNECTEAM MAPPING")
        
        # Manual review needed
        if mappings['manual_review']:
            report.append("\n❌ MANUAL REVIEW REQUIRED:")
            for item in mappings['manual_review']:
                if item['type'] == 'podfactory_unmapped':
                    report.append(f"  - PodFactory: {item['name']} ({item['email']})")
                    report.append(f"    Activities: {item['activities']}, Items: {item['items']}")
        
        return "\n".join(report)
    
    def apply_confident_mappings(self, mappings):
        """Apply high-confidence mappings automatically"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        applied = 0
        for mapping in mappings['confident']:
            if mapping['type'] == 'podfactory':
                cursor.execute("""
                    INSERT INTO employee_podfactory_mapping_v2 
                    (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified)
                    VALUES (%s, %s, %s, %s, 'high', 1)
                    ON DUPLICATE KEY UPDATE
                    similarity_score = VALUES(similarity_score),
                    confidence_level = 'high',
                    is_verified = 1
                """, (mapping['employee_id'], mapping['podfactory_email'], 
                      mapping['podfactory_name'], mapping['confidence']))
                applied += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return applied
    
    def run(self):
        """Main execution"""
        logger.info("Starting employee mapping check...")
        
        # Find unmapped users
        unmapped_connecteam = self.find_unmapped_connecteam_users()
        unmapped_podfactory = self.find_unmapped_podfactory_users()
        employees_without_mappings = self.find_employees_without_mappings()
        
        logger.info(f"Found {len(unmapped_connecteam)} unmapped Connecteam users")
        logger.info(f"Found {len(unmapped_podfactory)} unmapped PodFactory users")
        logger.info(f"Found {len(employees_without_mappings)} employees without complete mappings")
        
        # Attempt auto-mapping
        mappings = self.attempt_auto_mapping(
            unmapped_connecteam, 
            unmapped_podfactory, 
            employees_without_mappings
        )
        
        # Apply confident mappings
        applied = self.apply_confident_mappings(mappings)
        logger.info(f"Applied {applied} high-confidence mappings")
        
        # Create provisional employees for unmapped PodFactory users
        provisional = self.create_provisional_employees(mappings['manual_review'])
        logger.info(f"Created {len(provisional)} provisional employees")
        
        # Generate report
        report = self.generate_admin_report(mappings, provisional)
        
        # Save report
        with open('logs/employee_mapping_report.txt', 'w') as f:
            f.write(report)
        
        # Also log key points
        logger.info(report)
        
        # Send alert if manual review needed
        if mappings['possible'] or mappings['manual_review'] or provisional:
            self.send_admin_alert(report)
        
        return report
    
    def send_admin_alert(self, report):
        """Send alert to admin (implement email/slack/etc)"""
        # For now, just create an alert file
        alert_file = f"logs/ADMIN_ALERT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(alert_file, 'w') as f:
            f.write("ADMIN ACTION REQUIRED\n")
            f.write("=" * 50 + "\n")
            f.write(report)
        
        logger.warning(f"Admin alert created: {alert_file}")

if __name__ == "__main__":
    mapper = AutoEmployeeMapper()
    mapper.run()
