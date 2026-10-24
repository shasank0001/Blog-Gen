import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.core.database import get_db
from app.core.models import User, Thread
from app.core.workspace_models import GenerationJob, Article
from app.agent.nodes.style_analyst import analyze_style
from app.services.graph_runner import runner

router = APIRouter()


class StyleAnalysisRequest(BaseModel):
    urls: list[str] = Field(max_length=10)
    use_local: bool = False


@router.on_event('startup')
async def startup_event():
    await runner.setup()


@router.on_event('shutdown')
async def shutdown_event():
    await runner.shutdown()


@router.post('/stream')
@router.post('/resume')
async def legacy_execution(user: User = Depends(deps.get_current_user)):
    raise HTTPException(410, 'Generation now uses durable /api/v1/jobs with separate event subscriptions')


@router.post('/analyze-style')
async def analyze_style_endpoint(body: StyleAnalysisRequest, user: User = Depends(deps.get_current_user)):
    # This optional standalone analysis is not included in generation spending.
    return await analyze_style(body.urls, use_local=body.use_local)


@router.get('/state/{thread_id}')
async def get_state(thread_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    current_user: User = Depends(deps.get_current_user)):
    result = await db.execute(select(Thread).where(Thread.id == thread_id, Thread.user_id == current_user.id))
    if not result.scalars().first():
        raise HTTPException(404, 'Thread not found')
    job = await db.get(GenerationJob, thread_id)
    if job:
        article = (await db.execute(select(Article).where(Article.job_id == thread_id))).scalar_one_or_none()
        return {'values': {'outline': job.outline, 'final_content': article.content if article else ''},
                'next': ['human_approval'] if job.status == 'awaiting_approval' else []}
    if not runner.graph:
        raise HTTPException(503, 'Agent not initialized')
    snapshot = await runner.graph.aget_state({'configurable': {'thread_id': str(thread_id)}})
    return {'values': snapshot.values, 'next': snapshot.next}
