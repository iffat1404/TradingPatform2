"""
Migration: Decision Intelligence Engine.

Adds the trade-plan columns and the auto-journal flag to existing tables.
`Base.metadata.create_all` handles brand-new tables (trade_decisions) on startup, but it
never ALTERs an existing table — hence this script.

Safe to re-run: every step checks whether the column already exists.

Usage (from backend/, venv active):
    python migrate_add_decision_intelligence.py
"""
import sqlite3
import sys
from pathlib import Path

from app.core.config import settings

# Columns to add: (table, column, type)
NEW_COLUMNS = [
    ("orders", "target_price", "FLOAT"),
    ("orders", "stop_loss", "FLOAT"),
    ("journal_entries", "is_auto", "BOOLEAN NOT NULL DEFAULT 0"),
    # News-driven journaling: which headline the trader says drove the trade.
    ("journal_entries", "news_article_id", "VARCHAR"),
]


def _db_path() -> Path:
    """Resolve the SQLite file from DATABASE_URL rather than hardcoding a name."""
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        raise SystemExit(f"This migration only supports SQLite, got: {url}")
    # sqlite:///./nomura_stp.db  ->  ./nomura_stp.db
    raw = url.split("///", 1)[1] if "///" in url else url.split("//", 1)[1]
    path = Path(raw)
    return path if path.is_absolute() else (Path(__file__).parent / raw).resolve()


def _columns(cursor, table: str) -> set:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def migrate_database() -> int:
    db_path = _db_path()
    if not db_path.exists():
        print(f"No database at {db_path} — nothing to migrate.")
        print("It will be created with the new schema on first backend start.")
        return 0

    print(f"Migrating {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    changed = 0

    try:
        for table, column, coltype in NEW_COLUMNS:
            if not _table_exists(cursor, table):
                print(f"  - {table}: table not present yet, skipping (create_all will build it)")
                continue
            if column in _columns(cursor, table):
                print(f"  = {table}.{column} already present")
                continue
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            print(f"  + {table}.{column} added")
            changed += 1

        conn.commit()
    finally:
        conn.close()

    # trade_decisions is a brand-new table, so create_all builds it on next startup.
    print(f"\nDone — {changed} column(s) added.")
    print("The trade_decisions and level_alerts tables are created automatically on startup.")
    print(
        "\nNote: journal_entries.rationale stays NOT NULL on pre-existing databases "
        "(SQLite cannot drop a NOT NULL constraint without rebuilding the table). "
        "Auto-logged entries therefore store an empty string rather than NULL; the code "
        "treats empty and NULL identically as 'needs annotation'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(migrate_database())
