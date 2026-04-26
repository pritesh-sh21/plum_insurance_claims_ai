from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_mini_model: str = "gpt-4o-mini"
    policy_file_path: str = "./core/policy_terms.json"
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()