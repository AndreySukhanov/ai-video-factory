from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

_is_sqlite = settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite")

# timeout=30 — сколько секунд sqlite3 ждёт снятия блокировки записи,
# прежде чем бросить "database is locked" (API и RQ-воркер пишут конкурентно).
connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args=connect_args)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        # WAL позволяет читать во время записи; busy_timeout дублирует timeout
        # на уровне PRAGMA для соединений, переживших реконнект.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
