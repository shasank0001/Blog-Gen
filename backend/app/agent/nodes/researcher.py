import asyncio
from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from app.agent.state import AgentState
from app.services.firecrawl_service import firecrawl_service
from app.services.pinecone_service import pinecone_service
from app.services.embedding_service import embedding_service
from app.services.arxiv_service import arxiv_service
from app.services.llm_service import llm_service

class SearchQueries(BaseModel):
    queries: List[str] = Field(description="List of 3-5 optimized search queries")

async def researcher_node(state: AgentState):
    topic = state["topic"]
    bins = state.get("selected_bins", [])
    sources = state.get("research_sources", ["web", "internal"]) # Default
    guidelines = state.get("research_guidelines", [])
    audience = state.get("target_audience", "")
    extra_context = state.get("extra_context", "")
    use_local = state.get("use_local", False)

    # --- Step 1: Generate Optimized Queries ---
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "anthropic"),
        model_name=state.get("model_name", "claude-haiku-4-5"),
        use_local=use_local
    )
    
    query_prompt = ChatPromptTemplate.from_template(
        """
        You are a Research Strategist. Your goal is to generate targeted search queries to gather information for a blog post.
        
        Topic: {topic}
        Target Audience: {audience}
        Research Guidelines:
        {guidelines}
        
        Generate 3-5 specific, high-quality search queries that will help uncover relevant facts, statistics, and insights.
        If the audience is technical, use technical terms. If the guidelines ask for specific data, include that in the queries.
        """
    )
    
    structured_llm = llm.with_structured_output(SearchQueries)
    chain = query_prompt | structured_llm
    
    try:
        guidelines_str = "\\n".join(f"- {g}" for g in guidelines) if guidelines else "None"
        result = await chain.ainvoke({
            "topic": topic, 
            "audience": audience or "General Audience", 
            "guidelines": guidelines_str
        })
        search_queries = result.queries
        print(f"Generated Queries: {search_queries}")
    except Exception as e:
        print(f"Query generation failed: {e}. Falling back to topic.")
        search_queries = [topic]

    # --- Step 2: Execute Search Tasks ---
    
    async def search_web():
        if "web" not in sources:
            return []
        results = []
        
        # Use the first 2 generated queries for web search to avoid rate limits/overload
        queries_to_run = search_queries[:2]
        
        for q in queries_to_run:
            # Strip quotes from query as they break Firecrawl search
            clean_q = q.strip('"').strip("'")
            try:
                print(f"Executing Web Search for: {clean_q}")
                # Run blocking IO in thread
                web_results = await asyncio.to_thread(firecrawl_service.search, clean_q, limit=3)
                print(f"Raw Firecrawl Result for {clean_q}: {str(web_results)[:200]}...")
                
                # Handle Firecrawl v2 response
                if hasattr(web_results, 'model_dump'):
                    web_results = web_results.model_dump()
                
                # Extract data from 'web' or 'data' key
                data = web_results.get('web') or web_results.get('data') or []
                
                if not data:
                    print(f"No data found for query: {q}")
                
                for i, item in enumerate(data):
                     # Extract title/url from metadata if not at top level
                     metadata = item.get('metadata', {})
                     title = item.get('title') or metadata.get('title') or 'No Title'
                     url = item.get('url') or metadata.get('url') or 'No URL'
                     # Fallback to description or snippet if markdown is not available
                     content = item.get('markdown') or item.get('description') or item.get('snippet') or ''
                     content = content[:2000]

                     results.append({
                         "source_id": f"web_{len(results)+1}",
                         "source": "web",
                         "title": title,
                         "url": url,
                         "content": content
                     })
            except Exception as e:
                print(f"Web search failed for query '{q}': {e}")
                import traceback
                traceback.print_exc()
                
        return results

    async def search_social():
        if "social" not in sources:
            return []
        results = []
        try:
            # Search Reddit/Twitter via Firecrawl using the first query
            clean_q = search_queries[0].strip('"').strip("'")
            query = f"{clean_q} site:reddit.com OR site:x.com OR site:twitter.com"
            social_results = await asyncio.to_thread(firecrawl_service.search, query, limit=3)
            
            # Handle Firecrawl v2 response
            if hasattr(social_results, 'model_dump'):
                social_results = social_results.model_dump()
            
            # Extract data from 'web' or 'data' key
            data = social_results.get('web') or social_results.get('data') or []

            for i, item in enumerate(data):
                 # Extract title/url from metadata if not at top level
                 metadata = item.get('metadata', {})
                 title = item.get('title') or metadata.get('title') or 'No Title'
                 url = item.get('url') or metadata.get('url') or 'No URL'
                 # Fallback to description or snippet if markdown is not available
                 content = item.get('markdown') or item.get('description') or item.get('snippet') or ''
                 content = content[:1500]

                 results.append({
                     "source_id": f"social_{i+1}",
                     "source": "social",
                     "title": title,
                     "url": url,
                     "content": content
                 })
        except Exception as e:
            print(f"Social search failed: {e}")
        return results

    async def search_academic():
        if "academic" not in sources:
            return []
        results = []
        try:
            # Use the most technical query if possible, or just the first one
            q = search_queries[0]
            arxiv_results = await arxiv_service.search(q, limit=3)
            for i, item in enumerate(arxiv_results):
                results.append({
                    "source_id": f"acad_{i+1}",
                    "source": "academic",
                    "title": item.get('title'),
                    "url": item.get('url'),
                    "content": f"Summary: {item.get('summary')}\\nAuthors: {', '.join(item.get('authors', []))}"
                })
        except Exception as e:
            print(f"Academic search failed: {e}")
        return results

    async def search_internal():
        if "internal" not in sources or not bins:
            return []
        results = []
        try:
            # Embed the first 2 queries
            queries_to_run = search_queries[:2]
            
            for q in queries_to_run:
                # Use embed_query instead of embed_text, and run in thread
                query_embedding = await asyncio.to_thread(embedding_service.embed_query, q)
                
                # Search in each bin
                for bin_id in bins:
                    # Construct namespace: {user_id}_{bin_id}
                    # We need user_id from state.
                    user_id = state.get("user_id")
                    if not user_id:
                        print("User ID missing for internal search")
                        continue
                        
                    namespace = f"{user_id}_{bin_id}"
                    print(f"Internal Search: Querying namespace {namespace}")
                    
                    try:
                        query_response = await asyncio.to_thread(
                            pinecone_service.query_vectors,
                            vector=query_embedding,
                            namespace=namespace,
                            top_k=3
                        )
                        
                        # Handle Pinecone response (dict or object)
                        if hasattr(query_response, 'matches'):
                            matches = query_response.matches
                        elif isinstance(query_response, dict):
                            matches = query_response.get('matches', [])
                        else:
                            matches = []
                            
                        print(f"Internal Search: Found {len(matches)} matches in bin {bin_id}")
                    except Exception as e:
                        print(f"Pinecone query failed for bin {bin_id}: {e}")
                        matches = []
                    
                    for i, match in enumerate(matches):
                        # Handle match object/dict
                        if isinstance(match, dict):
                            metadata = match.get('metadata', {})
                        else:
                            metadata = getattr(match, 'metadata', {})
                            if hasattr(metadata, 'to_dict'):
                                metadata = metadata.to_dict()
                            
                        results.append({
                            "source_id": f"int_{bin_id[:4]}_{len(results)+1}",
                            "source": "internal",
                            "title": metadata.get('source', 'Internal Doc'),
                            "url": "Internal Knowledge Base",
                            "content": metadata.get('text', '')
                        })
        except Exception as e:
            print(f"Internal search failed: {e}")
        return results

    # Run all search tasks
    results_web, results_social, results_acad, results_internal = await asyncio.gather(
        search_web(),
        search_social(),
        search_academic(),
        search_internal()
    )
    
    # --- Step 3: Aggregate & Prioritize ---
    
    final_results = []
    
    # 1. User Provided Context (Highest Priority)
    if extra_context:
        final_results.append({
            "source_id": "user_context",
            "source": "user",
            "title": "User Provided Context",
            "url": "User Input",
            "content": extra_context
        })
        
    # 2. Internal Knowledge (High Priority)
    final_results.extend(results_internal)
    
    # 3. External Sources
    final_results.extend(results_web)
    final_results.extend(results_acad)
    final_results.extend(results_social)
    
    return {"research_data": final_results}
