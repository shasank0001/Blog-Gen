from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate

async def writer_node(state: AgentState):
    outline = state["outline"]
    idx = state.get("current_section_index", 0)
    
    if idx >= len(outline):
        return {"current_section_index": idx}
        
    section = outline[idx]
    style = state.get("style_profile", {})
    research = state.get("research_data", [])
    
    prompt = ChatPromptTemplate.from_template(
        """
        Write the following section for a blog post.
        
        Section Title: {title}
        Intent: {intent}
        
        Style Guide: {style}
        
        Research Context:
        {context}
        
        Write only the content for this section. Use Markdown.
        """
    )
    
    context_str = str(research)[:2000] 
    
    llm = llm_service.get_llm()
    chain = prompt | llm
    response = await chain.ainvoke({
        "title": section["title"],
        "intent": section["intent"],
        "style": str(style),
        "context": context_str
    })
    
    draft_sections = state.get("draft_sections", {}).copy()
    draft_sections[section["id"]] = response.content
    
    return {
        "draft_sections": draft_sections
    }
