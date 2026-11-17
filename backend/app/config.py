from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """All runtime configuration. Every value can be set through an env var of the same name."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./data/workflowwise.db"
    auto_create_tables: bool = True

    # Auth: "supabase" verifies Supabase JWTs, "dev" accepts `Bearer dev:<email>` tokens (local only).
    auth_mode: str = "dev"
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # legacy HS256 secret; JWKS is used when unset
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "documents"

    # Storage: "supabase" or "local"
    storage_backend: str = "local"
    local_storage_dir: str = "./data/uploads"

    # AI providers: "gemini", "local" or "auto" (gemini when a key is present).
    llm_provider: str = "auto"
    embedding_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # Background jobs: when set, ingestion runs on an RQ worker; otherwise in-process.
    redis_url: str | None = None

    cors_origins: str = "http://localhost:3000"
    stale_after_days: int = 120
    answer_min_score: float = 0.2
    max_upload_mb: int = 25

    def model_post_init(self, _ctx) -> None:
        # Relative local paths are relative to backend/, whatever directory the server was started from.
        if self.database_url.startswith("sqlite:///./"):
            self.database_url = f"sqlite:///{(BACKEND_DIR / self.database_url[len('sqlite:///./'):]).as_posix()}"
        if not Path(self.local_storage_dir).is_absolute():
            self.local_storage_dir = str((BACKEND_DIR / self.local_storage_dir).resolve())

    @property
    def use_gemini_llm(self) -> bool:
        return self.llm_provider == "gemini" or (self.llm_provider == "auto" and bool(self.gemini_api_key))

    @property
    def use_gemini_embeddings(self) -> bool:
        return self.embedding_provider == "gemini" or (
            self.embedding_provider == "auto" and bool(self.gemini_api_key)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
