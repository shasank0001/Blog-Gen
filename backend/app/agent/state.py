from typing import TypedDict, List, Dict, Any, Optional

class Section(TypedDict):
    id: str
    title: str
    intent: str
    source_ids: List[str]
    content: Optional[str]

class AgentState(TypedDict):
    topic: str
    tone_urls: List[str]
    target_domain: str
    selected_bins: List[str]
    
    style_profile: Dict[str, Any]
    research_data: List[Dict[str, Any]]
    
    outline: List[Section]
    
    current_section_index: int
    
    draft_sections: Dict[str, str]
    critique_feedback: Dict[str, str]
    
    final_content: str
