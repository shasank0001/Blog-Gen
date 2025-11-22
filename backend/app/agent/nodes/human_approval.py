from app.agent.state import AgentState
from langgraph.types import interrupt, Command

def human_approval_node(state: AgentState):
    user_feedback = interrupt({"outline": state["outline"]})
    
    if user_feedback and "approved_outline" in user_feedback:
        return Command(
            update={"outline": user_feedback["approved_outline"]},
            goto="writer"
        )
    
    return Command(goto="planner")
