from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from decimal import Decimal

class Settings(BaseSettings):
    PROJECT_NAME: str = "Content Strategist Agent"
    OPENAI_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    PINECONE_API_KEY: str = ""
    PINECONE_ENV: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "content-strategist"
    DATABASE_URL: str
    USE_LOCAL_LLM: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5"
    USE_LOCAL_EMBEDDINGS: bool = False
    LOCAL_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Model Providers
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Operator-supplied USD prices per million tokens. No stale price defaults.
    LLM_PRICING_JSON: str = "{}"
    DEFAULT_MONTHLY_LIMIT_USD: Decimal = Field(default=Decimal("10"), ge=0, le=100000)
    WORKER_CONCURRENCY: int = Field(default=2, ge=1, le=8)

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOW_REGISTRATION: bool = True

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v):
        if v.strip() in {"your-secret-key-change-in-production", "replace-with-strong-secret"} or len(v.strip()) < 32:
            raise ValueError("SECRET_KEY must be a unique random secret of at least 32 characters")
        return v

    class Config:
        env_file = ".env"

settings = Settings()
