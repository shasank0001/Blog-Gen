from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command

async def critic_node(state: AgentState):
    idx = state.get("current_section_index", 0)
    outline = state["outline"]
    
    # Safety check
    if idx >= len(outline):
        return Command(goto="publisher")

    section = outline[idx]
    draft = state["draft_sections"].get(section["id"], "")
    
    prompt = ChatPromptTemplate.from_template(
        """
        Critique the following draft section.
        
        Draft:
        {draft}
        
        Check for:
        1. Adherence to intent: {intent}
        2. No "AI fluff" (e.g. "In the ever-evolving landscape")
        3. Passive voice usage.
        
        Return "PASS" if it's good.
        Return "FAIL: <reason>" if it needs changes.
        """
    )
    
    llm = llm_service.get_llm()
    chain = prompt | llm
    response = await chain.ainvoke({
        "draft": draft,
        "intent": section["intent"]
    })
    
    result = response.content.strip()
    
    # Logic: If PASS, increment index and go to writer (for next section) or publisher (if done)
    # If FAIL, we should ideally loop back to writer with feedback. 
    # For MVP, we are just moving forward to avoid infinite loops, but logging feedback could be added.
    
    next_idx = idx + 1
    if next_idx < len(outline):
        return Command(
            update={"current_section_index": next_idx},
            goto="writer"
        )
    else:
        return Command(
            update={"current_section_index": next_idx},
            goto="publisher"
        )
