"""Typed application configuration loaded from environment and .env.

Model identifiers and thresholds live here and in .env only, never in code, so a
provider retirement is a configuration change (docs/11 deprecation guards).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CHARS_PER_TOKEN = 4


class Settings(BaseSettings):
    """Application settings with the VERITAS_ environment prefix."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="VERITAS_", extra="ignore")

    aws_region: str = "us-east-1"
    aws_profile: str = ""

    nova_micro_model_id: str = "amazon.nova-micro-v1:0"
    generator_model_id: str = "us.meta.llama3-3-70b-instruct-v1:0"

    embeddings_provider: str = "fastembed"  # fastembed or hash
    embeddings_model: str = "BAAI/bge-small-en-v1.5"

    chat_provider: str = "bedrock"  # bedrock or fake

    reranker_provider: str = "fastembed"  # fastembed or identity
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = 30

    spend_cap_usd: float = 5.0

    chunk_target_tokens: int = 300
    chunk_overlap_tokens: int = 45
    parent_max_tokens: int = 1200
    contextualize_max_tokens: int = 400

    data_dir: str = "data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()


def estimate_tokens(text: str) -> int:
    """Estimate a token count from character length (about 4 characters per token)."""
    return max(1, len(text) // CHARS_PER_TOKEN)
