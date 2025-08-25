# Add this to your podfactory_sync.py or create a new file: auto_map_employees.py

import mysql.connector
import logging
from typing import List, Tuple, Optional
import re

class PodFactoryAutoMapper:
    def __init__(self, local_db_config, podfactory_db_config):
        self.local_db_config = local_db_config
        self.podfactory_db_config = podfactory_db_config
        self.logger = logging.getLogger(__name__)
        
    def get_unmapped_podfactory_users(self) -> List[Tuple[str, str, str]]:
        """Get all PodFactory users that aren't mapped yet"""
        # Connect to PodFactory
        pf_conn = mysql.connector.connect(**self.podfactory_db_config)
        pf_cursor = pf_conn.cursor()
        
        # Get recent active users from PodFactory
        pf_cursor.execute("""
            SELECT DISTINCT 
                user_email,
                user_name,
                user_role
            FROM report_actions
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            AND user_email IS NOT NULL
            AND user_email != ''
            ORDER BY user_email
        """)
        
        podfactory_users = pf_cursor.fetchall()
        pf_cursor.close()
        pf_conn.close()
        
        # Connect to local DB
        local_conn = mysql.connector.connect(**self.local_db_config)
        local_cursor = local_conn.cursor()
        
        # Filter out already mapped emails
        unmapped_users = []
        for email, name, role in podfactory_users:
            local_cursor.execute(
                "SELECT id FROM employee_podfactory_mapping_v2 WHERE podfactory_email = %s",
                (email,)
            )
            if not local_cursor.fetchone():
                unmapped_users.append((email, name, role))
        
        local_cursor.close()
        local_conn.close()
        
        return unmapped_users
    
    def find_employee_match(self, pf_name: str, pf_email: str) -> Optional[int]:
        """Try to find matching employee in local database"""
        conn = mysql.connector.connect(**self.local_db_config)
        cursor = conn.cursor()
        
        # Clean up the PodFactory name
        clean_name = pf_name.strip()
        
        # Try different matching strategies
        matching_queries = [
            # Exact name match
            ("SELECT id FROM employees WHERE LOWER(name) = LOWER(%s) AND is_active = 1", (clean_name,)),
            
            # Name without spaces
            ("SELECT id FROM employees WHERE LOWER(REPLACE(name, ' ', '')) = LOWER(REPLACE(%s, ' ', '')) AND is_active = 1", (clean_name,)),
            
            # First and last name match
            ("""SELECT id FROM employees 
                WHERE LOWER(name) LIKE LOWER(CONCAT('%', SUBSTRING_INDEX(%s, ' ', 1), '%'))
                AND LOWER(name) LIKE LOWER(CONCAT('%', SUBSTRING_INDEX(%s, ' ', -1), '%'))
                AND is_active = 1""", (clean_name, clean_name)),
            
            # Email username match (for emails like firstname.lastname@...)
            ("""SELECT id FROM employees 
                WHERE LOWER(REPLACE(name, ' ', '.')) = LOWER(%s)
                OR LOWER(REPLACE(name, ' ', '_')) = LOWER(%s)
                AND is_active = 1""", 
                (pf_email.split('@')[0].replace('shp', ''), pf_email.split('@')[0].replace('shp', '')))
        ]
        
        for query, params in matching_queries:
            cursor.execute(query, params)
            result = cursor.fetchone()
            if result:
                cursor.close()
                conn.close()
                return result[0]
        
        cursor.close()
        conn.close()
        return None
    
    def create_mapping(self, employee_id: int, pf_email: str, pf_name: str, confidence: str = 'MEDIUM'):
        """Create a new mapping"""
        conn = mysql.connector.connect(**self.local_db_config)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO employee_podfactory_mapping_v2 
                (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified)
                VALUES (%s, %s, %s, 0.8, %s, 0)
            """, (employee_id, pf_email, pf_name, confidence))
            
            conn.commit()
            self.logger.info(f"Created mapping: {pf_email} -> Employee ID {employee_id}")
            return True
            
        except mysql.connector.IntegrityError as e:
            self.logger.warning(f"Mapping already exists or constraint violation: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def auto_map_all(self):
        """Automatically map all unmapped PodFactory users"""
        unmapped_users = self.get_unmapped_podfactory_users()
        
        self.logger.info(f"Found {len(unmapped_users)} unmapped PodFactory users")
        
        mapped_count = 0
        no_match_users = []
        
        for pf_email, pf_name, pf_role in unmapped_users:
            employee_id = self.find_employee_match(pf_name, pf_email)
            
            if employee_id:
                if self.create_mapping(employee_id, pf_email, pf_name):
                    mapped_count += 1
            else:
                no_match_users.append((pf_email, pf_name, pf_role))
        
        # Report results
        self.logger.info(f"Successfully mapped {mapped_count} users")
        
        if no_match_users:
            self.logger.warning(f"Could not find matches for {len(no_match_users)} users:")
            for email, name, role in no_match_users:
                self.logger.warning(f"  - {email} ({name}) - {role}")
                
        return {
            'mapped': mapped_count,
            'unmapped': no_match_users
        }
    
    def create_new_employee_with_mapping(self, pf_email: str, pf_name: str, pf_role: str) -> Optional[int]:
        """Create a new employee and map them (for truly new employees)"""
        conn = mysql.connector.connect(**self.local_db_config)
        cursor = conn.cursor()
        
        try:
            # Create new employee
            cursor.execute("""
                INSERT INTO employees (name, email, is_active, hire_date)
                VALUES (%s, %s, 1, CURDATE())
            """, (pf_name, pf_email))
            
            employee_id = cursor.lastrowid
            
            # Create mapping
            cursor.execute("""
                INSERT INTO employee_podfactory_mapping_v2 
                (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified)
                VALUES (%s, %s, %s, 1.0, 'HIGH', 1)
            """, (employee_id, pf_email, pf_name))
            
            conn.commit()
            self.logger.info(f"Created new employee and mapping for {pf_name} ({pf_email})")
            return employee_id
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error creating employee: {e}")
            return None
        finally:
            cursor.close()
            conn.close()


# Add this to your podfactory_sync.py main sync method:
def sync_with_auto_mapping(self):
    """Enhanced sync that automatically maps new users"""
    # First, run auto-mapping
    mapper = PodFactoryAutoMapper(self.local_db_config, self.podfactory_db_config)
    mapping_results = mapper.auto_map_all()
    
    # Then run normal sync
    sync_results = self.sync_activities()
    
    # Log combined results
    self.logger.info(f"""
    Sync Complete:
    - New mappings created: {mapping_results['mapped']}
    - Unmapped users: {len(mapping_results['unmapped'])}
    - Activities synced: {sync_results['success']}
    """)
    
    return {
        'mappings': mapping_results,
        'sync': sync_results
    }


# Usage in your sync script:
if __name__ == "__main__":
    local_db = {
        'host': 'localhost',
        'user': 'root',
        'password': 'Nicholasbin0116$',
        'database': 'productivity_tracker'
    }
    
    podfactory_db = {
        'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
        'port': 25060,
        'user': 'doadmin',
        'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
        'database': 'pod-report-stag'
    }
    
    # Run auto-mapping
    mapper = PodFactoryAutoMapper(local_db, podfactory_db)
    mapper.auto_map_all()