from app.agent.state import AgentState
from app.services.firecrawl_service import firecrawl_service
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
import json
from typing import List, Dict, Any

async def analyze_style(urls: List[str], use_local: bool = False, model_provider: str = "openai", model_name: str = "gpt-5.1") -> Dict[str, Any]:
    if not urls:
        return {"tone": "neutral", "formatting": "standard"}
    
    scraped_content = []
    for url in urls:
        try:
            result = firecrawl_service.scrape(url)
            if result and 'markdown' in result:
                scraped_content.append(result['markdown'][:5000])
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            
    if not scraped_content:
        return {"tone": "neutral", "formatting": "standard"}

    combined_text = "\n\n---\n\n".join(scraped_content)
    
    prompt = ChatPromptTemplate.from_template(
        """
        Analyze the following text samples to extract a "Style DNA" profile.
        Return a JSON object with keys: 'tone', 'vocabulary_complexity', 'sentence_structure', 'formatting_preferences', 'forbidden_words'.
        
        Text Samples:
        {text}
        """
    )
    
    llm = llm_service.get_llm(
        model_provider=model_provider,
        model_name=model_name,
        temperature=0, 
        use_local=use_local
    )
    chain = prompt | llm
    response = await chain.ainvoke({"text": combined_text})
    
    try:
        # Handle potential markdown code blocks in response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        style_profile = json.loads(content)
    except:
        style_profile = {"tone": "professional", "note": "parsing_failed", "raw_output": response.content}
        
    return style_profile

async def style_analyst_node(state: AgentState):
    # If style_profile is already provided (e.g. from DB), skip analysis
    if state.get("style_profile") and state["style_profile"].get("tone"):
        return {"style_profile": state["style_profile"]}

    urls = state.get("tone_urls", [])
    use_local = state.get("use_local", False)
    model_provider = state.get("model_provider", "openai")
    model_name = state.get("model_name", "gpt-5.1")
    
    style_profile = await analyze_style(urls, use_local=use_local, model_provider=model_provider, model_name=model_name)
        
    return {"style_profile": style_profile}
