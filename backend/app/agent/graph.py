from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes.style_analyst import style_analyst_node
from app.agent.nodes.researcher import researcher_node
from app.agent.nodes.planner import planner_node
from app.agent.nodes.human_approval import human_approval_node
from app.agent.nodes.writer import writer_node
from app.agent.nodes.critic import critic_node
from app.agent.nodes.publisher import publisher_node

def build_graph():
    builder = StateGraph(AgentState)
    
    builder.add_node("style_analyst", style_analyst_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("planner", planner_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("writer", writer_node)
    builder.add_node("critic", critic_node)
    builder.add_node("publisher", publisher_node)
    
    # Flow
    builder.add_edge(START, "style_analyst")
    builder.add_edge("style_analyst", "researcher")
    builder.add_edge("researcher", "planner")
    builder.add_edge("planner", "human_approval")
    
    # human_approval -> writer is handled by Command
    
    builder.add_edge("writer", "critic")
    
    # critic -> writer (next section) or publisher is handled by Command
    
    builder.add_edge("publisher", END)
    
    return builder
