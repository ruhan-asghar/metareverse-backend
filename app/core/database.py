import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from app.core.config import get_settings

psycopg2.extras.register_uuid()


def get_connection():
    settings = get_settings()
    return psycopg2.connect(
        settings.database_url.replace("Meta@reverse123", "Meta%40reverse123"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_db_cursor():
    with get_db() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()
