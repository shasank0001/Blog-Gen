import asyncio
import gzip
import io
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from app.agent.state import AgentState
from typing import Dict, Any
from app.core.database import AsyncSessionLocal
from app.core.models import InternalIndex
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone
from app.services.safe_fetch import fetch_public_bytes, MAX_RESPONSE_BYTES

async def fetch_url_content(url: str) -> bytes | None:
    try:
        content = await fetch_public_bytes(url)
        if content and content.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                content = compressed.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("Decompressed sitemap exceeds the size limit")
        return content
    except Exception as exc:
        print(f"Skipping sitemap URL {url}: {exc}")
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
    if "://" not in target_domain:
        target_domain = f"https://{target_domain}"
    
    domain_key = urlsplit(target_domain).netloc.lower()

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
    
    # Bound total work even for sitemap indexes that never contain page URLs.
    try:
        async with asyncio.timeout(60):
            sitemap_urls = []
            robots = await fetch_url_content(f"{target_domain}/robots.txt")
            if robots:
                for line in robots.decode("utf-8", errors="replace").splitlines():
                    if line.lower().startswith("sitemap:"):
                        sitemap_urls.append(line.split(":", 1)[1].strip())
            sitemap_urls.extend([
                f"{target_domain}/sitemap.xml",
                f"{target_domain}/sitemap_index.xml",
                f"{target_domain}/wp-sitemap.xml",
            ])
            sitemap_queue = list(dict.fromkeys(sitemap_urls))[:50]
            processed_sitemaps = set()
            while sitemap_queue and len(processed_sitemaps) < 50 and len(internal_links) < 5000:
                current_sitemap = sitemap_queue.pop(0)
                if current_sitemap in processed_sitemaps:
                    continue
                processed_sitemaps.add(current_sitemap)
                content = await fetch_url_content(current_sitemap)
                if not content:
                    continue
                urls, is_index = parse_sitemap_content(content)
                if is_index:
                    for child in urls:
                        if child not in processed_sitemaps and child not in sitemap_queue:
                            sitemap_queue.append(child)
                        if len(sitemap_queue) >= 50:
                            break
                else:
                    for url in urls:
                        if url not in visited_urls and len(internal_links) < 5000:
                            visited_urls.add(url)
                            slug = url.rstrip("/").split("/")[-1]
                            title = slug.replace("-", " ").replace("_", " ").title() or "Home"
                            internal_links.append({"url": url, "title": title})
    except TimeoutError:
        print("Sitemap crawl reached its time limit")

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
