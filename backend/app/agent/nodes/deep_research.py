import os
from typing import List, Dict, Any
import asyncio
from app.services.llm_service import llm_service
from app.services.firecrawl_service import firecrawl_service
from app.services.arxiv_service import arxiv_service
from app.agent.state import AgentState, ResearchResult, Citation
from app.core.config import settings
from pydantic import BaseModel
from app.services.embedding_service import embedding_service
from app.services.pinecone_service import pinecone_service

# --- Node 1: Generate Queries ---
async def generate_query_node(state: AgentState):
    topic = state["topic"]
    loop_count = state.get("research_loop_count", 0)
    use_local = state.get("use_local", False)
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "openai"),
        model_name=state.get("model_name", "gpt-5.1"),
        use_local=use_local
    )
    
    prompt = f"""
    You are a research planner. 
    Topic: {topic}
    Current Loop: {loop_count}
    
    Break the topic into 3 specific, search-optimized queries to gather comprehensive information.
    If this is a follow-up loop, focus on missing details.
    """
    
    class QueryList(BaseModel):
        queries: List[str]

    structured_llm = llm.with_structured_output(QueryList)
    result = await structured_llm.ainvoke(prompt)
    
    return {
        "generated_queries": result.queries,
        "research_loop_count": loop_count + 1
    }

# --- Node 2: Web Research (Parallel) ---
async def web_research_node(state: Dict):
    # Note: This node receives a subset of state via Send("web_research", {"query": q})
    
    query = state["query"]
    print(f"Executing Deep Research for: {query}")
    
    # We don't have direct access to 'use_local' here because 'state' is just the payload from Send.
    # However, we can default to Firecrawl which is safer for general use.
    # If we really need 'use_local', we should have passed it in the payload.
    # For now, let's use Firecrawl as the primary engine since 'client.responses' is unstable/unknown.
    
    try:
        # Use Firecrawl for search
        web_results = await asyncio.to_thread(firecrawl_service.search, query, limit=3)
        
        if hasattr(web_results, 'model_dump'):
            web_results = web_results.model_dump()
        
        data = web_results.get('web') or web_results.get('data') or []
        
        citations = []
        summary_parts = []
        
        for item in data:
            metadata = item.get('metadata', {})
            title = item.get('title') or metadata.get('title') or 'No Title'
            url = item.get('url') or metadata.get('url') or 'No URL'
            content = item.get('markdown') or item.get('description') or item.get('snippet') or ''
            
            citations.append(Citation(
                url=url,
                title=title,
                content=content[:500]
            ))
            summary_parts.append(f"Source: {title}\nURL: {url}\nContent: {content[:1000]}")
            
        content_text = "\n\n".join(summary_parts)
        
    except Exception as e:
        print(f"Deep Research Failed for {query}: {e}")
        content_text = f"Search failed for {query}. Error: {str(e)}"
        citations = []

    return {
        "deep_research_results": [
            ResearchResult(
                query=query, 
                summary=content_text, 
                citations=citations
            )
        ]
    }

# --- Node 2B: Social Research (Parallel) ---
async def social_research_node(state: Dict):
    query = state["query"]
    print(f"Executing Deep Social Research for: {query}")
    
    try:
        # Search Reddit/Twitter via Firecrawl using site filter
        clean_q = query.strip('"').strip("'")
        social_query = f"{clean_q} site:reddit.com OR site:x.com OR site:twitter.com"
        social_results = await asyncio.to_thread(firecrawl_service.search, social_query, limit=3)
        
        if hasattr(social_results, 'model_dump'):
            social_results = social_results.model_dump()
        
        data = social_results.get('web') or social_results.get('data') or []
        
        citations = []
        summary_parts = []
        
        for item in data:
            metadata = item.get('metadata', {})
            title = item.get('title') or metadata.get('title') or 'No Title'
            url = item.get('url') or metadata.get('url') or 'No URL'
            content = item.get('markdown') or item.get('description') or item.get('snippet') or ''
            
            citations.append(Citation(
                url=url,
                title=title,
                content=content[:500]
            ))
            summary_parts.append(f"Source: {title}\nURL: {url}\nContent: {content[:1000]}")
            
        content_text = "\n\n".join(summary_parts)
        
    except Exception as e:
        print(f"Deep Social Research Failed for {query}: {e}")
        content_text = f"Social search failed for {query}. Error: {str(e)}"
        citations = []

    return {
        "deep_research_results": [
            ResearchResult(
                query=query, 
                summary=content_text, 
                citations=citations
            )
        ]
    }

# --- Node 2C: Academic Research (Parallel) ---
async def academic_research_node(state: Dict):
    query = state["query"]
    print(f"Executing Deep Academic Research for: {query}")
    
    try:
        # Search Arxiv for academic papers
        arxiv_results = await arxiv_service.search(query, limit=3)
        
        citations = []
        summary_parts = []
        
        for item in arxiv_results:
            title = item.get('title', 'No Title')
            url = item.get('url', 'No URL')
            summary = item.get('summary', '')
            authors = ', '.join(item.get('authors', []))
            published = item.get('published', 'Unknown')
            
            content = f"Summary: {summary}\nAuthors: {authors}\nPublished: {published}"
            
            citations.append(Citation(
                url=url,
                title=title,
                content=content[:500]
            ))
            summary_parts.append(f"Source: {title}\nURL: {url}\n{content[:1000]}")
            
        content_text = "\n\n".join(summary_parts)
        
    except Exception as e:
        print(f"Deep Academic Research Failed for {query}: {e}")
        content_text = f"Academic search failed for {query}. Error: {str(e)}"
        citations = []

    return {
        "deep_research_results": [
            ResearchResult(
                query=query, 
                summary=content_text, 
                citations=citations
            )
        ]
    }

# --- Node 3: Reflection ---
async def reflection_node(state: AgentState):
    topic = state["topic"]
    results = state.get("deep_research_results", [])
    loop_count = state.get("research_loop_count", 0)
    use_local = state.get("use_local", False)
    
    # Summarize current findings
    findings_summary = "\n\n".join([f"Query: {r.query}\nSummary: {r.summary}" for r in results])
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "openai"),
        model_name=state.get("model_name", "gpt-5.1"),
        use_local=use_local
    )
    
    class ReflectionOutput(BaseModel):
        is_sufficient: bool
        feedback: str

    prompt = f"""
    Review the current research findings for the topic: "{topic}"
    
    Findings:
    {findings_summary}
    
    Are these findings sufficient to write a comprehensive blog post?
    If yes, set is_sufficient to True.
    If no, explain what is missing.
    """
    
    structured_llm = llm.with_structured_output(ReflectionOutput)
    result = await structured_llm.ainvoke(prompt)
    
    return {
        "is_sufficient": result.is_sufficient,
        # We don't strictly need to store feedback, but it helps debugging
    }

# --- Node 4: Finalize Answer (Adapter) ---
async def finalize_answer_node(state: AgentState):
    # Convert Deep Research Results into the format expected by the 'planner' node
    # Planner expects 'research_data' as List[Dict]
    
    deep_results = state.get("deep_research_results", [])
    research_data = list(state.get("research_data") or [])
    
    # Categorize results by detecting source type from citations
    web_count = 0
    social_count = 0
    acad_count = 0
    
    for i, res in enumerate(deep_results):
        # Determine source type based on URL patterns in citations
        source_type = "web"  # default
        if res.citations:
            first_url = res.citations[0].url.lower()
            if "reddit.com" in first_url or "x.com" in first_url or "twitter.com" in first_url:
                source_type = "social"
                social_count += 1
            elif "arxiv.org" in first_url:
                source_type = "academic"
                acad_count += 1
            else:
                web_count += 1
        else:
            web_count += 1
        
        # Add individual citations with proper source IDs
        for j, cit in enumerate(res.citations):
            if source_type == "social":
                source_id = f"social_{social_count}_{j+1}"
            elif source_type == "academic":
                source_id = f"acad_{acad_count}_{j+1}"
            else:
                source_id = f"web_{web_count}_{j+1}"
            
            research_data.append({
                "source_id": source_id,
                "source": source_type,
                "url": cit.url,
                "title": cit.title,
                "content": cit.content or cit.title # Fallback if content empty
            })

    internal_results = await _run_internal_search(state)
    # Prioritize internal findings by prepending them
    if internal_results:
        research_data = internal_results + research_data
            
    return {
        "research_data": research_data
    }

async def _run_internal_search(state: AgentState) -> List[Dict[str, Any]]:
    sources = state.get("research_sources", [])
    bins = state.get("selected_bins", [])
    user_id = state.get("user_id")
    loop_count = state.get("research_loop_count", 0)
    
    if "internal" not in sources or not bins or not user_id:
        return []

    queries = state.get("generated_queries") or [state.get("topic", "")]
    queries_to_run = [q for q in queries if q] or [state.get("topic", "")]
    queries_to_run = queries_to_run[:2]

    results: List[Dict[str, Any]] = []

    for q in queries_to_run:
        try:
            query_embedding = await asyncio.to_thread(embedding_service.embed_query, q)
        except Exception as e:
            print(f"Deep internal search embedding failed for query '{q}': {e}")
            continue

        for bin_id in bins:
            namespace = f"{user_id}_{bin_id}"
            try:
                query_response = await asyncio.to_thread(
                    pinecone_service.query_vectors,
                    vector=query_embedding,
                    namespace=namespace,
                    top_k=3
                )
            except Exception as e:
                print(f"Deep internal search Pinecone error for namespace {namespace}: {e}")
                continue

            if hasattr(query_response, "matches"):
                matches = query_response.matches
            elif isinstance(query_response, dict):
                matches = query_response.get("matches", [])
            else:
                matches = []

            for match in matches:
                if isinstance(match, dict):
                    metadata = match.get("metadata", {})
                else:
                    metadata = getattr(match, "metadata", {})
                    if hasattr(metadata, "to_dict"):
                        metadata = metadata.to_dict()

                results.append({
                    "source_id": f"int_{str(bin_id)[:4]}_L{loop_count}_{len(results)+1}",
                    "source": "internal",
                    "title": metadata.get("source", "Internal Doc"),
                    "url": "Internal Knowledge Base",
                    "content": metadata.get("text", "")
                })

    return results
