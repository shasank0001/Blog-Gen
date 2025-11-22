from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.agent.graph import build_graph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
import uuid
from app.core.config import settings

router = APIRouter()

class RunRequest(BaseModel):
    topic: str
    tone_urls: List[str] = []
    target_domain: str = ""
    selected_bins: List[str] = []

class ResumeRequest(BaseModel):
    thread_id: str
    approved_outline: List[Dict[str, Any]]

class AgentRunner:
    def __init__(self):
        self.graph = None
        self.checkpointer = None
        self.checkpointer_context = None
        
    async def setup(self):
        # Ensure the DB URL is async-friendly if needed, or rely on the library to handle it.
        # AsyncPostgresSaver uses psycopg (v3) async connection.
        try:
            self.checkpointer_context = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
            self.checkpointer = await self.checkpointer_context.__aenter__()
            await self.checkpointer.setup()
            builder = build_graph()
            self.graph = builder.compile(checkpointer=self.checkpointer)
            print("Agent graph initialized with AsyncPostgresSaver")
        except Exception as e:
            print(f"Failed to initialize AsyncPostgresSaver: {e}")
            # Fallback to MemorySaver for dev if DB fails
            from langgraph.checkpoint.memory import MemorySaver
            self.checkpointer = MemorySaver()
            builder = build_graph()
            self.graph = builder.compile(checkpointer=self.checkpointer)
            print("Fallback to MemorySaver")

    async def shutdown(self):
        if self.checkpointer_context:
            await self.checkpointer_context.__aexit__(None, None, None)
            print("AsyncPostgresSaver connection closed")

agent_runner = AgentRunner()

@router.on_event("startup")
async def startup_event():
    await agent_runner.setup()

@router.on_event("shutdown")
async def shutdown_event():
    await agent_runner.shutdown()

@router.post("/run")
async def run_agent(request: RunRequest):
    if not agent_runner.graph:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "topic": request.topic,
        "tone_urls": request.tone_urls,
        "target_domain": request.target_domain,
        "selected_bins": request.selected_bins,
        "current_section_index": 0,
        "draft_sections": {},
        "critique_feedback": {}
    }
    
    result = await agent_runner.graph.ainvoke(initial_state, config=config)
    snapshot = await agent_runner.graph.aget_state(config)
    
    return {
        "thread_id": thread_id,
        "status": "interrupted" if snapshot.next else "completed",
        "state": snapshot.values
    }

@router.post("/resume")
async def resume_agent(request: ResumeRequest):
    if not agent_runner.graph:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    config = {"configurable": {"thread_id": request.thread_id}}
    
    result = await agent_runner.graph.ainvoke(
        Command(resume={"approved_outline": request.approved_outline}),
        config=config
    )
    
    snapshot = await agent_runner.graph.aget_state(config)
    
    return {
        "thread_id": request.thread_id,
        "status": "interrupted" if snapshot.next else "completed",
        "state": snapshot.values
    }

@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    if not agent_runner.graph:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await agent_runner.graph.aget_state(config)
    return {
        "values": snapshot.values,
        "next": snapshot.next
    }
