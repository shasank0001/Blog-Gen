from firecrawl import Firecrawl
from app.core.config import settings

class FirecrawlService:
    def __init__(self):
        self._app = None

    @property
    def app(self):
        if self._app is None:
            if not settings.FIRECRAWL_API_KEY:
                raise ValueError("Configure FIRECRAWL_API_KEY to use web research or style URL scraping")
            self._app = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)
        return self._app

    def search(self, query: str, limit: int = 5):
        print(f"FirecrawlService: Searching for '{query}'")
        try:
            return self.app.search(
                query, 
                limit=limit,
                scrape_options={"formats": ["markdown"]}
            )
        except Exception as e:
            print(f"FirecrawlService Error: {e}")
            raise e

    def scrape(self, url: str):
        return self.app.scrape(
            url, 
            formats=["markdown"]
        )

firecrawl_service = FirecrawlService()
