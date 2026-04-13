from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Clerk
    clerk_secret_key: str
    clerk_webhook_secret: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str

    # Cloudflare R2
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "metareverse-media"
    r2_endpoint: str

    # Meta / Facebook
    meta_app_id: str
    meta_app_secret: str

    # Resend
    resend_api_key: str = ""

    # Cloudflare
    cloudflare_api_token: str = ""

    # App
    environment: str = "development"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://landing-rho-seven-89.vercel.app",
        "https://dashboard-six-swart-26.vercel.app",
    ]
    encryption_key: str = ""  # auto-derived from clerk_secret_key if empty

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
