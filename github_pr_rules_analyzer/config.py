"""
Application configuration management
"""

import os
from typing import Optional
from pydantic import BaseSettings, Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # GitHub API Configuration
    github_token: str = Field(..., env="GITHUB_TOKEN")
    github_api_base_url: str = Field("https://api.github.com", env="GITHUB_API_BASE_URL")
    
    # LLM Service Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_api_base_url: str = Field("https://api.openai.com/v1", env="OPENAI_API_BASE_URL")
    openai_model: str = Field("gpt-4", env="OPENAI_MODEL")
    
    # Database Configuration
    database_url: str = Field("sqlite:///./github_pr_rules.db", env="DATABASE_URL")
    
    # Application Configuration
    app_name: str = Field("GitHub PR Rules Analyzer", env="APP_NAME")
    app_version: str = Field("1.0.0", env="APP_VERSION")
    debug: bool = Field(False, env="DEBUG")
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    
    # API Configuration
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Data Collection Configuration
    max_github_retries: int = Field(3, env="MAX_GITHUB_RETRIES")
    github_retry_delay: float = Field(1.0, env="GITHUB_RETRY_DELAY")
    max_prs_per_repo: int = Field(1000, env="MAX_PRS_PER_REPO")
    batch_size: int = Field(50, env="BATCH_SIZE")
    
    # LLM Configuration
    max_llm_retries: int = Field(3, env="MAX_LLM_RETRIES")
    llm_retry_delay: float = Field(2.0, env="LLM_RETRY_DELAY")
    max_tokens: int = Field(2000, env="MAX_TOKENS")
    temperature: float = Field(0.1, env="TEMPERATURE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_database_url() -> str:
    """Get database URL from settings"""
    return get_settings().database_url


def get_github_headers() -> dict:
    """Get GitHub API headers with authentication"""
    settings = get_settings()
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"{settings.app_name}/{settings.app_version}"
    }


def get_openai_headers() -> dict:
    """Get OpenAI API headers"""
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json"
    }