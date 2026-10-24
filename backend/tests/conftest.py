"""Hermetic test settings; no developer credentials or live services are used."""
import os
import pytest

os.environ.update(
    OPENAI_API_KEY="review-dummy",
    FIRECRAWL_API_KEY="review-dummy",
    PINECONE_API_KEY="review-dummy",
    DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
    SECRET_KEY="test-only-secret-0123456789-abcdefghijklmnopqrstuvwxyz",
)


@pytest.fixture(autouse=True)
def isolated_dependencies():
    from app.main import app
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
