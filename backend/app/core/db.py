from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Create SQLite engine with WAL mode for better concurrency
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},  # Needed for SQLite
    # Websocket fan-out plus normal HTTP traffic can outgrow the 5+10 default pool; a
    # starved pool takes down every DB-backed route at once, so keep real headroom and
    # recycle idle connections rather than blocking indefinitely on checkout.
    pool_size=20,
    max_overflow=30,
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
)

# Enable WAL mode for better concurrency (per Section 16.1)
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()