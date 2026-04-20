"""Export OpenAPI schema to JSON without starting a server or touching the DB."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set dummy env before importing main to satisfy pydantic Settings
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost/db")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_dummy")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_dummy")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon_dummy")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "svc_dummy")
os.environ.setdefault("R2_ACCOUNT_ID", "acc")
os.environ.setdefault("R2_ACCESS_KEY_ID", "akid")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "sk")
os.environ.setdefault("R2_BUCKET_NAME", "metareverse-media")
os.environ.setdefault("R2_ENDPOINT", "https://example.r2.cloudflarestorage.com")
os.environ.setdefault("META_APP_ID", "0")
os.environ.setdefault("META_APP_SECRET", "secret")
os.environ.setdefault("RESEND_API_KEY", "re_dummy")
os.environ.setdefault("META_MODE", "mock")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "dummy")

from main import app  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, indent=2)
print(f"Wrote {out}")
