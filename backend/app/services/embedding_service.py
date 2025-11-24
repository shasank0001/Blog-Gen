from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from app.core.config import settings

class EmbeddingService:
    def __init__(self):
        if settings.USE_LOCAL_EMBEDDINGS:
            print(f"Using Local Embeddings: {settings.LOCAL_EMBEDDING_MODEL}")
            self.embeddings = OllamaEmbeddings(
                model=settings.LOCAL_EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL
            )
        else:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.OPENAI_API_KEY
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)

embedding_service = EmbeddingService()
