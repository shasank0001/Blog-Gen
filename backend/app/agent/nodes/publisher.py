from app.agent.state import AgentState

def publisher_node(state: AgentState):
    drafts = state.get("draft_sections", {})
    outline = state.get("outline", [])
    
    final_doc = f"# {state.get('topic', 'Blog Post')}\n\n"
    
    for section in outline:
        final_doc += f"## {section['title']}\n\n"
        final_doc += drafts.get(section['id'], "") + "\n\n"
        
    return {"final_content": final_doc}
