import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import agent, deps
from app.core.config import Settings
from app.core.database import get_db
from app.core.models import Thread, User
from app.services import safe_fetch


def test_state_requires_authentication(monkeypatch):
    graph = SimpleNamespace(aget_state=AsyncMock())
    monkeypatch.setattr(agent.runner, 'graph', graph)
    app = FastAPI()
    app.include_router(agent.router)
    response = TestClient(app).get(f'/state/{uuid.uuid4()}')
    assert response.status_code == 401
    graph.aget_state.assert_not_called()


@pytest.mark.parametrize('owned', [False, True])
def test_state_checks_owner_before_reading_checkpoint(monkeypatch, owned):
    user = User(id=uuid.uuid4(), email='owner@example.com', is_active=True)
    thread_id = uuid.uuid4()
    graph = SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(
        values={'final_content': 'private article'}, next=())))
    monkeypatch.setattr(agent.runner, 'graph', graph)
    db = AsyncMock()
    db.get.return_value = None
    result = MagicMock()
    result.scalars.return_value.first.return_value = Thread(id=thread_id) if owned else None
    db.execute.return_value = result
    app = FastAPI()
    app.include_router(agent.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[deps.get_current_user] = lambda: user
    response = TestClient(app).get(f'/state/{thread_id}')
    statement = db.execute.call_args.args[0].compile()
    assert user.id in statement.params.values()
    assert thread_id in statement.params.values()
    if owned:
        assert response.status_code == 200
        assert response.json()['values']['final_content'] == 'private article'
        graph.aget_state.assert_awaited_once_with({'configurable': {'thread_id': str(thread_id)}})
    else:
        assert response.status_code == 404
        graph.aget_state.assert_not_called()


@pytest.mark.parametrize('secret', ['', 'short', 'replace-with-strong-secret', 'your-secret-key-change-in-production'])
def test_weak_secrets_are_rejected(secret):
    with pytest.raises(ValidationError, match='unique random secret'):
        Settings(_env_file=None, SECRET_KEY=secret)


def test_random_secret_is_accepted():
    import secrets
    value = secrets.token_urlsafe(48)
    assert Settings(_env_file=None, SECRET_KEY=value).SECRET_KEY == value


def dns_result(address):
    return [(2, 1, 6, '', (address, 443))]


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1',
                                     '::1', '::ffff:127.0.0.1', '224.0.0.1'])
def test_private_destinations_are_blocked(monkeypatch, address):
    monkeypatch.setattr(safe_fetch.socket, 'getaddrinfo', lambda *a, **kw: dns_result(address))
    with pytest.raises(safe_fetch.UnsafeURL):
        asyncio.run(safe_fetch.resolve_public_url('https://example.com/sitemap.xml'))


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://user:pass@example.com', 'http://[fe80::1%eth0]/'])
def test_non_public_url_forms_are_rejected(url):
    with pytest.raises(safe_fetch.UnsafeURL):
        asyncio.run(safe_fetch.resolve_public_url(url))


def test_dns_is_pinned_and_private_redirect_is_blocked(monkeypatch):
    calls = []
    resolutions = []
    def resolve(host, *args, **kwargs):
        resolutions.append(host)
        return dns_result('127.0.0.1' if host == 'localhost' else '93.184.216.34')
    monkeypatch.setattr(safe_fetch.socket, 'getaddrinfo', resolve)
    def handle(request):
        calls.append(request)
        return httpx.Response(302, headers={'location': 'http://localhost/private'}, stream=httpx.ByteStream(b''))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(safe_fetch.httpx, 'AsyncClient',
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(safe_fetch.UnsafeURL):
        asyncio.run(safe_fetch.fetch_public_bytes('https://example.com/sitemap.xml'))
    assert len(calls) == 1
    assert calls[0].url.host == '93.184.216.34'
    assert calls[0].headers['host'] == 'example.com'
    assert calls[0].extensions['sni_hostname'] == 'example.com'
    assert resolutions == ['example.com', 'localhost']


def test_sitemap_response_has_byte_limit(monkeypatch):
    monkeypatch.setattr(safe_fetch.socket, 'getaddrinfo', lambda *a, **kw: dns_result('93.184.216.34'))
    def handle(request):
        return httpx.Response(200, stream=httpx.ByteStream(b'x' * (safe_fetch.MAX_RESPONSE_BYTES + 1)))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(safe_fetch.httpx, 'AsyncClient',
                        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(safe_fetch.UnsafeURL, match='size limit'):
        asyncio.run(safe_fetch.fetch_public_bytes('https://example.com/sitemap.xml'))


@pytest.mark.parametrize('sources,queries', [(['internal'], ['query']), ([], ['query']), (['web'], []), (['web'], ['query'])])
def test_deep_research_reaches_approval(monkeypatch, sources, queries):
    from app.agent import graph as module
    from langgraph.checkpoint.memory import MemorySaver
    visited = []
    def node(name, update=None):
        async def run(state):
            visited.append(name)
            return update or {}
        return run
    updates = {
        'generate_query_node': {'generated_queries': queries, 'research_loop_count': 1},
        'reflection_node': {'is_sufficient': True},
        'planner_node': {'outline': [{'id': 's1', 'title': 'Title', 'intent': 'Explain', 'source_ids': []}]},
    }
    for name in ['internal_indexer_node', 'style_analyst_node', 'researcher_node', 'planner_node',
                 'writer_node', 'critic_node', 'visuals_node', 'publisher_node', 'generate_query_node',
                 'web_research_node', 'social_research_node', 'academic_research_node',
                 'reflection_node', 'finalize_answer_node']:
        monkeypatch.setattr(module, name, node(name, updates.get(name)))
    async def run():
        graph = module.build_graph().compile(checkpointer=MemorySaver())
        config = {'configurable': {'thread_id': str(uuid.uuid4())}}
        await graph.ainvoke({'topic': 'test', 'deep_research_mode': True, 'research_sources': sources}, config)
        snapshot = await graph.aget_state(config)
        assert snapshot.next == ('human_approval',)
        assert any(task.interrupts for task in snapshot.tasks)
    asyncio.run(run())
    assert 'finalize_answer_node' in visited
    assert 'planner_node' in visited


def test_publisher_preserves_source_ids():
    from app.agent.nodes.publisher import publisher_node
    output = publisher_node({'topic': 'Test', 'outline': [{'id': 's1', 'title': 'Title'}],
                             'draft_sections': {'s1': 'Second [web_2]. First [web_1].'},
                             'research_data': [{'source_id': 'web_1', 'title': 'First', 'url': 'https://first.example'},
                                               {'source_id': 'web_2', 'title': 'Second', 'url': 'https://second.example'}]})
    assert '- [web_1] [First](https://first.example)' in output['final_content']
    assert '- [web_2] [Second](https://second.example)' in output['final_content']


def test_legacy_generation_cannot_bypass_durable_jobs(monkeypatch):
    user = User(id=uuid.uuid4(), email='owner@example.com', is_active=True)
    graph = SimpleNamespace(astream_events=AsyncMock())
    monkeypatch.setattr(agent.runner, 'graph', graph)
    app = FastAPI()
    app.include_router(agent.router)
    app.dependency_overrides[deps.get_current_user] = lambda: user
    response = TestClient(app).post('/resume', json={'thread_id': str(uuid.uuid4()), 'approved_outline': []})
    assert response.status_code == 410
    graph.astream_events.assert_not_called()


def test_public_sitemap_can_be_fetched(monkeypatch):
    monkeypatch.setattr(safe_fetch.socket, 'getaddrinfo', lambda *a, **kw: dns_result('93.184.216.34'))
    content = b'<urlset><url><loc>https://example.com/post</loc></url></urlset>'
    original_client = httpx.AsyncClient
    monkeypatch.setattr(safe_fetch.httpx, 'AsyncClient', lambda **kwargs: original_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(content))), **kwargs))
    assert asyncio.run(safe_fetch.fetch_public_bytes('https://example.com/sitemap.xml')) == content


def test_gzip_sitemap_decompression_is_bounded(monkeypatch):
    import gzip
    from app.agent.nodes import internal_indexer
    monkeypatch.setattr(internal_indexer, 'fetch_public_bytes', AsyncMock(
        return_value=gzip.compress(b'x' * (safe_fetch.MAX_RESPONSE_BYTES + 1))))
    assert asyncio.run(internal_indexer.fetch_url_content('https://example.com/sitemap.xml.gz')) is None


def test_setup_generates_secret_without_overwriting_custom_value(tmp_path):
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    script = tmp_path / 'generate_secret.py'
    shutil.copy(Path(__file__).parents[1] / 'generate_secret.py', script)
    env = tmp_path / '.env'
    env.write_text('SECRET_KEY="replace-with-strong-secret"\nOPENAI_API_KEY="unchanged"\n')
    subprocess.run([sys.executable, str(script)], check=True)
    first = env.read_text()
    assert 'replace-with-strong-secret' not in first
    assert 'OPENAI_API_KEY="unchanged"' in first
    subprocess.run([sys.executable, str(script)], check=True)
    assert env.read_text() == first
