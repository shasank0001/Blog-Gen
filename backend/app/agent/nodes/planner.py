from app.agent.state import AgentState
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from app.utils.llm_logger import llm_logger
import json

class SectionModel(BaseModel):
    id: str = Field(description="Unique ID like sec_1")
    title: str
    intent: str
    source_ids: List[str] = Field(description="List of Source IDs to cite")
    content: Optional[str] = None

class Outline(BaseModel):
    sections: List[SectionModel]

class WordBudgetAllocation(BaseModel):
    """LLM-generated word budget allocation per section"""
    section_budgets: Dict[str, int] = Field(description="Map of section_id to target word count")
    reasoning: str = Field(description="Explanation of how words were allocated")

async def planner_node(state: AgentState):
    topic = state["topic"]
    research_data = state.get("research_data", [])
    style = state.get("style_profile", {})
    use_local = state.get("use_local", False)
    audience = state.get("target_audience", "General Audience")
    guidelines = state.get("research_guidelines", [])
    blog_size = state.get("blog_size", "medium")
    
    # Map blog size to target word count AND recommended section count
    size_guidelines = {
        "small": {"word_count": 2500, "min_sections": 3, "max_sections": 5},
        "medium": {"word_count": 5500, "min_sections": 6, "max_sections": 8},
        "large": {"word_count": 10000, "min_sections": 10, "max_sections": 15}
    }
    guidelines_config = size_guidelines.get(blog_size, size_guidelines["medium"])
    target_word_count = guidelines_config["word_count"]
    min_sections = guidelines_config["min_sections"]
    max_sections = guidelines_config["max_sections"]
    
    context = ""
    for item in research_data:
        context += f"Source ID: {item.get('source_id')}\nTitle: {item.get('title', 'Untitled')}\nContent: {item.get('content', '')[:500]}\n\n"
        
    guidelines_str = "\n".join(f"- {g}" for g in guidelines) if guidelines else "None"

    # PASS 1: Create outline
    outline_prompt = ChatPromptTemplate.from_template(
        """
        You are a Content Strategist. Create a detailed blog post outline for the topic: "{topic}".
        
        Target Audience: {audience}
        Blog Size: {blog_size}
        Blog Length Target: {target_word_count} words
        Required Section Count: {min_sections} to {max_sections} sections (STRICT)
        
        Specific Guidelines:
        {guidelines}
        
        Style Profile: {style}
        
        Available Research:
        {context}
        
        Create an outline where each section is assigned specific Intent and Source IDs (from the provided Research Context).
        Ensure Source IDs match exactly what is provided in the context (e.g., web_1, int_abc_1).
        
        CRITICAL CONSTRAINTS: 
        - You MUST create between {min_sections} and {max_sections} sections - no more, no less
        - For a {blog_size} blog ({target_word_count} words), this section range is mandatory
        - Each section will average {avg_words_per_section} words
        - Prioritize using 'internal' sources (IDs starting with 'int_') over web sources where possible
        - Focus on the most important aspects of the topic to fit within the section limit
        - Quality over quantity: fewer well-developed sections are better than many shallow ones
        
        Section Count Guidance by Blog Size:
        - Small (2,500 words): 3-5 focused sections covering core concepts
        - Medium (5,500 words): 6-8 sections with moderate depth
        - Large (10,000 words): 10-15 comprehensive sections with deep coverage
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=state.get("model_provider", "anthropic"),
        model_name=state.get("model_name", "claude-haiku-4-5"),
        use_local=use_local
    )
    structured_llm = llm.with_structured_output(Outline)
    chain = outline_prompt | structured_llm
    
    # Calculate average words per section for the prompt
    avg_words_per_section = target_word_count // max_sections
    
    try:
        prompt_vars = {
            "topic": topic, 
            "style": str(style), 
            "context": context,
            "audience": audience,
            "guidelines": guidelines_str,
            "blog_size": blog_size,
            "target_word_count": target_word_count,
            "min_sections": min_sections,
            "max_sections": max_sections,
            "avg_words_per_section": avg_words_per_section
        }
        result = await chain.ainvoke(prompt_vars)
        # Convert Pydantic models to dicts for State
        outline = [section.model_dump() for section in result.sections]
        
        # Log the LLM call
        thread_id = state.get("user_id", "unknown")  # Using user_id as proxy for thread_id
        try:
            # Format the full prompt for logging
            formatted_prompt = outline_prompt.format(**prompt_vars)
        except:
            formatted_prompt = str(outline_prompt.messages[0].prompt.template) if hasattr(outline_prompt, 'messages') else str(outline_prompt)
        
        llm_logger.log_call(
            thread_id=thread_id,
            node_name="planner_pass1_outline",
            prompt=formatted_prompt,
            response=json.dumps([s.model_dump() for s in result.sections], indent=2),
            metadata={
                "blog_size": blog_size,
                "target_word_count": target_word_count,
                "min_sections": min_sections,
                "max_sections": max_sections,
                "actual_sections_created": len(outline)
            },
            model_info={
                "provider": state.get("model_provider", "anthropic"),
                "name": state.get("model_name", "claude-haiku-4-5")
            }
        )
        
        # Validate section count (safety check)
        section_count = len(outline)
        if section_count < min_sections or section_count > max_sections:
            print(f"⚠️  WARNING: LLM created {section_count} sections, expected {min_sections}-{max_sections} for {blog_size} blog")
            print(f"   Adjusting outline to meet constraints...")
            # If too many sections, truncate to max
            if section_count > max_sections:
                outline = outline[:max_sections]
                print(f"   Truncated to {max_sections} sections")
            # If too few and we have at least 2, we'll proceed (edge case)
            elif section_count < min_sections and section_count >= 2:
                print(f"   Proceeding with {section_count} sections (minimum viable)")
            
    except Exception as e:
        print(f"Planner failed: {e}")
        outline = [
            {"id": "sec_1", "title": "Introduction", "intent": "Introduce topic", "source_ids": [], "content": None},
            {"id": "sec_2", "title": "Main Point", "intent": "Discuss main point", "source_ids": [], "content": None},
            {"id": "sec_3", "title": "Conclusion", "intent": "Summarize", "source_ids": [], "content": None}
        ]
    
    # PASS 2: Allocate word budgets across sections
    section_titles = [s["title"] for s in outline]
    section_ids = [s["id"] for s in outline]
    
    budget_prompt = ChatPromptTemplate.from_template(
        """
        You are an expert content planner. Allocate a word budget across blog sections to reach a total target.
        
        Total Target Word Count: {target_word_count} words
        Blog Size: {blog_size}
        
        Sections to allocate budget for:
        {section_list}
        
        Your task:
        1. Distribute {target_word_count} words across the {num_sections} sections
        2. Consider:
           - Introduction/Conclusion sections are typically shorter (200-500 words)
           - Main content sections should be more substantial (500-2000 words)
           - Distribute proportionally based on section importance and depth
        3. The sum of all section budgets should approximately equal {target_word_count}
        
        Return a mapping of section_id to target word count for each section.
        """
    )
    
    section_list = "\n".join(f"- {sid}: {title}" for sid, title in zip(section_ids, section_titles))
    
    budget_llm = llm.with_structured_output(WordBudgetAllocation)
    budget_chain = budget_prompt | budget_llm
    
    try:
        budget_vars = {
            "target_word_count": target_word_count,
            "blog_size": blog_size,
            "section_list": section_list,
            "num_sections": len(outline)
        }
        budget_result = await budget_chain.ainvoke(budget_vars)
        section_word_budgets = budget_result.section_budgets
        print(f"Word Budget Allocation: {section_word_budgets}")
        print(f"Reasoning: {budget_result.reasoning}")
        
        # Log the budget allocation call
        try:
            formatted_budget_prompt = budget_prompt.format(**budget_vars)
        except:
            formatted_budget_prompt = str(budget_prompt.messages[0].prompt.template) if hasattr(budget_prompt, 'messages') else str(budget_prompt)
        
        llm_logger.log_call(
            thread_id=thread_id,
            node_name="planner_pass2_budget",
            prompt=formatted_budget_prompt,
            response=json.dumps(budget_result.model_dump(), indent=2),
            metadata={
                "blog_size": blog_size,
                "target_word_count": target_word_count,
                "num_sections": len(outline),
                "total_allocated": sum(section_word_budgets.values())
            },
            model_info={
                "provider": state.get("model_provider", "anthropic"),
                "name": state.get("model_name", "claude-haiku-4-5")
            }
        )
    except Exception as e:
        print(f"Budget allocation failed: {e}. Using simple division.")
        # Fallback: divide evenly
        words_per_section = target_word_count // len(outline)
        section_word_budgets = {s["id"]: words_per_section for s in outline}
        
    return {
        "outline": outline,
        "target_word_count": target_word_count,
        "section_word_budgets": section_word_budgets,
        "critique_feedback": {},
        "section_retries": {},
        "draft_sections": {}
    }
