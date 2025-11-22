from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
import json

async def planner_node(state: AgentState):
    topic = state["topic"]
    research_data = state.get("research_data", [])
    style = state.get("style_profile", {})
    
    context = ""
    for item in research_data:
        context += f"Source ({item['source']}): {item.get('title', 'Untitled')}\n{item.get('content', '')[:500]}\n\n"
        
    prompt = ChatPromptTemplate.from_template(
        """
        You are a Content Strategist. Create a detailed blog post outline for the topic: "{topic}".
        
        Style Profile: {style}
        
        Available Research:
        {context}
        
        Return a JSON object with a key "sections" which is a list of objects.
        Each object must have:
        - "id": "section_1", "section_2", etc.
        - "title": Section header
        - "intent": What this section should achieve
        - "source_ids": List of source titles/urls from research to cite (optional)
        """
    )
    
    llm = llm_service.get_llm(model_name="gpt-4o")
    chain = prompt | llm
    response = await chain.ainvoke({"topic": topic, "style": str(style), "context": context})
    
    try:
        # Clean up markdown code blocks if present
        content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        outline = data.get("sections", [])
    except:
        outline = [
            {"id": "sec_1", "title": "Introduction", "intent": "Introduce topic", "source_ids": []},
            {"id": "sec_2", "title": "Main Point", "intent": "Discuss main point", "source_ids": []},
            {"id": "sec_3", "title": "Conclusion", "intent": "Summarize", "source_ids": []}
        ]
        
    return {"outline": outline}
