from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
from app.services.metering import current_meter, UsageMeter, model_price

class LLMService:
    def get_llm(self, model_provider: str = "anthropic", model_name: str = "claude-haiku-4-5", temperature: float = 0.7, use_local: bool = False):
        local = use_local or settings.USE_LOCAL_LLM
        provider = "ollama" if local else model_provider
        name = settings.OLLAMA_MODEL if local else model_name
        meter = current_meter.get()
        # Standalone style analysis remains outside the generation ledger.
        price = model_price(provider, name) if meter else (0, 0, 4096)
        options = {"callbacks": [UsageMeter(meter, provider, name, price)]} if meter else {}
        if local:
            from langchain_ollama import ChatOllama
            return ChatOllama(model=name, base_url=settings.OLLAMA_BASE_URL,
                              temperature=temperature, num_predict=price[2], **options)
        if model_provider == "anthropic":
            return ChatAnthropic(model=model_name, temperature=temperature,
                api_key=settings.ANTHROPIC_API_KEY, max_tokens=price[2], max_retries=0, **options)
        if model_provider == "google":
            return ChatGoogleGenerativeAI(model=model_name, temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY, max_output_tokens=price[2], max_retries=0, **options)
        return ChatOpenAI(model=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY,
                           max_tokens=price[2], max_retries=0, stream_usage=True, **options)


llm_service = LLMService()
