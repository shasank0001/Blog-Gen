"""Independent PostgreSQL job worker: python -m app.worker."""
import asyncio
import json
import logging
import signal
import uuid
from datetime import timedelta

import psycopg
from fastapi.encoders import jsonable_encoder
from langgraph.types import Command
from sqlalchemy import select, or_, and_, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.models import Thread, ThreadStatus
from app.core.workspace_models import GenerationJob, JobEvent, Article, LLMCall, utcnow
from app.services.graph_runner import AgentRunner
from app.services.metering import MeterContext, current_meter, BudgetExceeded
from app.services.workspace import add_revision
from app import worker_health

log = logging.getLogger(__name__)
STEPS = {'internal_indexer', 'style_analyst', 'researcher', 'planner', 'writer', 'critic', 'visuals',
         'publisher', 'deep_generate_query', 'deep_web_research', 'deep_social_research',
         'deep_academic_research', 'deep_reflection', 'deep_finalize'}


def eligible():
    return or_(GenerationJob.status == 'queued', and_(GenerationJob.status == 'running',
                GenerationJob.lease_expires_at < utcnow()))


async def claim_job():
    async with AsyncSessionLocal() as db:
        candidates = (await db.execute(select(GenerationJob.id).where(eligible())
                                      .order_by(GenerationJob.created_at).limit(20))).scalars().all()
    for job_id in candidates:
        # The session lock is held for the entire execution, not just a claim.
        # A live slow worker cannot overlap a replacement after lease expiry.
        connection = await psycopg.AsyncConnection.connect(
            settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://'), autocommit=True,
            keepalives=1, keepalives_idle=5, keepalives_interval=5, keepalives_count=3)
        locked = False
        keep_connection = False
        try:
            cursor = await connection.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0))', (str(job_id),))
            locked = (await cursor.fetchone())[0]
            if not locked:
                continue
            async with AsyncSessionLocal() as db, db.begin():
                job = (await db.execute(select(GenerationJob).where(GenerationJob.id == job_id, eligible())
                                        .with_for_update())).scalar_one_or_none()
                if not job:
                    continue
                if job.cancel_requested:
                    job.status = 'cancelled'
                    job.lease_owner, job.lease_expires_at = None, None
                    await db.execute(update(LLMCall).where(LLMCall.job_id == job.id, LLMCall.status == 'reserved').values(status='unresolved'))
                    thread = await db.get(Thread, job.id)
                    thread.status = ThreadStatus.FAILED
                    db.add(JobEvent(job_id=job.id, event='status', payload={'status': 'cancelled'}))
                    continue
                await db.execute(update(LLMCall).where(LLMCall.job_id == job.id, LLMCall.status == 'reserved').values(status='unresolved'))
                owner = uuid.uuid4()
                job.status, job.lease_owner, job.lease_expires_at = 'running', owner, utcnow() + timedelta(seconds=30)
                job.attempts += 1
                job.error = None
                db.add(JobEvent(job_id=job.id, event='status', payload={'status': 'running'}))
            keep_connection = True
            return job_id, owner, connection
        finally:
            # Returned claims retain their dedicated connection until execution ends.
            if not keep_connection:
                await connection.close()
    return None


async def write_event(job_id, owner, event, payload):
    async with AsyncSessionLocal() as db, db.begin():
        job = (await db.execute(select(GenerationJob).where(GenerationJob.id == job_id).with_for_update())).scalar_one()
        if job.lease_owner != owner or job.status != 'running' or job.cancel_requested:
            raise asyncio.CancelledError()
        if event == 'step_start':
            job.active_step = payload['step']
        job.updated_at = utcnow()
        db.add(JobEvent(job_id=job_id, event=event, payload=payload))


async def heartbeat(job_id, owner, task, lock_connection):
    while True:
        await asyncio.sleep(2)
        try:
            await asyncio.wait_for(lock_connection.execute('SELECT 1'), timeout=5)
            async with AsyncSessionLocal() as db, db.begin():
                job = await db.get(GenerationJob, job_id, with_for_update=True)
                if not job or job.lease_owner != owner or job.cancel_requested or job.status != 'running':
                    task.cancel()
                    return
                job.lease_expires_at = utcnow() + timedelta(seconds=30)
        except Exception:
            # Stop generation when its ownership/cancellation state cannot be checked.
            task.cancel()
            return


async def stop_job(job_id, owner, status, error=None):
    async with AsyncSessionLocal() as db, db.begin():
        job = await db.get(GenerationJob, job_id, with_for_update=True)
        if not job or job.lease_owner != owner:
            return
        job.status = 'cancelled' if job.cancel_requested else status
        job.error = error
        job.lease_owner, job.lease_expires_at = None, None
        job.updated_at = utcnow()
        await db.execute(update(LLMCall).where(LLMCall.job_id == job_id, LLMCall.status == 'reserved').values(status='unresolved'))
        thread = await db.get(Thread, job_id)
        thread.status = ThreadStatus.RUNNING if job.status == 'queued' else ThreadStatus.FAILED
        db.add(JobEvent(job_id=job_id, event='status', payload={'status': job.status, 'error': error}))


async def finish_job(job_id, owner, values, outline=None):
    async with AsyncSessionLocal() as db, db.begin():
        job = await db.get(GenerationJob, job_id, with_for_update=True)
        if job.lease_owner != owner or job.cancel_requested:
            raise asyncio.CancelledError()
        job.lease_owner, job.lease_expires_at = None, None
        job.updated_at = utcnow()
        thread = await db.get(Thread, job_id)
        if outline is not None:
            job.status, job.outline, job.resume_payload = 'awaiting_approval', jsonable_encoder(outline), None
            db.add(JobEvent(job_id=job_id, event='interrupt', payload={'payload': job.outline}))
            return
        content = values.get('final_content')
        if not content:
            raise RuntimeError('Workflow stopped without an article or an approval request')
        article = (await db.execute(select(Article).where(Article.job_id == job_id))).scalar_one_or_none()
        if article is None:
            article = Article(user_id=job.user_id, job_id=job_id, title=job.input_state['topic'], content=content, version=1)
            db.add(article)
            await db.flush()
            add_revision(db, article, 'generated')
        # Recovery never overwrites a draft that the user has already edited.
        job.status = 'completed'
        thread.status = ThreadStatus.COMPLETED
        db.add(JobEvent(job_id=job_id, event='end', payload={'output': {'final_content': article.content}, 'article_id': str(article.id)}))


async def execute_claim(claim, graph):
    job_id, owner, connection = claim
    token = None
    pulse = None
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(GenerationJob, job_id)
            context = MeterContext(job.user_id, job_id, owner)
            initial, resume = job.input_state, job.resume_payload
        token = current_meter.set(context)
        pulse = asyncio.create_task(heartbeat(job_id, owner, asyncio.current_task(), connection))
        config = {'configurable': {'thread_id': str(job_id)}, 'recursion_limit': 250}
        snapshot = await graph.aget_state(config)
        interrupted = any(task.interrupts for task in snapshot.tasks)
        if interrupted and not resume:
            await finish_job(job_id, owner, snapshot.values, snapshot.values.get('outline', []))
            return
        if snapshot.values and not snapshot.next and snapshot.values.get('final_content'):
            await finish_job(job_id, owner, snapshot.values)
            return
        value = Command(resume=resume) if interrupted and resume else (None if snapshot.values else initial)
        async for event in graph.astream_events(value, config, version='v1'):
            if context.stop_reason:
                raise BudgetExceeded(context.stop_reason)
            name, kind = event['name'], event['event']
            if name not in STEPS:
                continue
            if kind == 'on_chain_start':
                await write_event(job_id, owner, 'step_start', {'step': name, 'status': 'running'})
            elif kind == 'on_chain_end':
                output = jsonable_encoder(event['data'].get('output'))
                if len(json.dumps(output, default=str)) > 100000:
                    output = {'summary': 'Step output saved in the workflow checkpoint'}
                await write_event(job_id, owner, 'step_complete', {'step': name, 'status': 'completed', 'output': output})
        if context.stop_reason:
            raise BudgetExceeded(context.stop_reason)
        snapshot = await graph.aget_state(config)
        interrupted = any(task.interrupts for task in snapshot.tasks)
        if interrupted:
            await finish_job(job_id, owner, snapshot.values, snapshot.values.get('outline', []))
        elif snapshot.next:
            raise RuntimeError('Workflow has unfinished steps')
        else:
            await finish_job(job_id, owner, snapshot.values)
    except asyncio.CancelledError:
        await asyncio.shield(stop_job(job_id, owner, 'queued', 'Worker stopped; saved progress will resume'))
    except BudgetExceeded as exc:
        await stop_job(job_id, owner, 'budget_exceeded', str(exc))
    except Exception as exc:
        log.exception('Generation job %s failed', job_id)
        await stop_job(job_id, owner, 'failed', str(exc)[:1000])
    finally:
        if pulse:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
        if token is not None:
            current_meter.reset(token)
        await connection.close()  # releases the per-job advisory lock


async def main():
    worker_health.clear()
    runner = AgentRunner()
    await runner.setup()
    tasks = set()
    try:
        while True:
            worker_health.mark_alive()
            done = {task for task in tasks if task.done()}
            if done:
                for result in await asyncio.gather(*done, return_exceptions=True):
                    if isinstance(result, BaseException):
                        log.error('Worker task ended unexpectedly: %s', result)
                tasks -= done
            if len(tasks) < max(1, min(8, settings.WORKER_CONCURRENCY)):
                try:
                    claim = await claim_job()
                except Exception:
                    log.exception('Could not claim a job; retrying')
                    await asyncio.sleep(3)
                    continue
                if claim:
                    tasks.add(asyncio.create_task(execute_claim(claim, runner.graph)))
                    continue
            await asyncio.sleep(1)
    finally:
        worker_health.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.shutdown()


async def serve():
    task = asyncio.create_task(main())
    loop = asyncio.get_running_loop()
    installed = False
    try:
        # Docker sends SIGTERM. Let main cancel claims and release leases before
        # exiting instead of waiting for crash recovery on every deployment.
        try:
            loop.add_signal_handler(signal.SIGTERM, task.cancel)
            installed = True
        except NotImplementedError:  # Windows uses its normal console shutdown.
            pass
        await task
    except asyncio.CancelledError:
        pass
    finally:
        if installed:
            loop.remove_signal_handler(signal.SIGTERM)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
