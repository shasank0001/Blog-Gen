from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command
from pydantic import BaseModel, Field
from app.utils.llm_logger import llm_logger
import json

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
    
    # Get word count targets
    section_word_budgets = state.get("section_word_budgets", {})
    target_words = section_word_budgets.get(section_id, 500)
    min_words = int(target_words * 0.9)
    max_words = int(target_words * 1.1)
    actual_words = len(draft.split())
    
    # Note: The writer node now handles the "rewrite -> visuals" transition directly.
    # So if we are here, it is the first pass.
    
    prompt = ChatPromptTemplate.from_template(
        """
        Review the following draft section and suggest improvements.
        
        Section Title: {title}
        Intent: {intent}
        
        Target Word Count: {target_words} words (acceptable range: {min_words}-{max_words} words)
        Actual Word Count: {actual_words} words
        Word Count Status: {word_count_status}
        
        Draft:
        {draft}
        
        Check for:
        1. Word count compliance - Is it within the {min_words}-{max_words} range?
        2. Adherence to intent - Does it fulfill the stated purpose?
        3. No "AI fluff" (e.g. "In the ever-evolving landscape", "delve", "tapestry", "revolutionize", "game-changer")
        4. Proper citation usage (looking for [source_id])
        5. Flow and clarity
        6. Conciseness - Can any verbose passages be tightened?

        IMPORTANT: 
        - If the draft EXCEEDS {max_words} words, you MUST request cutting content to fit the limit
        - If the draft is below {min_words} words, suggest adding more detail
        - The word count limit is NON-NEGOTIABLE - it's part of the overall blog size constraint
        - Suggest specific sentences or paragraphs to cut if over the limit
        
        Provide constructive feedback on how to improve this section while respecting the word count constraint.
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "anthropic"),
        model_name=state.get("model_name", "claude-haiku-4-5"),
        use_local=state.get("use_local", False)
    )
    structured_llm = llm.with_structured_output(CritiqueResult)
    chain = prompt | structured_llm
    
    # Determine word count status
    if actual_words > max_words:
        word_count_status = f"❌ OVER LIMIT by {actual_words - max_words} words - MUST CUT"
    elif actual_words < min_words:
        word_count_status = f"⚠️ UNDER TARGET by {min_words - actual_words} words - needs expansion"
    else:
        word_count_status = f"✅ WITHIN RANGE ({actual_words}/{target_words} words)"
    
    prompt_vars = {
        "title": section["title"],
        "draft": draft,
        "intent": section["intent"],
        "target_words": target_words,
        "min_words": min_words,
        "max_words": max_words,
        "actual_words": actual_words,
        "word_count_status": word_count_status
    }
    result = await chain.ainvoke(prompt_vars)
    
    # Log the critic call
    thread_id = state.get("user_id", "unknown")
    draft_words = len(draft.split())
    section_word_budgets = state.get("section_word_budgets", {})
    target_words = section_word_budgets.get(section_id, 0)
    
    try:
        formatted_critic_prompt = prompt.format(**prompt_vars)
    except:
        formatted_critic_prompt = str(prompt.messages[0].prompt.template) if hasattr(prompt, 'messages') else str(prompt)
    
    llm_logger.log_call(
        thread_id=thread_id,
        node_name=f"critic_section_{idx+1}",
        prompt=formatted_critic_prompt,
        response=json.dumps(result.model_dump(), indent=2),
        metadata={
            "section_id": section_id,
            "section_title": section["title"],
            "section_index": idx,
            "draft_word_count": draft_words,
            "target_words": target_words,
            "word_diff": draft_words - target_words,
            "feedback_length": len(result.feedback)
        },
        model_info={
            "provider": state.get("model_provider", "anthropic"),
            "name": state.get("model_name", "claude-haiku-4-5")
        }
    )
    
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
