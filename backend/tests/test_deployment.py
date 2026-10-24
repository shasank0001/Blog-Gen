import importlib.util
import os
from pathlib import Path
import time
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.api import health
from app.core.config import settings
from app.core.database import get_db
from app import worker_health, deployment_check
from app.services.firecrawl_service import FirecrawlService


def test_readiness_requires_workflow_and_database(monkeypatch):
    client = TestClient(app)
    check = AsyncMock()
    monkeypatch.setattr(health, 'check_database', check)
    monkeypatch.setattr(health.runner, 'graph', None)
    assert client.get('/health/live').status_code == 200
    assert client.get('/health/ready').status_code == 503
    check.assert_not_awaited()
    monkeypatch.setattr(health.runner, 'graph', object())
    assert client.get('/health/ready').json() == {'status': 'ready'}
    check.side_effect = RuntimeError('private-connection-credentials')
    response = client.get('/health/ready')
    assert response.status_code == 503
    assert 'private' not in response.text


def test_closed_registration_does_not_write_to_database(monkeypatch):
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(settings, 'ALLOW_REGISTRATION', False)
    client = TestClient(app)
    assert client.get('/api/v1/auth/config').json() == {'allow_registration': False}
    response = client.post('/api/v1/auth/register', json={'email': 'closed@example.com', 'password': 'test-password-123'})
    assert response.status_code == 403
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_worker_probe_detects_missing_stale_and_cleared_heartbeat(tmp_path, monkeypatch):
    path = tmp_path / 'worker-health'
    monkeypatch.setattr(worker_health, 'HEARTBEAT_FILE', path)
    assert not worker_health.healthy()
    worker_health.mark_alive()
    assert worker_health.healthy()
    old = time.time() - 60
    os.utime(path, (old, old))
    assert not worker_health.healthy()
    worker_health.clear()
    assert not path.exists()


def test_unconfigured_firecrawl_is_lazy(monkeypatch):
    monkeypatch.setattr(settings, 'FIRECRAWL_API_KEY', '')
    service = FirecrawlService()
    assert service._app is None
    with pytest.raises(ValueError, match='Configure FIRECRAWL_API_KEY'):
        service.scrape('https://example.com')


def test_preflight_omits_invalid_secret_values(monkeypatch, capsys):
    monkeypatch.setenv('POSTGRES_PASSWORD', 'secret-that-must-not-appear')
    assert deployment_check.main() == 1
    captured = capsys.readouterr()
    assert 'POSTGRES_PASSWORD' in captured.err
    assert 'secret-that-must-not-appear' not in captured.err


def test_initializer_is_private_unique_and_never_overwrites(tmp_path):
    module_file = Path(__file__).resolve().parents[2] / 'scripts/init_deploy.py'
    spec = importlib.util.spec_from_file_location('init_deploy', module_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    template = tmp_path / 'example'
    template.write_text('POSTGRES_PASSWORD=GENERATE_DATABASE_PASSWORD\nSECRET_KEY=GENERATE_SIGNING_SECRET\n')
    first, second = tmp_path / 'one', tmp_path / 'two'
    module.initialize(template, first)
    module.initialize(template, second)
    assert first.read_text() != second.read_text()
    assert 'GENERATE_' not in first.read_text()
    assert first.stat().st_mode & 0o777 == 0o600
    before = first.read_text()
    with pytest.raises(FileExistsError):
        module.initialize(template, first)
    assert first.read_text() == before
