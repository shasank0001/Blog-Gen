import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class ArxivService:
    BASE_URL = "https://export.arxiv.org/api/query"

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search Arxiv for papers related to the query.
        """
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.BASE_URL, params=params, timeout=10.0)
                response.raise_for_status()
                return self._parse_response(response.text)
            except Exception as e:
                print(f"Arxiv search failed: {e}")
                return []

    def _parse_response(self, xml_content: str) -> List[Dict[str, Any]]:
        results = []
        try:
            root = ET.fromstring(xml_content)
            # Arxiv API returns Atom 1.0 format
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
                link = entry.find('atom:id', ns).text.strip()
                published = entry.find('atom:published', ns).text.strip()
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns).text
                    authors.append(name)
                
                results.append({
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published": published,
                    "authors": authors
                })
        except Exception as e:
            print(f"Error parsing Arxiv XML: {e}")
            
        return results

arxiv_service = ArxivService()
