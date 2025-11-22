from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Content Strategist Agent"
    OPENAI_API_KEY: str
    FIRECRAWL_API_KEY: str
    PINECONE_API_KEY: str
    PINECONE_ENV: str = "us-east-1"
    DATABASE_URL: str
    USE_LOCAL_LLM: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
