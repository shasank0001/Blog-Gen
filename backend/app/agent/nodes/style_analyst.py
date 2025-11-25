from app.agent.state import AgentState
from app.services.firecrawl_service import firecrawl_service
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
import json
from typing import List, Dict, Any

async def analyze_style(urls: List[str], use_local: bool = False, model_provider: str = "anthropic", model_name: str = "claude-haiku-4-5") -> Dict[str, Any]:
    if not urls:
        print("[Style Analyst] No URLs provided, returning default style")
        return {"tone": "neutral", "formatting": "standard"}
    
    print(f"[Style Analyst] Analyzing {len(urls)} URLs: {urls}")
    scraped_content = []
    scraping_errors = []
    
    for url in urls:
        try:
            print(f"[Style Analyst] Scraping {url}...")
            result = firecrawl_service.scrape(url)
            
            # Handle both dict and Document object formats
            if result:
                # Try to get markdown content (supports both dict and object attribute access)
                markdown_content = None
                if isinstance(result, dict) and 'markdown' in result:
                    markdown_content = result['markdown']
                elif hasattr(result, 'markdown'):
                    markdown_content = result.markdown
                
                if markdown_content:
                    content = markdown_content[:5000]
                    print(f"[Style Analyst] Successfully scraped {len(content)} chars from {url}")
                    scraped_content.append(content)
                else:
                    error_msg = f"No markdown content in response from {url}"
                    print(f"[Style Analyst] {error_msg}")
                    scraping_errors.append(error_msg)
            else:
                error_msg = f"Empty response from {url}"
                print(f"[Style Analyst] {error_msg}")
                scraping_errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error scraping {url}: {str(e)}"
            print(f"[Style Analyst] {error_msg}")
            scraping_errors.append(error_msg)
            
    if not scraped_content:
        print(f"[Style Analyst] WARNING: All scraping failed! Errors: {scraping_errors}")
        return {
            "tone": "neutral", 
            "formatting": "standard",
            "note": "scraping_failed",
            "errors": scraping_errors
        }

    combined_text = "\n\n---\n\n".join(scraped_content)
    print(f"[Style Analyst] Combined text length: {len(combined_text)} chars")
    
    prompt = ChatPromptTemplate.from_template(
        """
        Analyze the following text samples to extract a "Style DNA" profile.
        Return a JSON object with keys: 'tone', 'vocabulary_complexity', 'sentence_structure', 'formatting_preferences', 'forbidden_words'.
        
        Text Samples:
        {text}
        """
    )
    
    print(f"[Style Analyst] Calling LLM ({model_provider}/{model_name}) for style analysis...")
    llm = llm_service.get_llm(
        model_provider=model_provider,
        model_name=model_name,
        temperature=0, 
        use_local=use_local
    )
    chain = prompt | llm
    response = await chain.ainvoke({"text": combined_text})
    print(f"[Style Analyst] LLM response received")
    
    try:
        # Handle potential markdown code blocks in response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        style_profile = json.loads(content)
        print(f"[Style Analyst] Successfully parsed style profile: {list(style_profile.keys())}")
    except Exception as e:
        print(f"[Style Analyst] Failed to parse LLM response: {e}")
        print(f"[Style Analyst] Raw response: {response.content[:500]}")
        style_profile = {"tone": "professional", "note": "parsing_failed", "raw_output": response.content}
        
    return style_profile

async def style_analyst_node(state: AgentState):
    # If style_profile is already provided (e.g. from DB), skip analysis
    if state.get("style_profile") and state["style_profile"].get("tone"):
        return {"style_profile": state["style_profile"]}

    urls = state.get("tone_urls", [])
    use_local = state.get("use_local", False)
    model_provider = state.get("model_provider", "anthropic")
    model_name = state.get("model_name", "claude-haiku-4-5")
    
    style_profile = await analyze_style(urls, use_local=use_local, model_provider=model_provider, model_name=model_name)
        
    return {"style_profile": style_profile}
