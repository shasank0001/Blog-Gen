from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.agent.graph import build_graph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
import uuid
import json
import asyncio
from app.core.config import settings
from sse_starlette.sse import EventSourceResponse
from app.agent.nodes.style_analyst import analyze_style
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.core.database import get_db
from app.core.models import User, StyleProfile, Thread, ThreadStatus, KnowledgeBin
from datetime import datetime, timezone
import os
from app.utils.workflow_summary import generate_summary_for_thread
from fastapi.encoders import jsonable_encoder

def log_to_file(thread_id: str, category: str, payload: Any):
    try:
        log_dir = "workflow_logs"
        os.makedirs(log_dir, exist_ok=True)
        file_path = os.path.join(log_dir, f"{thread_id}.jsonl")
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "payload": payload
        }
        
        with open(file_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as e:
        print(f"Logging failed: {e}")

router = APIRouter()

class RunRequest(BaseModel):
    topic: str
    tone_urls: List[str] = []
    profile_id: Optional[uuid.UUID] = None
    target_domain: str = ""
    selected_bins: List[str] = []
    use_local: bool = False
    model_provider: str = "anthropic"
    model_name: str = "claude-haiku-4-5"
    style_profile: Optional[Dict[str, Any]] = None
    research_sources: List[str] = ["web", "internal"] # Default to web and internal
    deep_research_mode: bool = False
    blog_size: str = "medium" # small, medium, large
    
    research_guidelines: List[str] = []
    target_audience: str = ""
    extra_context: str = ""

class ResumeRequest(BaseModel):
    thread_id: str
    approved_outline: List[Dict[str, Any]]

class StyleAnalysisRequest(BaseModel):
    urls: List[str]
    use_local: bool = False

class AgentRunner:
    def __init__(self):
        self.graph = None
        self.checkpointer = None
        self.checkpointer_context = None
        
    async def setup(self):
        # Ensure the DB URL is async-friendly if needed, or rely on the library to handle it.
        # AsyncPostgresSaver uses psycopg (v3) async connection.
        try:
            # Fix connection string for AsyncPostgresSaver (needs postgresql:// not postgresql+asyncpg://)
            conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            self.checkpointer_context = AsyncPostgresSaver.from_conn_string(conn_string)
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

runner = AgentRunner()

@router.on_event("startup")
async def startup_event():
    await runner.setup()

@router.on_event("shutdown")
async def shutdown_event():
    await runner.shutdown()

@router.post("/stream")
async def stream_agent(
    request: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Start the agent workflow and stream events via SSE.
    """
    if not runner.graph:
        raise HTTPException(status_code=503, detail="Agent not initialized")
        
    # Verify bins ownership
    if request.selected_bins:
        # Convert strings to UUIDs if needed, assuming they are UUID strings
        try:
            bin_ids = [uuid.UUID(b) for b in request.selected_bins]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bin id format")

        result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id.in_(bin_ids), KnowledgeBin.user_id == current_user.id))
        found_bins = result.scalars().all()
        if len(found_bins) != len(request.selected_bins):
             raise HTTPException(status_code=403, detail="One or more selected bins do not belong to the user")

    # Fetch profile if provided
    if request.profile_id:
        result = await db.execute(select(StyleProfile).where(StyleProfile.id == request.profile_id, StyleProfile.user_id == current_user.id))
        profile = result.scalars().first()
        if profile and profile.style_dna:
            request.style_profile = profile.style_dna
        elif profile and profile.tone_urls:
             request.tone_urls = profile.tone_urls

    thread_id = str(uuid.uuid4())
    
    # Create Thread record
    thread = Thread(
        id=uuid.UUID(thread_id),
        user_id=current_user.id,
        topic=request.topic,
        target_audience=request.target_audience,
        research_guidelines="\n".join(request.research_guidelines) if request.research_guidelines else None,
        extra_context=request.extra_context,
        status=ThreadStatus.RUNNING
    )
    db.add(thread)
    await db.commit()
    
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 150}
    
    initial_state = {
        "user_id": str(current_user.id),
        "topic": request.topic,
        "tone_urls": request.tone_urls,
        "target_domain": request.target_domain,
        "selected_bins": request.selected_bins,
        "use_local": request.use_local,
        "model_provider": request.model_provider,
        "model_name": request.model_name,
        "research_sources": request.research_sources,
        "deep_research_mode": request.deep_research_mode,
        "blog_size": request.blog_size,
        "research_guidelines": request.research_guidelines,
        "target_audience": request.target_audience,
        "extra_context": request.extra_context,
        "style_profile": request.style_profile or {},
        "current_section_index": 0,
        "draft_sections": {},
        "critique_feedback": {},
        "section_retries": {},
        # Initialize fields that will be set by nodes
        "research_data": [],
        "internal_links": [],
        "outline": [],
        "deep_research_results": [],
        "research_loop_count": 0,
        "is_sufficient": False,
        "generated_queries": [],
        "target_word_count": 0,  # Will be set by planner based on blog_size
        "section_word_budgets": {},  # Will be set by planner
        "final_content": ""
    }
    
    log_to_file(thread_id, "initial_state", initial_state)

    async def event_generator():
        yield {
            "event": "metadata",
            "data": json.dumps({"thread_id": thread_id})
        }
        
        try:
            async for event in runner.graph.astream_events(initial_state, config, version="v1"):
                kind = event["event"]
                name = event["name"]
                
                # Log relevant node events
                if kind in ["on_chain_start", "on_chain_end"] and name in ["internal_indexer", "style_analyst", "researcher", "planner", "writer", "critic", "visuals", "publisher"]:
                    log_to_file(thread_id, f"{name}_{kind}", event["data"])

                # Filter and format events
                if kind == "on_chain_start" and name == "LangGraph":
                    continue
                    
                if kind == "on_chain_start" and name in ["internal_indexer", "style_analyst", "researcher", "planner", "writer", "critic", "visuals", "publisher"]:
                    yield {
                        "event": "step_start",
                        "data": json.dumps({"step": event["name"], "status": "running"})
                    }
                    
                elif kind == "on_chain_end" and name in ["internal_indexer", "style_analyst", "researcher", "planner", "writer", "critic", "visuals", "publisher"]:
                    output = event["data"].get("output")
                    # Handle Command objects if present (though usually they are processed by LangGraph)
                    # If output is a dict or list, jsonable_encoder handles it.
                    # If it's a Command, we might want to extract the update.
                    # But for now, let's try jsonable_encoder.
                    try:
                        serialized_output = jsonable_encoder(output)
                    except:
                        serialized_output = str(output)
                        
                    yield {
                        "event": "step_complete",
                        "data": json.dumps({"step": name, "status": "completed", "output": serialized_output})
                    }
                
                elif kind == "on_chain_end" and name == "LangGraph":
                    # Check if we reached the end (not just paused)
                    # But LangGraph emits on_chain_end even when paused.
                    # We rely on the interrupt check below for pauses.
                    # If it's truly done, we might want to mark it.
                    # But usually stream_agent pauses at human_approval.
                    pass
                    
                # Handle Interrupts (Human Approval)
                # Note: astream_events might not catch interrupts directly as events in v1, 
                # but we can check if the run stops. 
                # However, LangGraph v0.2+ handles interrupts differently.
                # We might need to check the state after the stream ends or handle specific interrupt events if available.
                
        except Exception as e:
            thread.status = ThreadStatus.FAILED
            await db.commit()
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
            
        # Check final state for interrupt
        snapshot = await runner.graph.aget_state(config)
        if snapshot.tasks:
            for task in snapshot.tasks:
                if task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    payload = interrupt_value.get("outline") if isinstance(interrupt_value, dict) else snapshot.values.get("outline")
                    
                    log_to_file(thread_id, "interrupt", payload)
                    
                    yield {
                        "event": "interrupt",
                        "data": json.dumps({"type": "human_approval", "payload": payload})
                    }
                    break
        else:
             # If no tasks and no interrupts, maybe it finished? (Unlikely for stream_agent which usually pauses)
             pass

    return EventSourceResponse(event_generator())

@router.post("/resume")
async def resume_agent(
    request: ResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Resume the agent workflow after human approval.
    """
    if not runner.graph:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Verify thread ownership
    try:
        thread_uuid = uuid.UUID(request.thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread_id format")

    result = await db.execute(select(Thread).where(Thread.id == thread_uuid, Thread.user_id == current_user.id))
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found or access denied")
        
    config = {"configurable": {"thread_id": request.thread_id}, "recursion_limit": 150}
    
    async def event_generator():
        # Construct the Command to resume
        resume_command = Command(
            resume={"approved_outline": request.approved_outline}
        )
        
        log_to_file(request.thread_id, "resume_command", request.approved_outline)
        
        try:
            async for event in runner.graph.astream_events(resume_command, config, version="v1"):
                kind = event["event"]
                name = event["name"]
                
                # Log relevant node events
                if kind in ["on_chain_start", "on_chain_end"] and name in ["writer", "critic", "visuals", "publisher"]:
                    log_to_file(request.thread_id, f"{name}_{kind}", event["data"])
                
                if kind == "on_chain_start" and name in ["writer", "critic", "visuals", "publisher"]:
                    yield {
                        "event": "step_start",
                        "data": json.dumps({"step": name, "status": "running"})
                    }
                    
                elif kind == "on_chain_end" and name in ["writer", "critic", "visuals", "publisher"]:
                    output = event["data"].get("output")
                    try:
                        serialized_output = jsonable_encoder(output)
                    except:
                        serialized_output = str(output)

                    yield {
                        "event": "step_complete",
                        "data": json.dumps({"step": name, "status": "completed", "output": serialized_output})
                    }
                
                elif kind == "on_chain_end" and name == "LangGraph":
                     # Update thread status to COMPLETED
                    thread.status = ThreadStatus.COMPLETED
                    thread.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await db.commit()
                    
                    log_to_file(request.thread_id, "workflow_complete", event["data"].get("output"))
                    
                    # Generate Markdown summary automatically
                    try:
                        summary_path = generate_summary_for_thread(request.thread_id, "workflow_logs")
                        print(f"✅ Generated workflow summary: {summary_path}")
                    except Exception as summary_error:
                        print(f"⚠️ Failed to generate workflow summary: {summary_error}")
                    
                    yield {
                        "event": "end",
                        "data": json.dumps({"output": event["data"].get("output")})
                    }

        except Exception as e:
            thread.status = ThreadStatus.FAILED
            await db.commit()
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())

@router.post("/analyze-style")
async def analyze_style_endpoint(
    request: StyleAnalysisRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Analyze URLs to extract a Style DNA profile.
    """
    style_profile = await analyze_style(request.urls, use_local=request.use_local)
    return style_profile

@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    if not runner.graph:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await runner.graph.aget_state(config)
    return {
        "values": snapshot.values,
        "next": snapshot.next
    }
