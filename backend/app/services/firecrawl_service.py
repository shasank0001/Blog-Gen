from firecrawl import FirecrawlApp
from app.core.config import settings

class FirecrawlService:
    def __init__(self):
        self.app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)

    def search(self, query: str, limit: int = 5):
        params = {
            "limit": limit,
            "scrapeOptions": {"formats": ["markdown"]},
        }
        # Note: The SDK might have slightly different method signatures depending on version.
        # Using the generic search method based on v2 API description.
        return self.app.search(query, params=params)

    def scrape(self, url: str):
        params = {"formats": ["markdown"]}
        return self.app.scrape_url(url, params=params)

firecrawl_service = FirecrawlService()
