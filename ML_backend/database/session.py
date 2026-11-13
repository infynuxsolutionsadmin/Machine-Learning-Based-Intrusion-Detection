"""
session.py - SQLite Connection and Session Management for MANET Backend.
Configures WAL mode, foreign key constraints, connection timeouts, and thread safety.
"""
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .base import Base

# Directory containing database
DB_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("MANET_DB_PATH", DB_DIR / "manet_records.db"))

# Global write lock to serialize concurrent SQLite writes across worker threads
db_write_lock = threading.Lock()


def get_sqlite_url(db_path: Path | str = DEFAULT_DB_PATH) -> str:
    """Resolve an absolute, normalized SQLite URL."""
    p = Path(db_path).resolve()
    # On Windows, path representation requires forward slashes for sqlite url
    return f"sqlite:///{p.as_posix()}"


def create_db_engine(db_path: Path | str = DEFAULT_DB_PATH) -> Engine:
    """Create a configured SQLAlchemy Engine for SQLite."""
    p = Path(db_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    url = get_sqlite_url(p)
    new_engine = create_engine(
        url,
        connect_args={
            "timeout": 30.0,
            "check_same_thread": False,
        },
        future=True,
    )

    # Attach event listeners to enable SQLite WAL mode and foreign key enforcement
    @event.listens_for(new_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA wal_autocheckpoint=256;")
        cursor.close()

    return new_engine


# Primary application engine and session factory
engine = create_db_engine(DEFAULT_DB_PATH)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def safe_wal_checkpoint(target_engine: Engine = engine) -> Dict[str, Any]:
    """
    Execute a safe, isolated PASSIVE WAL checkpoint on the target SQLite engine.
    
    Guarantees:
      - Runs outside any active ingestion transaction on an independent connection.
      - Uses PRAGMA wal_checkpoint(PASSIVE), which checkpoints as many frames as
        possible without blocking concurrent readers or writers.
      - Never raises exceptions; failures or busy states are captured in the return dict.
      - Keeps checkpoint diagnostics strictly separate from persistence status.
    
    Returns:
      dict with keys:
        - checkpoint_status: 'COMPLETED' (busy=0), 'PARTIAL' (busy=1, checkpointed_frames>0),
                             'BUSY' (busy=1, checkpointed_frames=0), or 'ERROR'
        - busy: Optional[int] (0 or 1)
        - log_frames: Optional[int] (frames currently in WAL)
        - checkpointed_frames: Optional[int] (frames successfully moved to database file)
        - error: Optional[str]
    """
    diag: Dict[str, Any] = {
        "checkpoint_status": "PENDING",
        "busy": None,
        "log_frames": None,
        "checkpointed_frames": None,
        "error": None,
    }
    try:
        raw_conn = target_engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
            row = cursor.fetchone()
            cursor.close()
            if row:
                busy = int(row[0])
                log_f = int(row[1])
                ckpt_f = int(row[2])
                diag["busy"] = busy
                diag["log_frames"] = log_f
                diag["checkpointed_frames"] = ckpt_f
                if busy == 0:
                    diag["checkpoint_status"] = "COMPLETED"
                elif ckpt_f > 0:
                    diag["checkpoint_status"] = "PARTIAL"
                else:
                    diag["checkpoint_status"] = "BUSY"
            else:
                diag["checkpoint_status"] = "COMPLETED"
        finally:
            raw_conn.close()
    except Exception as exc:
        diag["checkpoint_status"] = "ERROR"
        diag["error"] = str(exc)
    return diag


def init_db(target_engine: Engine = engine) -> None:
    """
    Controlled database initialization.
    Ensures parent directories exist, pragma settings are executed,
    and metadata tables are created.
    """
    from . import models  # Ensure all ORM models are registered with Base.metadata
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields an independent database session per request
    and guarantees its disposal in a finally block.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_write_session() -> Generator[Session, None, None]:
    """
    Context manager for database write operations.
    Serializes writes using `db_write_lock` and provides explicit transaction boundaries.
    """
    with db_write_lock:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

