import httpx
import gzip
from bs4 import BeautifulSoup
from app.agent.state import AgentState
from typing import Dict, Any, List, Set
from app.core.database import AsyncSessionLocal
from app.core.models import InternalIndex
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone

async def fetch_url_content(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code != 200:
            return None
        
        content = response.content
        if url.endswith(".gz"):
            try:
                content = gzip.decompress(content)
            except Exception:
                pass
        return content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_sitemap_content(content: bytes):
    urls = []
    try:
        soup = BeautifulSoup(content, "xml")
    except Exception:
        soup = BeautifulSoup(content, "html.parser")
    
    # Check for sitemap index
    sitemaps = soup.find_all("sitemap")
    if sitemaps:
        for sm in sitemaps:
            loc = sm.find("loc")
            if loc and loc.text:
                urls.append(loc.text.strip())
        return urls, True # True indicates it's an index
    
    # Check for urlset
    url_tags = soup.find_all("url")
    for url in url_tags:
        loc = url.find("loc")
        if loc and loc.text:
            urls.append(loc.text.strip())
    return urls, False # False indicates it's a urlset

async def internal_indexer_node(state: AgentState) -> Dict[str, Any]:
    target_domain = state.get("target_domain")
    if not target_domain:
        return {"internal_links": []}

    # Ensure domain has protocol
    if not target_domain.startswith("http"):
        target_domain = f"https://{target_domain}"
    
    domain_key = target_domain.replace("https://", "").replace("http://", "").split("/")[0]

    # Check Cache
    async with AsyncSessionLocal() as db:
        # Check if we have recent data (last 24h)
        stmt = select(InternalIndex).where(InternalIndex.domain == domain_key)
        result = await db.execute(stmt)
        cached_links = result.scalars().all()
        
        if cached_links:
            # Check freshness of the first link (assuming all scraped at same time)
            # Use naive UTC for comparison as DB is naive
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if cached_links[0].last_scraped > now_naive - timedelta(hours=24):
                print(f"Using cached sitemap for {domain_key}")
                return {"internal_links": [{"url": l.url, "title": l.title} for l in cached_links]}
            else:
                # Stale, delete old
                await db.execute(delete(InternalIndex).where(InternalIndex.domain == domain_key))
                await db.commit()

    internal_links = []
    visited_urls = set()
    
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ContentStrategistBot/1.0)"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        
        # 1. Find Sitemap URL
        sitemap_urls = []
        
        # Check robots.txt
        try:
            robots_resp = await client.get(f"{target_domain}/robots.txt", timeout=5.0)
            if robots_resp.status_code == 200:
                for line in robots_resp.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_urls.append(line.split(":", 1)[1].strip())
        except Exception:
            pass
            
        # Add defaults
        sitemap_urls.extend([
            f"{target_domain}/sitemap.xml",
            f"{target_domain}/sitemap_index.xml",
            f"{target_domain}/wp-sitemap.xml"
        ])
        
        # Deduplicate sitemap URLs
        sitemap_queue = list(dict.fromkeys(sitemap_urls))
        processed_sitemaps = set()
        
        while sitemap_queue:
            current_sitemap = sitemap_queue.pop(0)
            if current_sitemap in processed_sitemaps:
                continue
            processed_sitemaps.add(current_sitemap)
            
            print(f"Fetching sitemap: {current_sitemap}")
            content = await fetch_url_content(client, current_sitemap)
            if not content:
                continue
                
            urls, is_index = parse_sitemap_content(content)
            
            if is_index:
                # Add children to queue
                for child_url in urls:
                    if child_url not in processed_sitemaps:
                        sitemap_queue.append(child_url)
            else:
                # Extract links
                for url in urls:
                    if url not in visited_urls:
                        visited_urls.add(url)
                        # Simple title extraction from URL slug
                        slug = url.rstrip("/").split("/")[-1]
                        title = slug.replace("-", " ").replace("_", " ").title()
                        if not title:
                            title = "Home"
                        internal_links.append({"url": url, "title": title})
                        
            # Limit to avoid infinite loops or huge sites
            if len(internal_links) > 5000:
                break

    # Save to Cache
    if internal_links:
        async with AsyncSessionLocal() as db:
            for link in internal_links:
                db_link = InternalIndex(
                    domain=domain_key,
                    url=link["url"],
                    title=link["title"]
                )
                db.add(db_link)
            await db.commit()

    return {"internal_links": internal_links}
