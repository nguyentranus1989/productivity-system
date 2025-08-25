"""Database connection manager with connection pooling"""
import mysql.connector
from mysql.connector import pooling
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any
import logging
from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manage database connections with connection pooling"""
    
    def __init__(self, pool_size: int = 5):
        self.pool_size = pool_size
        self._pool: Optional[pooling.MySQLConnectionPool] = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool"""
        try:
            config = {
                'host': Config.DB_HOST,
		'port': Config.DB_PORT,
                'user': Config.DB_USER,
                'password': Config.DB_PASSWORD,
                'database': Config.DB_NAME,
                'pool_size': self.pool_size,
                'pool_reset_session': True,
                'autocommit': False,
                'raise_on_warnings': True
            }
            
            self._pool = pooling.MySQLConnectionPool(
                pool_name="productivity_pool",
                **config
            )
            logger.info(f"Database connection pool initialized with {self.pool_size} connections")
            
        except mysql.connector.Error as e:
            logger.error(f"Error initializing database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        connection = None
        try:
            connection = self._pool.get_connection()
            yield connection
        except mysql.connector.Error as e:
            logger.error(f"Database error: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
    
    @contextmanager
    def get_cursor(self, dictionary: bool = False):
        """Get a cursor with automatic connection management"""
        with self.get_connection() as connection:
            cursor = connection.cursor(dictionary=dictionary)
            try:
                yield cursor
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()
    
    def execute_query(self, query: str, params: tuple = None, dictionary: bool = True) -> list:
        """Execute a SELECT query and return results"""
        with self.get_cursor(dictionary=dictionary) as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()
    
    def execute_one(self, query: str, params: tuple = None, dictionary: bool = True) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return single result"""
        with self.get_cursor(dictionary=dictionary) as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchone()
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT, UPDATE, or DELETE query"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
    
    def execute_many(self, query: str, data: list) -> int:
        """Execute many INSERT, UPDATE, or DELETE queries"""
        with self.get_cursor() as cursor:
            cursor.executemany(query, data)
            return cursor.rowcount
    
    def close_pool(self):
        """Close all connections in the pool"""
        if self._pool:
            # Close all connections
            logger.info("Closing database connection pool")
    
    # Compatibility methods for existing code
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return one result (alias for execute_one)"""
        return self.execute_one(query, params)
    
    def fetch_all(self, query: str, params: tuple = None) -> list:
        """Execute a SELECT query and return all results (alias for execute_query)"""
        return self.execute_query(query, params)
    
    # Method aliases for MySQL compatibility
    fetchone = fetch_one
    fetchall = fetch_all

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions
def get_db():
    """Get database manager instance"""
    return db_manager

def execute_query(query: str, params: tuple = None, dictionary: bool = True) -> list:
    """Execute a query using the global database manager"""
    return db_manager.execute_query(query, params, dictionary)

def execute_one(query: str, params: tuple = None, dictionary: bool = True) -> Optional[Dict[str, Any]]:
    """Execute a query and get one result using the global database manager"""
    return db_manager.execute_one(query, params, dictionary)

def execute_update(query: str, params: tuple = None) -> int:
    """Execute an update query using the global database manager"""
    return db_manager.execute_update(query, params)
