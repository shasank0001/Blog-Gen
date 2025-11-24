from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional

class SectionModel(BaseModel):
    id: str = Field(description="Unique ID like sec_1")
    title: str
    intent: str
    source_ids: List[str] = Field(description="List of Source IDs to cite")
    content: Optional[str] = None

class Outline(BaseModel):
    sections: List[SectionModel]

async def planner_node(state: AgentState):
    topic = state["topic"]
    research_data = state.get("research_data", [])
    style = state.get("style_profile", {})
    use_local = state.get("use_local", False)
    audience = state.get("target_audience", "General Audience")
    guidelines = state.get("research_guidelines", [])
    
    context = ""
    for item in research_data:
        context += f"Source ID: {item.get('source_id')}\nTitle: {item.get('title', 'Untitled')}\nContent: {item.get('content', '')[:500]}\n\n"
        
    guidelines_str = "\n".join(f"- {g}" for g in guidelines) if guidelines else "None"

    prompt = ChatPromptTemplate.from_template(
        """
        You are a Content Strategist. Create a detailed blog post outline for the topic: "{topic}".
        
        Target Audience: {audience}
        
        Specific Guidelines:
        {guidelines}
        
        Style Profile: {style}
        
        Available Research:
        {context}
        
        Create an outline where each section is assigned specific Intent and Source IDs (from the provided Research Context).
        Ensure Source IDs match exactly what is provided in the context (e.g., web_1, int_abc_1).
        
        IMPORTANT: Prioritize using 'internal' sources (IDs starting with 'int_') over web sources where possible.
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "openai"),
        model_name=state.get("model_name", "gpt-5.1"),
        use_local=use_local
    )
    structured_llm = llm.with_structured_output(Outline)
    chain = prompt | structured_llm
    
    try:
        result = await chain.ainvoke({
            "topic": topic, 
            "style": str(style), 
            "context": context,
            "audience": audience,
            "guidelines": guidelines_str
        })
        # Convert Pydantic models to dicts for State
        outline = [section.model_dump() for section in result.sections]
    except Exception as e:
        print(f"Planner failed: {e}")
        outline = [
            {"id": "sec_1", "title": "Introduction", "intent": "Introduce topic", "source_ids": [], "content": None},
            {"id": "sec_2", "title": "Main Point", "intent": "Discuss main point", "source_ids": [], "content": None},
            {"id": "sec_3", "title": "Conclusion", "intent": "Summarize", "source_ids": [], "content": None}
        ]
        
    return {
        "outline": outline,
        "critique_feedback": {},
        "section_retries": {},
        "draft_sections": {}
    }
