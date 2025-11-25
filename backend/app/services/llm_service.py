from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class LLMService:
    def get_llm(self, model_provider: str = "anthropic", model_name: str = "claude-haiku-4-5", temperature: float = 0.7, use_local: bool = False):
        if use_local or settings.USE_LOCAL_LLM:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_MODEL, 
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature
            )
        
        if model_provider == "anthropic":
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                api_key=settings.ANTHROPIC_API_KEY
            )
        elif model_provider == "google":
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY
            )
        else:
            # Default to OpenAI
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                api_key=settings.OPENAI_API_KEY
            )

llm_service = LLMService()
