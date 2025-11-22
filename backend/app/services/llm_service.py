from langchain_openai import ChatOpenAI
from app.core.config import settings

class LLMService:
    def get_llm(self, model_name: str = "gpt-4o", temperature: float = 0.7):
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY
        )

llm_service = LLMService()
