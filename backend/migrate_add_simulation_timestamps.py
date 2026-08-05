"""
Migration script to add simulation_timestamp columns to existing tables
for the Global MarketClock system.
"""
import sqlite3
from pathlib import Path

def migrate_database():
    db_path = Path(__file__).parent / "trading_platform.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add simulation_timestamp to orders table
        cursor.execute("ALTER TABLE orders ADD COLUMN simulation_timestamp DATETIME")
        print("Added simulation_timestamp to orders table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("simulation_timestamp already exists in orders table")
        else:
            print(f"Error adding to orders: {e}")
    
    try:
        # Add simulation_timestamp to order_events table
        cursor.execute("ALTER TABLE order_events ADD COLUMN simulation_timestamp DATETIME")
        print("Added simulation_timestamp to order_events table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("simulation_timestamp already exists in order_events table")
        else:
            print(f"Error adding to order_events: {e}")
    
    try:
        # Add simulation_timestamp to fills table
        cursor.execute("ALTER TABLE fills ADD COLUMN simulation_timestamp DATETIME")
        print("Added simulation_timestamp to fills table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("simulation_timestamp already exists in fills table")
        else:
            print(f"Error adding to fills: {e}")
    
    try:
        # Add simulation_timestamp to price_history_minute table
        cursor.execute("ALTER TABLE price_history_minute ADD COLUMN simulation_timestamp DATETIME")
        print("Added simulation_timestamp to price_history_minute table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("simulation_timestamp already exists in price_history_minute table")
        else:
            print(f"Error adding to price_history_minute: {e}")
    
    try:
        # Create market_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_sessions (
                id VARCHAR PRIMARY KEY,
                account_id VARCHAR,
                start_timestamp DATETIME NOT NULL,
                current_timestamp DATETIME NOT NULL,
                speed_multiplier FLOAT DEFAULT 1.0 NOT NULL,
                market_status VARCHAR DEFAULT 'open' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        print("Created market_sessions table")
    except sqlite3.OperationalError as e:
        print(f"Error creating market_sessions: {e}")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully")

if __name__ == "__main__":
    migrate_database()
