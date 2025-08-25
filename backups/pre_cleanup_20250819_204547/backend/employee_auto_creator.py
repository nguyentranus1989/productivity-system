#!/usr/bin/env python3
"""
Auto-create employees from PodFactory data
"""
import pymysql
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

class EmployeeAutoCreator:
    def __init__(self, db_config):
        self.db_config = db_config
    
    def get_connection(self):
        """Get database connection"""
        return pymysql.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database']
        )
    
    def find_or_create_employee(self, user_name, user_email):
        """
        Find existing employee by name or create new one
        Returns: dict with employee_id and name
        """
        if not user_name:
            logger.warning(f"No user_name provided for email {user_email}")
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        try:
            # First, check if employee exists by exact name match
            cursor.execute("""
                SELECT id, name, email 
                FROM employees 
                WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
                LIMIT 1
            """, (user_name,))
            
            existing = cursor.fetchone()
            
            if existing:
                logger.info(f"Found existing employee: {existing['name']} (ID: {existing['id']})")
                
                # Add email mapping if not exists
                cursor.execute("""
                    INSERT IGNORE INTO employee_podfactory_mapping_v2 
                    (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified, created_at)
                    VALUES (%s, %s, %s, 1.0, 'HIGH', 1, NOW())
                """, (existing['id'], user_email, user_name))
                
                if cursor.rowcount > 0:
                    logger.info(f"Added new email mapping: {user_email} -> {existing['name']}")
                    conn.commit()
                
                return {'employee_id': existing['id'], 'name': existing['name']}
            
            # Employee doesn't exist, create new one
            logger.info(f"Creating new employee: {user_name}")
            
            # Generate a safe email if not provided or if it's a PodFactory email
            safe_email = user_email
            if '@colorecommerce.us' in user_email:
                # Extract base email without suffixes
                email_base = user_email.split('@')[0]
                # Remove common suffixes
                for suffix in ['shp', 'ship', 'pack', 'pick', 'label', 'film', 'heatpress', 'hp']:
                    if email_base.endswith(suffix):
                        email_base = email_base[:-len(suffix)]
                        break
                safe_email = f"{email_base}@colorecommerce.us"
            
            # Check if this email already exists
            cursor.execute("SELECT id FROM employees WHERE email = %s", (safe_email,))
            if cursor.fetchone():
                # Email exists, use a modified version
                safe_email = f"{email_base}_pf@colorecommerce.us"
            
            # Insert new employee
            cursor.execute("""
                INSERT INTO employees 
                (name, email, hire_date, is_active, is_new_employee, created_at, updated_at)
                VALUES (%s, %s, %s, 1, 1, NOW(), NOW())
            """, (user_name, safe_email, date.today()))
            
            new_employee_id = cursor.lastrowid
            
            # Create PodFactory mapping
            cursor.execute("""
                INSERT INTO employee_podfactory_mapping_v2 
                (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified, created_at)
                VALUES (%s, %s, %s, 1.0, 'HIGH', 1, NOW())
            """, (new_employee_id, user_email, user_name))
            
            conn.commit()
            logger.info(f"✅ Created employee: {user_name} (ID: {new_employee_id}) with email mapping {user_email}")
            
            return {'employee_id': new_employee_id, 'name': user_name}
            
        except Exception as e:
            logger.error(f"Error in find_or_create_employee: {str(e)}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

# Test function
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO)
    
    db_config = {
        'host': os.getenv('DB_HOST', 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com'),
        'port': int(os.getenv('DB_PORT', 25060)),
        'user': os.getenv('DB_USER', 'doadmin'),
        'password': os.getenv('DB_PASSWORD', 'AVNS_OWqdUdZ2Nw_YCkGI5Eu'),
        'database': os.getenv('DB_NAME', 'productivity_tracker')
    }
    
    creator = EmployeeAutoCreator(db_config)
    
    # Test with a fake employee
    result = creator.find_or_create_employee("Test Employee", "test.employee@colorecommerce.us")
    if result:
        print(f"Success: {result}")
    else:
        print("Failed to create/find employee")
