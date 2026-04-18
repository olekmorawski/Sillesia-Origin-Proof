from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

DINO_DIM_MASK: list[int] = list(range(0, 384, 6))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: str = ""
    default_model: str = "black-forest-labs/flux.2-klein-4b"

    wallet_private_key: str = ""
    contract_address: str = ""
    rpc_url: str = "https://sepolia.base.org"

    redis_url: str = "redis://localhost:6379"

    c2pa_cert_pem: Optional[str] = None
    c2pa_private_key_pem: Optional[str] = None


settings = Settings()
