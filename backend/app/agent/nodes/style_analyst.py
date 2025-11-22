from app.agent.state import AgentState
from app.services.firecrawl_service import firecrawl_service
from app.services.llm_service import llm_service
from langchain_core.prompts import ChatPromptTemplate
import json

async def style_analyst_node(state: AgentState):
    urls = state.get("tone_urls", [])
    if not urls:
        return {"style_profile": {"tone": "neutral", "formatting": "standard"}}
    
    scraped_content = []
    for url in urls:
        try:
            result = firecrawl_service.scrape(url)
            if result and 'markdown' in result:
                scraped_content.append(result['markdown'][:5000])
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            
    if not scraped_content:
        return {"style_profile": {"tone": "neutral", "formatting": "standard"}}

    combined_text = "\n\n---\n\n".join(scraped_content)
    
    prompt = ChatPromptTemplate.from_template(
        """
        Analyze the following text samples to extract a "Style DNA" profile.
        Return a JSON object with keys: 'tone', 'vocabulary_complexity', 'sentence_structure', 'formatting_preferences', 'forbidden_words'.
        
        Text Samples:
        {text}
        """
    )
    
    llm = llm_service.get_llm(model_name="gpt-4o", temperature=0)
    chain = prompt | llm
    response = await chain.ainvoke({"text": combined_text})
    
    try:
        style_profile = json.loads(response.content)
    except:
        style_profile = {"tone": "professional", "note": "parsing_failed"}
        
    return {"style_profile": style_profile}
