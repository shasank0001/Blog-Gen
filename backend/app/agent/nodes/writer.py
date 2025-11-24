from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import Command

async def writer_node(state: AgentState):
    outline = state["outline"]
    idx = state.get("current_section_index", 0)
    
    if idx >= len(outline):
        return Command(goto="publisher")
        
    section = outline[idx]
    style = state.get("style_profile", {})
    research = state.get("research_data", [])
    internal_links = state.get("internal_links", [])
    audience = state.get("target_audience", "General Audience")
    
    # Filter research data based on section source_ids
    relevant_research = [
        r for r in research 
        if r.get("source_id") in section.get("source_ids", [])
    ]
    
    # If no specific sources assigned, use top 3 from general research as fallback
    if not relevant_research:
        relevant_research = research[:3]

    # Check for critique feedback
    critique_feedback = state.get("critique_feedback", {}).get(section["id"])
    retry_count = state.get("section_retries", {}).get(section["id"], 0)
    
    feedback_instruction = ""
    if critique_feedback:
        feedback_instruction = f"\nIMPORTANT: This is a revision to improve the content.\nIncorporate the following feedback:\n{critique_feedback}\n"

    # Get previous section content for better flow
    previous_section_content = ""
    if idx > 0:
        prev_section_id = outline[idx - 1]["id"]
        previous_section_content = state.get("draft_sections", {}).get(prev_section_id, "")
        # Take the last 500 characters to provide context for transition
        if previous_section_content:
            previous_section_content = "..." + previous_section_content[-500:]

    context_str = "\n\n".join([
        f"Source ID: {r.get('source_id')}\nTitle: {r.get('title')}\nContent: {r.get('content', '')[:500]}"
        for r in relevant_research
    ])
    
    links_str = "\n".join([f"- {l['title']}: {l['url']}" for l in internal_links])
    
    prompt = ChatPromptTemplate.from_template(
        """
        Write the following section for a blog post.
        
        Section Title: {title}
        Intent: {intent}
        Target Audience: {audience}
        
        Style Guide: {style}

        Previous Section (For smooth transition):
        {previous_content}
        
        Internal Links (Insert these naturally if relevant, using [Title](url)):
        {links}
        
        {feedback_instruction}
        
        Research Context (You MUST cite these using [source_id] at the end of sentences where appropriate):
        {context}
        
        IMPORTANT: When writing, give more weight to information from internal sources (IDs starting with 'int_').
        
        Write only the content for this section. Use Markdown. Do not include the Section Title in the output.
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "openai"),
        model_name=state.get("model_name", "gpt-5.1"),
        use_local=state.get("use_local", False)
    )
    chain = prompt | llm
    response = await chain.ainvoke({
        "title": section["title"],
        "intent": section["intent"],
        "style": str(style),
        "previous_content": previous_section_content,
        "links": links_str,
        "context": context_str,
        "audience": audience,
        "feedback_instruction": feedback_instruction
    })
    
    draft_sections = state.get("draft_sections", {}).copy()
    draft_sections[section["id"]] = response.content
    
    # If this was a rewrite (we have retried at least once), skip the critic and go to visuals
    if retry_count > 0:
        return Command(
            update={"draft_sections": draft_sections},
            goto="visuals"
        )
    
    return Command(
        update={"draft_sections": draft_sections},
        goto="critic"
    )
