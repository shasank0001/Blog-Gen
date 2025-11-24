import re
from app.agent.state import AgentState

def publisher_node(state: AgentState):
    drafts = state.get("draft_sections", {})
    outline = state.get("outline", [])
    research_data = state.get("research_data", [])
    
    final_doc = f"# {state.get('topic', 'Blog Post')}\n\n"
    
    used_source_ids = set()
    source_map = {r.get("source_id"): r for r in research_data if r.get("source_id")}
    
    for section in outline:
        content = drafts.get(section['id'], "")
        final_doc += f"## {section['title']}\n\n"
        final_doc += content + "\n\n"
        
        # Find all [source_id] tags regardless of prefix, but ignore markdown links
        matches = re.findall(r'\[([a-zA-Z0-9_\-]+)\]', content)
        for match in matches:
            if match in source_map:
                used_source_ids.add(match)
        
    # Build References Section
    if used_source_ids:
        final_doc += "## References\n\n"
        
        for sid in sorted(used_source_ids):
            source = source_map.get(sid)
            if source:
                title = source.get("title", "Unknown Source")
                url = source.get("url")
                if url:
                    final_doc += f"- [{title}]({url})\n"
                else:
                    final_doc += f"- {title} (Internal Document)\n"
                    
    return {"final_content": final_doc}
