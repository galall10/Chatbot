"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # LLM Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_temperature: float = 0.7
    gemini_max_tokens: int = 2048
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    redis_ttl_seconds: int = 86400  # 24 hours default
    
    # Memory Configuration
    max_history_tokens: int = 4000
    max_history_turns: int = 20
    
    # Application Configuration
    app_name: str = "LLM Chatbot Service"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    environment: str = "development"
    
    # CORS Configuration
    cors_origins: list[str] = ["*"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
