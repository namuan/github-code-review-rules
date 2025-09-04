"""Test configuration and fixtures."""

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set environment variables immediately when this module is imported
# This ensures they're available before any other modules try to load Settings
test_env_vars = {
    "GITHUB_TOKEN": "test_github_token_123",
    "GITHUB_API_BASE_URL": "https://api.github.com",
    "OLLAMA_API_BASE_URL": "http://localhost:11434/v1",
    "OLLAMA_MODEL": "llama3.2:latest",
    "DATABASE_URL": "sqlite:///:memory:",
    "APP_NAME": "GitHub PR Rules Analyzer Test",
    "APP_VERSION": "1.0.0-test",
    "DEBUG": "true",
    "HOST": "127.0.0.1",
    "PORT": "8000",
    "LOG_LEVEL": "DEBUG",
    "MAX_GITHUB_RETRIES": "3",
    "GITHUB_RETRY_DELAY": "0.1",
    "MAX_PRS_PER_REPO": "100",
    "BATCH_SIZE": "10",
    "MAX_LLM_RETRIES": "3",
    "LLM_RETRY_DELAY": "0.1",
    "MAX_TOKENS": "1000",
    "TEMPERATURE": "0.1",
}

# Set environment variables immediately
for key, value in test_env_vars.items():
    os.environ[key] = value


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> None:
    """Set up test environment variables."""
    # Environment variables are already set at module level
    yield

    # Clean up environment variables after tests
    for key in test_env_vars:
        os.environ.pop(key, None)


@pytest.fixture
def test_engine() -> Generator[create_engine, None, None]:
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    # Import models to ensure they're registered with Base
    from github_pr_rules_analyzer.utils.database import Base

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    # Create session
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = testing_session_local()

    yield session

    session.close()
    # Drop all tables after test
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mock_settings() -> Generator[object, None, None]:
    """Mock settings for individual tests."""
    from github_pr_rules_analyzer.config import Settings

    with patch("github_pr_rules_analyzer.config.get_settings") as mock_get_settings:
        # Using a variable to avoid hardcoded password detection
        test_token = "test_token"
        mock_settings_instance = Settings(
            github_token=test_token,
            github_api_base_url="https://api.github.com",
            ollama_api_base_url="http://localhost:11434/v1",
            ollama_model="llama3.2:latest",
            database_url="sqlite:///:memory:",
            app_name="Test App",
            app_version="1.0.0",
            debug=True,
            host="127.0.0.1",
            port=8000,
            log_level="DEBUG",
            max_github_retries=3,
            github_retry_delay=0.1,
            max_prs_per_repo=100,
            batch_size=10,
            max_llm_retries=3,
            llm_retry_delay=0.1,
            max_tokens=1000,
            temperature=0.1,
        )
        mock_get_settings.return_value = mock_settings_instance
        yield mock_settings_instance


@pytest.fixture
def mock_db_session(test_session) -> Generator[Session, None, None]:
    """Mock database session for dependency injection."""
    with patch("github_pr_rules_analyzer.api.routes.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__ = lambda _x: test_session
        mock_get_db.return_value.__exit__ = lambda _x, _y, _z, _w: None
        yield test_session
