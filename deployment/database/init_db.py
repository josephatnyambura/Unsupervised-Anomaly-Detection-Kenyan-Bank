"""
Database Initialization Script
Sets up PostgreSQL database and loads initial schema
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database initialization and schema setup"""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME', 'anomaly_detection')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'postgres')
    
    def create_database(self):
        """Create the database if it doesn't exist"""
        try:
            # Connect to default postgres database
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(
                f"SELECT 1 FROM pg_database WHERE datname = '{self.database}'"
            )
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(f"CREATE DATABASE {self.database}")
                logger.info(f"✓ Database '{self.database}' created")
            else:
                logger.info(f"✓ Database '{self.database}' already exists")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            raise
    
    def load_schema(self):
        """Load SQL schema from file"""
        try:
            # Connect to anomaly_detection database
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            cursor = conn.cursor()
            
            # Read schema file
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Execute schema
            cursor.execute(schema_sql)
            conn.commit()
            
            logger.info("✓ Schema loaded successfully")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            raise
    
    def verify_setup(self):
        """Verify database setup"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'anomaly_detection'
            """)
            tables = cursor.fetchall()
            
            logger.info("✓ Database verification:")
            logger.info(f"  - Tables found: {len(tables)}")
            for table in tables:
                logger.info(f"    • {table[0]}")
            
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying setup: {e}")
            return False
    
    def initialize(self):
        """Complete initialization process"""
        logger.info("Starting database initialization...")
        logger.info("="*60)
        
        # Create database
        self.create_database()
        
        # Load schema
        self.load_schema()
        
        # Verify
        success = self.verify_setup()
        
        logger.info("="*60)
        if success:
            logger.info("✓ Database initialization complete!")
        else:
            logger.error("✗ Database initialization failed!")
        
        return success


if __name__ == '__main__':
    initializer = DatabaseInitializer()
    initializer.initialize()

