from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command
from pydantic import BaseModel, Field

class CritiqueResult(BaseModel):
    feedback: str = Field(description="Suggestions for improvement. If the draft is perfect, provide minor polish suggestions.")

async def critic_node(state: AgentState):
    idx = state.get("current_section_index", 0)
    outline = state["outline"]
    
    # Safety check
    if idx >= len(outline):
        return Command(goto="publisher")

    section = outline[idx]
    section_id = section["id"]
    draft = state["draft_sections"].get(section_id, "")
    
    # Note: The writer node now handles the "rewrite -> visuals" transition directly.
    # So if we are here, it is the first pass.
    
    prompt = ChatPromptTemplate.from_template(
        """
        Review the following draft section and suggest improvements.
        
        Draft:
        {draft}
        
        Intent: {intent}
        
        Check for:
        1. Adherence to intent.
        2. No "AI fluff" (e.g. "In the ever-evolving landscape", "delve", "tapestry").
        3. Proper citation usage (looking for [source_id]).
        4. Flow and clarity.

        Provide constructive feedback on how to improve this section.
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "openai"),
        model_name=state.get("model_name", "gpt-5.1"),
        use_local=state.get("use_local", False)
    )
    structured_llm = llm.with_structured_output(CritiqueResult)
    chain = prompt | structured_llm
    
    result = await chain.ainvoke({
        "draft": draft,
        "intent": section["intent"]
    })
    
    # Always send back to writer for one round of improvements
    feedback_dict = state.get("critique_feedback", {}).copy()
    feedback_dict[section_id] = result.feedback
    
    retries_dict = state.get("section_retries", {}).copy()
    retries_dict[section_id] = state.get("section_retries", {}).get(section_id, 0) + 1
    
    return Command(
        update={
            "critique_feedback": feedback_dict,
            "section_retries": retries_dict
        },
        goto="writer"
    )
