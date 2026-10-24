"""Requires BLOG_GEN_TEST_DATABASE_URL pointing to a migrated disposable PostgreSQL DB."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
import os
from types import SimpleNamespace
import uuid
import httpx
import pytest
from fastapi import Request
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.api import deps, jobs
from app.core.database import get_db
from app.core.config import settings
from app.core.models import User, Thread
from app.core.workspace_models import GenerationJob, SpendingAccount, LLMCall, utcnow
from app.services import metering
from app.services.graph_runner import AgentRunner
from app import worker

DATABASE = os.getenv('BLOG_GEN_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DATABASE, reason='Requires disposable migrated PostgreSQL')

@asynccontextmanager
async def environment(monkeypatch):
    engine = create_async_engine(DATABASE)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = [uuid.uuid4(), uuid.uuid4()]
    async with sessions() as db, db.begin():
        for identifier in ids:
            db.add(User(id=identifier, email=f'{identifier}@example.com', hashed_password='test-only'))
    async def database():
        async with sessions() as db:
            yield db
    async def identity(request: Request):
        return SimpleNamespace(id=uuid.UUID(request.headers.get('x-test-user', str(ids[0]))))
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[deps.get_current_user] = identity
    for module in [jobs, worker, metering]:
        monkeypatch.setattr(module, 'AsyncSessionLocal', sessions)
    monkeypatch.setattr(settings, 'DATABASE_URL', DATABASE)
    monkeypatch.setattr(settings, 'LLM_PRICING_JSON', '{"openai:test-model":{"input_per_million":"1","output_per_million":"2","max_output_tokens":512}}')
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, sessions, ids
    finally:
        app.dependency_overrides.clear()
        async with sessions() as db, db.begin():
            await db.execute(delete(Thread).where(Thread.user_id.in_(ids)))
            await db.execute(delete(User).where(User.id.in_(ids)))
        await engine.dispose()

def payload(**extra):
    return {**dict(idempotency_key=str(uuid.uuid4()), topic='Integration article', use_local=True,
                   research_sources=[], cost_limit_usd='0.05'), **extra}

def test_job_idempotency_and_ownership(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            body = payload()
            a, b = await asyncio.gather(client.post('/api/v1/jobs', json=body), client.post('/api/v1/jobs', json=body))
            assert a.status_code == b.status_code == 201, (a.text, b.text)
            job_id = a.json()['id']
            assert b.json()['id'] == job_id
            assert (await client.post('/api/v1/jobs', json={**body, 'topic': 'Different'})).status_code == 409
            other = {'x-test-user': str(ids[1])}
            for method, path in [('get', ''), ('post', '/cancel'), ('post', '/resume'), ('get', '/events')]:
                assert (await client.request(method, f'/api/v1/jobs/{job_id}{path}', headers=other, json={} if method == 'post' else None)).status_code == 404
            assert (await client.get('/api/v1/jobs', headers=other)).json()['items'] == []
            assert (await client.get('/api/v1/threads/')).json() == []
            async with sessions() as db:
                assert (await db.execute(select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == ids[0]))).scalar_one() == 1
            assert (await client.post('/api/v1/jobs', json=payload(use_local=False, model_name='unknown'))).status_code == 400
    asyncio.run(run())


def test_operator_account_creation_with_registration_closed(monkeypatch):
    from app import manage
    from app.core.security import verify_password
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            monkeypatch.setattr(manage, 'AsyncSessionLocal', sessions)
            email = f'{ids[0]}-operator@example.com'
            try:
                await manage.create_user(email, 'test-operator-password')
                async with sessions() as db:
                    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
                    assert verify_password('test-operator-password', user.hashed_password)
                with pytest.raises(ValueError, match='already exists'):
                    await manage.create_user(email, 'other-test-password')
            finally:
                async with sessions() as db, db.begin():
                    await db.execute(delete(User).where(User.email == email))
    asyncio.run(run())

def test_autosave_conflicts_and_revision_restore(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            created = await client.post('/api/v1/articles', json={'title': 'Draft', 'content': ''})
            assert created.status_code == 201, created.text
            path = '/api/v1/articles/' + created.json()['id']
            body = {'title': 'Draft', 'content': 'First edit', 'expected_version': 1}
            assert (await client.patch(path, json=body)).json()['version'] == 2
            assert (await client.patch(path, json=body)).json()['version'] == 2
            responses = await asyncio.gather(*[client.patch(path, json={**body, 'content': text, 'expected_version': 2}) for text in ['Tab A', 'Tab B']])
            assert sorted(item.status_code for item in responses) == [200, 409]
            versions = (await client.get(path + '/revisions')).json()['items']
            assert len(versions) == 3
            original = versions[-1]['id']
            restored = await client.post(path + '/restore', json={'revision_id': original, 'expected_version': 3})
            assert restored.json()['version'] == 4 and restored.json()['content'] == ''
            assert len((await client.get(path + '/revisions')).json()['items']) == 4
            assert (await client.get(path + '/revisions/' + versions[0]['id'])).json()['content'] in ['Tab A', 'Tab B']
            for method, suffix, body in [('get', '', None), ('get', '/revisions', None), ('get', '/revisions/' + original, None),
                                          ('patch', '', {'title': 'Stolen', 'content': '', 'expected_version': 4}),
                                          ('post', '/restore', {'revision_id': original, 'expected_version': 4})]:
                assert (await client.request(method, path + suffix, headers={'x-test-user': str(ids[1])}, json=body)).status_code == 404
    asyncio.run(run())

def test_atomic_budget_reservations_and_reconciliation(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            created = (await client.post('/api/v1/jobs', json=payload(cost_limit_usd='0.005'))).json()
            job_id, owner = uuid.UUID(created['id']), uuid.uuid4()
            async with sessions() as db, db.begin():
                job = await db.get(GenerationJob, job_id)
                job.status, job.lease_owner = 'running', owner
            context = metering.MeterContext(ids[0], job_id, owner)
            async def hold():
                call_id = uuid.uuid4()
                try:
                    await metering.reserve(metering.MeterContext(ids[0], job_id, owner), call_id, 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
                    return call_id
                except metering.BudgetExceeded:
                    return None
            results = await asyncio.gather(hold(), hold())
            assert sum(item is not None for item in results) == 1
            await metering.reconcile(context, next(item for item in results if item), (10, 5))
            another = uuid.uuid4()
            await metering.reserve(context, another, 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
            await metering.reconcile(context, another)
            async with sessions() as db, db.begin():
                account = await db.get(SpendingAccount, ids[0])
                account.monthly_limit_usd = Decimal('0.004')
            second = (await client.post('/api/v1/jobs', json=payload())).json()
            other_job, other_owner = uuid.UUID(second['id']), uuid.uuid4()
            async with sessions() as db, db.begin():
                job = await db.get(GenerationJob, other_job)
                job.status, job.lease_owner = 'running', other_owner
            with pytest.raises(metering.BudgetExceeded, match='monthly'):
                await metering.reserve(metering.MeterContext(ids[0], other_job, other_owner), uuid.uuid4(), 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
            usage = (await client.get('/api/v1/usage')).json()
            assert Decimal(usage['estimated_usd']) == Decimal('0.00002')
            assert Decimal(usage['held_usd']) == Decimal('0.003')
            assert (await client.patch('/api/v1/usage/limit', json={'monthly_limit_usd': '0.001'})).status_code == 409
    asyncio.run(run())

def fake_graph(checkpointer, writing=None, started=None, charge=False):
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Command
    from app.agent.state import AgentState
    from app.agent.nodes.human_approval import human_approval_node
    from app.agent.nodes.publisher import publisher_node
    async def plan(state):
        return {'outline': [{'id': 's1', 'title': 'Section', 'intent': 'Explain', 'source_ids': []}]}
    async def write(state):
        if started: started.set()
        if writing: await writing.wait()
        if charge:
            context = metering.current_meter.get()
            call_id = uuid.uuid4()
            await metering.reserve(context, call_id, 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
            await metering.reconcile(context, call_id, (10, 5))
        return Command(update={'draft_sections': {'s1': 'Recovered draft content.'}}, goto='publisher')
    graph = StateGraph(AgentState)
    graph.add_node('planner', plan)
    graph.add_node('human_approval', human_approval_node)
    graph.add_node('writer', write)
    graph.add_node('publisher', publisher_node)
    graph.add_edge(START, 'planner')
    graph.add_edge('planner', 'human_approval')
    graph.add_edge('publisher', END)
    return graph.compile(checkpointer=checkpointer)

def test_worker_restart_approval_and_event_replay(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            job_id = (await client.post('/api/v1/jobs', json=payload())).json()['id']
            first = AgentRunner()
            await first.setup()
            await worker.execute_claim(await worker.claim_job(), fake_graph(first.checkpointer))
            paused = (await client.get('/api/v1/jobs/' + job_id)).json()
            assert paused['status'] == 'awaiting_approval', paused
            assert 'event: interrupt' in (await client.get(f'/api/v1/jobs/{job_id}/events')).text
            await first.shutdown()
            second = AgentRunner()
            await second.setup()
            try:
                approved = await client.post(f'/api/v1/jobs/{job_id}/resume', json={'approved_outline': paused['outline']})
                assert approved.status_code == 200, approved.text
                await worker.execute_claim(await worker.claim_job(), fake_graph(second.checkpointer))
                completed = (await client.get('/api/v1/jobs/' + job_id)).json()
                assert completed['status'] == 'completed', completed
                tail = await client.get(f'/api/v1/jobs/{job_id}/events?after={paused["last_event_id"]}')
                assert 'event: end' in tail.text and 'event: interrupt' not in tail.text
                draft = (await client.get('/api/v1/articles/' + completed['article_id'])).json()
                assert 'Recovered draft content.' in draft['content'] and draft['version'] == 1
                assert (await client.post(f'/api/v1/jobs/{job_id}/resume', json={})).status_code == 409
            finally:
                await second.shutdown()
    asyncio.run(run())

def test_worker_cancel_and_resume_checkpoint(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            job_id = (await client.post('/api/v1/jobs', json=payload())).json()['id']
            runner = AgentRunner()
            await runner.setup()
            task = None
            try:
                await worker.execute_claim(await worker.claim_job(), fake_graph(runner.checkpointer))
                job = (await client.get('/api/v1/jobs/' + job_id)).json()
                await client.post(f'/api/v1/jobs/{job_id}/resume', json={'approved_outline': job['outline']})
                started, waiting = asyncio.Event(), asyncio.Event()
                task = asyncio.create_task(worker.execute_claim(await worker.claim_job(), fake_graph(runner.checkpointer, waiting, started)))
                await asyncio.wait_for(started.wait(), 5)
                await client.post(f'/api/v1/jobs/{job_id}/cancel')
                await asyncio.wait_for(task, 5)
                assert (await client.get('/api/v1/jobs/' + job_id)).json()['status'] == 'cancelled'
                await client.post(f'/api/v1/jobs/{job_id}/resume', json={})
                await worker.execute_claim(await worker.claim_job(), fake_graph(runner.checkpointer))
                assert (await client.get('/api/v1/jobs/' + job_id)).json()['status'] == 'completed'
            finally:
                if task and not task.done():
                    task.cancel(); await asyncio.gather(task, return_exceptions=True)
                await runner.shutdown()
    asyncio.run(run())

def test_live_lock_prevents_duplicate_execution_and_expired_lease_recovers(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            job_id = (await client.post('/api/v1/jobs', json=payload())).json()['id']
            first = await worker.claim_job()
            assert first and str(first[0]) == job_id
            call_id = uuid.uuid4()
            await metering.reserve(metering.MeterContext(ids[0], first[0], first[1]), call_id, 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
            try:
                async with sessions() as db, db.begin():
                    job = await db.get(GenerationJob, first[0])
                    job.lease_expires_at = utcnow() - timedelta(seconds=1)
                assert await worker.claim_job() is None
            finally:
                await first[2].close()
            replacement = await worker.claim_job()
            assert replacement and replacement[0] == first[0] and replacement[1] != first[1]
            async with sessions() as db:
                assert (await db.get(LLMCall, call_id)).status == 'unresolved'
            second_call = uuid.uuid4()
            await metering.reserve(metering.MeterContext(ids[0], replacement[0], replacement[1]), second_call, 'openai', 'test-model', 1000, 1000, (Decimal(1), Decimal(2)))
            async with sessions() as db, db.begin():
                job = await db.get(GenerationJob, replacement[0])
                job.lease_expires_at = utcnow() - timedelta(seconds=1)
            await client.post(f'/api/v1/jobs/{job_id}/cancel')
            await replacement[2].close()
            assert await worker.claim_job() is None
            async with sessions() as db:
                assert (await db.get(LLMCall, second_call)).status == 'unresolved'
            assert (await client.get('/api/v1/jobs/' + job_id)).json()['status'] == 'cancelled'
    asyncio.run(run())


def test_worker_stops_for_budget_then_resumes_with_a_larger_limit(monkeypatch):
    async def run():
        async with environment(monkeypatch) as (client, sessions, ids):
            job_id = (await client.post('/api/v1/jobs', json=payload(cost_limit_usd='0.001'))).json()['id']
            runner = AgentRunner()
            await runner.setup()
            try:
                graph = fake_graph(runner.checkpointer, charge=True)
                await worker.execute_claim(await worker.claim_job(), graph)
                paused = (await client.get('/api/v1/jobs/' + job_id)).json()
                await client.post(f'/api/v1/jobs/{job_id}/resume', json={'approved_outline': paused['outline']})
                await worker.execute_claim(await worker.claim_job(), graph)
                assert (await client.get('/api/v1/jobs/' + job_id)).json()['status'] == 'budget_exceeded'
                assert (await client.post(f'/api/v1/jobs/{job_id}/resume', json={'cost_limit_usd': '0.05'})).status_code == 200
                await worker.execute_claim(await worker.claim_job(), graph)
                final = (await client.get('/api/v1/jobs/' + job_id)).json()
                assert final['status'] == 'completed'
                assert Decimal(final['committed_usd']) == Decimal('0.00002')
            finally:
                await runner.shutdown()
    asyncio.run(run())
