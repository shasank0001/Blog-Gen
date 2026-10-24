import asyncio
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api import deps
from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.core.models import User, Thread, ThreadStatus, KnowledgeBin, StyleProfile
from app.core.workspace_models import GenerationJob, JobEvent, utcnow
from app.schemas_workspace import GenerateRequest, ResumeJob
from app.services.metering import account_for_update, model_price, committed
from app.services.safe_fetch import resolve_public_url, UnsafeURL
from app.services.workspace import owned_job, job_data

router = APIRouter()
TERMINAL = {'completed', 'failed', 'cancelled', 'budget_exceeded', 'awaiting_approval'}


@router.post('', status_code=201)
async def create_job(body: GenerateRequest, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    canonical = body.model_dump(mode='json', exclude={'idempotency_key'})
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    # Serialize creation per account, including duplicate requests across API processes.
    await account_for_update(db, user.id)
    existing = (await db.execute(select(GenerationJob).where(
        GenerationJob.user_id == user.id, GenerationJob.idempotency_key == body.idempotency_key))).scalar_one_or_none()
    if existing:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, 'This request key was already used with different settings')
        return await job_data(db, existing)
    active_count = (await db.execute(select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id, GenerationJob.status.in_(['queued', 'running', 'awaiting_approval'])))).scalar_one()
    if active_count >= 10:
        raise HTTPException(429, 'You already have 10 active runs. Finish or cancel a run before creating another.')
    try:
        model_price('ollama' if body.use_local or settings.USE_LOCAL_LLM else body.model_provider,
                    settings.OLLAMA_MODEL if body.use_local or settings.USE_LOCAL_LLM else body.model_name)
        if body.target_domain:
            target = body.target_domain if '://' in body.target_domain else 'https://' + body.target_domain
            url, _ = await resolve_public_url(target)
            body.target_domain = str(url).rstrip('/')
    except (ValueError, UnsafeURL) as exc:
        raise HTTPException(400, str(exc)) from exc
    if body.selected_bins:
        found = (await db.execute(select(KnowledgeBin.id).where(
            KnowledgeBin.id.in_(body.selected_bins), KnowledgeBin.user_id == user.id))).scalars().all()
        if set(found) != set(body.selected_bins):
            raise HTTPException(403, 'One or more knowledge bins do not belong to you')
    if body.profile_id:
        profile = (await db.execute(select(StyleProfile).where(
            StyleProfile.id == body.profile_id, StyleProfile.user_id == user.id))).scalar_one_or_none()
        if not profile:
            raise HTTPException(404, 'Style profile not found')
        if profile.style_dna:
            body.style_profile = profile.style_dna
        elif profile.tone_urls:
            body.tone_urls = profile.tone_urls
    job_id = uuid.uuid4()
    db.add(Thread(id=job_id, user_id=user.id, topic=body.topic, status=ThreadStatus.RUNNING,
                  target_audience=body.target_audience, extra_context=body.extra_context,
                  research_guidelines='\n'.join(body.research_guidelines)))
    await db.flush()
    state = body.model_dump(mode='json', exclude={'idempotency_key', 'cost_limit_usd', 'profile_id'})
    state.update(user_id=str(user.id), style_profile=body.style_profile or {}, current_section_index=0,
                 draft_sections={}, critique_feedback={}, section_retries={}, research_data=[], internal_links=[],
                 outline=[], deep_research_results=[], research_loop_count=0, is_sufficient=False,
                 generated_queries=[], target_word_count=0, section_word_budgets={}, final_content='')
    job = GenerationJob(id=job_id, user_id=user.id, idempotency_key=body.idempotency_key,
                        request_hash=fingerprint, status='queued', input_state=state, outline=[], cost_limit_usd=body.cost_limit_usd)
    db.add(job)
    await db.flush()
    db.add(JobEvent(job_id=job_id, event='status', payload={'status': 'queued'}))
    await db.commit()
    return await job_data(db, job)


@router.get('')
async def list_jobs(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                    db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    jobs = (await db.execute(select(GenerationJob).where(GenerationJob.user_id == user.id)
                            .order_by(desc(GenerationJob.created_at)).offset(skip).limit(limit + 1))).scalars().all()
    return {'items': [await job_data(db, job) for job in jobs[:limit]], 'has_more': len(jobs) > limit}


@router.get('/{job_id}')
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    return await job_data(db, await owned_job(db, user.id, job_id))


@router.post('/{job_id}/cancel')
async def cancel_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    job = await owned_job(db, user.id, job_id, lock=True)
    if job.status == 'completed':
        raise HTTPException(409, 'This run has already completed')
    job.cancel_requested = True
    if job.status != 'running':
        job.status = 'cancelled'
    job.updated_at = utcnow()
    db.add(JobEvent(job_id=job.id, event='status', payload={'status': job.status, 'cancel_requested': True}))
    await db.commit()
    return await job_data(db, job)


@router.post('/{job_id}/resume')
async def resume_job(job_id: uuid.UUID, body: ResumeJob, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    job = await owned_job(db, user.id, job_id, lock=True)
    if job.status not in {'awaiting_approval', 'failed', 'cancelled', 'budget_exceeded'}:
        raise HTTPException(409, 'Only paused or stopped runs can be resumed')
    if job.status == 'awaiting_approval' and body.approved_outline is None:
        raise HTTPException(400, 'Approve the outline before continuing')
    if body.approved_outline is not None and job.status != 'awaiting_approval':
        raise HTTPException(409, 'This run is not awaiting outline approval')
    if body.cost_limit_usd is not None:
        if body.cost_limit_usd < await committed(db, user.id, job.id):
            raise HTTPException(400, 'The limit cannot be below the amount already spent or held')
        job.cost_limit_usd = body.cost_limit_usd
    job.resume_payload = ({'approved_outline': [item.model_dump() for item in body.approved_outline]}
                          if body.approved_outline is not None else None)
    job.status, job.cancel_requested, job.error = 'queued', False, None
    job.updated_at = utcnow()
    db.add(JobEvent(job_id=job.id, event='status', payload={'status': 'queued'}))
    await db.commit()
    return await job_data(db, job)


@router.get('/{job_id}/events')
async def events(job_id: uuid.UUID, request: Request, after: int = Query(0, ge=0, le=9223372036854775807),
                 db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    await owned_job(db, user.id, job_id)
    try:
        cursor = max(after, int(request.headers.get('last-event-id', '0')))
        if cursor > 9223372036854775807:
            raise ValueError('Cursor exceeds the event ID range')
    except ValueError as exc:
        raise HTTPException(400, 'Invalid event cursor') from exc
    # Do not retain an idle DB connection while the browser subscribes.
    user_id = user.id
    await db.rollback()
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            async with AsyncSessionLocal() as session:
                job = await owned_job(session, user_id, job_id)
                batch = (await session.execute(select(JobEvent).where(JobEvent.job_id == job_id, JobEvent.id > cursor)
                                               .order_by(JobEvent.id).limit(100))).scalars().all()
                stopped = job.status in TERMINAL
            for event in batch:
                cursor = event.id
                yield {'id': str(event.id), 'event': event.event, 'data': json.dumps(event.payload)}
            if stopped and len(batch) < 100:
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(stream())
