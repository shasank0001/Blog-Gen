from firecrawl import Firecrawl
from app.core.config import settings

class FirecrawlService:
    def __init__(self):
        self.app = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)

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
