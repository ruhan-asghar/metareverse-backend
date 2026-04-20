from datetime import datetime, timezone, timedelta
from app.core.database import get_connection
from app.core.encryption import decrypt_token
from app.services.meta import get_meta_client


def ping_token_for_page(page_id: str) -> str:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""SELECT encrypted_access_token, token_expires_at
                             FROM pages WHERE id=%s""", (page_id,))
            row = cur.fetchone()
            if not row:
                return "not_found"
            if not row["encrypted_access_token"]:
                cur.execute("UPDATE pages SET status='token_expired' WHERE id=%s", (page_id,))
                return "token_expired"
            try:
                token = decrypt_token(bytes(row["encrypted_access_token"]))
            except Exception:
                cur.execute("UPDATE pages SET status='token_expired' WHERE id=%s", (page_id,))
                return "token_expired"
            ok = get_meta_client().ping_token(token)
            if not ok:
                cur.execute("UPDATE pages SET status='token_expired' WHERE id=%s", (page_id,))
                return "token_expired"
            if row["token_expires_at"] and row["token_expires_at"] < datetime.now(timezone.utc) + timedelta(days=7):
                cur.execute("UPDATE pages SET status='token_expiring' WHERE id=%s", (page_id,))
                return "token_expiring"
            cur.execute("UPDATE pages SET status='ready' WHERE id=%s", (page_id,))
            return "ready"
    finally:
        conn.close()
