"""
Migration script to add IBKT columns to user_categories table
"""
import sqlite3
import os
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get the database path from the environment or use the default
DB_PATH = os.environ.get('DB_PATH', 'AdaptiveLearning.db')

def migrate_database():
    """Add IBKT columns to user_categories table."""
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if the columns already exist
        cursor.execute('PRAGMA table_info(user_categories)')
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add parameter_history column if it doesn't exist
        if 'parameter_history' not in column_names:
            logger.info("Adding parameter_history column to user_categories table")
            cursor.execute('ALTER TABLE user_categories ADD COLUMN parameter_history TEXT DEFAULT "{}"')
        
        # Add last_update column if it doesn't exist
        if 'last_update' not in column_names:
            logger.info("Adding last_update column to user_categories table")
            current_time = datetime.now().isoformat()
            cursor.execute(f'ALTER TABLE user_categories ADD COLUMN last_update TEXT DEFAULT "{current_time}"')
        
        # Add response_count column if it doesn't exist
        if 'response_count' not in column_names:
            logger.info("Adding response_count column to user_categories table")
            cursor.execute('ALTER TABLE user_categories ADD COLUMN response_count INTEGER DEFAULT 0')
        
        # Add use_ibkt column if it doesn't exist
        if 'use_ibkt' not in column_names:
            logger.info("Adding use_ibkt column to user_categories table")
            cursor.execute('ALTER TABLE user_categories ADD COLUMN use_ibkt BOOLEAN DEFAULT 1')
        
        # Initialize parameter_history for existing records
        cursor.execute('SELECT id FROM user_categories WHERE parameter_history IS NULL OR parameter_history = "{}"')
        categories_to_update = cursor.fetchall()
        
        empty_history = json.dumps({
            'responses': [],
            'p_transit_history': [],
            'p_slip_history': [],
            'p_guess_history': []
        })
        
        for category_id in categories_to_update:
            cursor.execute('UPDATE user_categories SET parameter_history = ? WHERE id = ?', 
                          (empty_history, category_id[0]))
            logger.info(f"Initialized parameter_history for category_id {category_id[0]}")
        
        # Commit changes
        conn.commit()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database() 