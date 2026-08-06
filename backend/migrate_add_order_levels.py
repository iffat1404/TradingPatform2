"""
Migration: Add target_price and stop_loss columns to orders table.

These columns are used for trade planning and decision scoring.
"""

from sqlalchemy import text
from app.core.db import engine

def migrate():
    with engine.connect() as conn:
        # Check if columns already exist
        inspector_query = text("""
            PRAGMA table_info(orders);
        """)
        result = conn.execute(inspector_query)
        columns = {row[1] for row in result}  # row[1] is the column name

        # Add target_price if it doesn't exist
        if 'target_price' not in columns:
            print("Adding target_price column...")
            conn.execute(text("""
                ALTER TABLE orders ADD COLUMN target_price FLOAT DEFAULT NULL;
            """))
            conn.commit()
            print("✓ Added target_price column")
        else:
            print("✓ target_price column already exists")

        # Add stop_loss if it doesn't exist
        if 'stop_loss' not in columns:
            print("Adding stop_loss column...")
            conn.execute(text("""
                ALTER TABLE orders ADD COLUMN stop_loss FLOAT DEFAULT NULL;
            """))
            conn.commit()
            print("✓ Added stop_loss column")
        else:
            print("✓ stop_loss column already exists")

        print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
