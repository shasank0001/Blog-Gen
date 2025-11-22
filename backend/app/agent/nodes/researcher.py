from app.agent.state import AgentState
from app.services.firecrawl_service import firecrawl_service
from app.services.pinecone_service import pinecone_service
from app.services.embedding_service import embedding_service

async def researcher_node(state: AgentState):
    topic = state["topic"]
    bins = state.get("selected_bins", [])
    
    research_data = []
    
    # 1. External Search (Firecrawl)
    try:
        web_results = firecrawl_service.search(topic, limit=3)
        if web_results and 'data' in web_results:
             for item in web_results['data']:
                 research_data.append({
                     "source": "web",
                     "title": item.get('title'),
                     "url": item.get('url'),
                     "content": item.get('markdown', '')[:2000]
                 })
    except Exception as e:
        print(f"Web search failed: {e}")

    # 2. Internal Search (Pinecone)
    try:
        query_vector = embedding_service.embed_query(topic)
        
        for bin_id in bins:
            try:
                results = pinecone_service.query_vectors(query_vector, namespace=bin_id, top_k=3)
                if results and 'matches' in results:
                    for match in results['matches']:
                        research_data.append({
                            "source": "internal",
                            "title": match['metadata'].get('source', 'Unknown'),
                            "content": match['metadata'].get('text', ''),
                            "score": match['score']
                        })
            except Exception as e:
                print(f"Internal search failed for bin {bin_id}: {e}")
    except Exception as e:
        print(f"Embedding failed: {e}")
            
    return {"research_data": research_data}
