from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from app.agent.state import AgentState
from app.agent.nodes.style_analyst import style_analyst_node
from app.agent.nodes.internal_indexer import internal_indexer_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.planner import planner_node
from app.agent.nodes.human_approval import human_approval_node
from app.agent.nodes.writer import writer_node
from app.agent.nodes.critic import critic_node
from app.agent.nodes.visuals import visuals_node
from app.agent.nodes.publisher import publisher_node
from app.agent.nodes.deep_research import (
    generate_query_node, 
    web_research_node,
    social_research_node,
    academic_research_node,
    reflection_node, 
    finalize_answer_node
)

def build_graph():
    builder = StateGraph(AgentState)
    
    builder.add_node("internal_indexer", internal_indexer_node)
    builder.add_node("style_analyst", style_analyst_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("planner", planner_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("visuals", visuals_node)
    builder.add_node("publisher", publisher_node)
    
    # Deep Research Nodes
    builder.add_node("deep_generate_query", generate_query_node)
    builder.add_node("deep_web_research", web_research_node)
    builder.add_node("deep_social_research", social_research_node)
    builder.add_node("deep_academic_research", academic_research_node)
    builder.add_node("deep_reflection", reflection_node)
    builder.add_node("deep_finalize", finalize_answer_node)
    
    # Research Phase (Sequential for safety)
    builder.add_edge(START, "internal_indexer")
    builder.add_edge("internal_indexer", "style_analyst")
    
    # Conditional Routing for Research
    def route_research(state):
        if state.get("deep_research_mode"):
            return "deep_generate_query"
        return "researcher"

    builder.add_conditional_edges("style_analyst", route_research, ["deep_generate_query", "researcher"])
    
    # Deep Research Loop - Route to parallel research based on selected sources
    def route_to_research_tasks(state):
        queries = state.get("generated_queries", [])
        sources = state.get("research_sources", ["web", "internal"])
        tasks = []
        
        # Always run web research if 'web' is in sources
        if "web" in sources:
            tasks.extend([Send("deep_web_research", {"query": q}) for q in queries])
        
        # Add social research if enabled (only first query to avoid rate limits)
        if "social" in sources and queries:
            tasks.append(Send("deep_social_research", {"query": queries[0]}))
        
        # Add academic research if enabled (only first query)
        if "academic" in sources and queries:
            tasks.append(Send("deep_academic_research", {"query": queries[0]}))
        
        return tasks

    builder.add_conditional_edges(
        "deep_generate_query", 
        route_to_research_tasks, 
        ["deep_web_research", "deep_social_research", "deep_academic_research"]
    )
    builder.add_edge("deep_web_research", "deep_reflection")
    builder.add_edge("deep_social_research", "deep_reflection")
    builder.add_edge("deep_academic_research", "deep_reflection")
    
    def route_after_reflection(state):
        if state.get("is_sufficient") or state.get("research_loop_count", 0) > 3:
            return "deep_finalize"
        return "deep_generate_query"

    builder.add_conditional_edges("deep_reflection", route_after_reflection, ["deep_finalize", "deep_generate_query"])
    
    # Rejoin Main Flow
    builder.add_edge("deep_finalize", "planner")
    builder.add_edge("researcher", "planner")
    
    # Planning Phase
    builder.add_edge("planner", "human_approval")
    
    # Generation Loop
    # human_approval -> writer (via Command)
    # writer -> critic (via Command)
    # critic -> writer (retry) or visuals (pass) (via Command)
    # visuals -> writer (next section) or publisher (done) (via Command)
    
    builder.add_edge("publisher", END)
    
    return builder
