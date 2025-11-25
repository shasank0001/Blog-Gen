from typing import TypedDict, List, Dict, Any, Optional, Annotated
from typing_extensions import Annotated as AnnotatedExt
from pydantic import BaseModel, Field
import operator

class Section(TypedDict):
    id: str
    title: str
    intent: str
    source_ids: List[str]
    content: Optional[str]

class Citation(BaseModel):
    url: str
    title: str
    content: str

class ResearchResult(BaseModel):
    query: str
    summary: str
    citations: List[Citation]

class AgentState(TypedDict):
    user_id: str # Added for namespace construction
    topic: str
    tone_urls: List[str]
    target_domain: str
    selected_bins: List[str]
    use_local: bool = False
    model_provider: str = "anthropic" # openai, anthropic, google
    model_name: str = "claude-haiku-4-5"
    research_sources: List[str] # ['web', 'social', 'academic', 'internal']
    deep_research_mode: bool = False # Added for Deep Research Toggle
    
    blog_size: str # 'small', 'medium', 'large'
    target_word_count: int # 2500, 5500, 10000
    section_word_budgets: Dict[str, int] # section_id -> word_count
    
    research_guidelines: List[str]
    target_audience: str
    extra_context: str

    style_profile: Dict[str, Any]
    research_data: List[Dict[str, Any]]
    
    # Deep Research State - use operator.add to handle concurrent updates
    deep_research_results: Annotated[List[ResearchResult], operator.add]
    research_loop_count: int
    is_sufficient: bool
    generated_queries: List[str] # For the deep research loop
    
    internal_links: List[Dict[str, str]]  # Added for Internal Indexer
    
    outline: List[Section]
    
    current_section_index: int
    
    draft_sections: Dict[str, str]
    critique_feedback: Dict[str, str]
    section_retries: Dict[str, int]  # Added for Reflexion Loop
    
    final_content: str
