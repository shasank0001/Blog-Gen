import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from app.services import metering
from app.core.config import settings


class FakeMeteredModel(BaseChatModel):
    calls: int = 0
    @property
    def _llm_type(self):
        return 'test-model'
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='test',
            usage_metadata={'input_tokens': 20, 'output_tokens': 10, 'total_tokens': 30}))])


def test_callback_blocks_provider_before_request(monkeypatch):
    reserve = AsyncMock(side_effect=metering.BudgetExceeded('Limit reached'))
    monkeypatch.setattr(metering, 'reserve', reserve)
    monkeypatch.setattr(metering, 'reconcile', AsyncMock())
    context = metering.MeterContext(uuid.uuid4())
    model = FakeMeteredModel(callbacks=[metering.UsageMeter(context, 'openai', 'test', (Decimal(1), Decimal(2), 512))])
    with pytest.raises(metering.BudgetExceeded):
        asyncio.run(model.ainvoke([HumanMessage(content='test')]))
    assert model.calls == 0


def test_callback_records_reported_usage(monkeypatch):
    reserve, reconcile = AsyncMock(), AsyncMock()
    monkeypatch.setattr(metering, 'reserve', reserve)
    monkeypatch.setattr(metering, 'reconcile', reconcile)
    model = FakeMeteredModel(callbacks=[metering.UsageMeter(metering.MeterContext(uuid.uuid4()), 'openai', 'test', (Decimal(1), Decimal(2), 512))])
    asyncio.run(model.ainvoke([HumanMessage(content='test')]))
    assert model.calls == 1
    assert reserve.await_args.args[4] > 4096
    assert reserve.await_args.args[5] == 512
    assert reconcile.await_args.args[2] == (20, 10)


@pytest.mark.parametrize('value', ['[]', '{"bad":{}}', '{"openai:test":{"input_per_million":"NaN","output_per_million":"2"}}',
                                   '{"openai:test":{"input_per_million":"-1","output_per_million":"2"}}'])
def test_invalid_prices_fail_closed(monkeypatch, value):
    monkeypatch.setattr(settings, 'LLM_PRICING_JSON', value)
    with pytest.raises(ValueError):
        metering.prices()


def test_unknown_prices_are_not_treated_as_free(monkeypatch):
    monkeypatch.setattr(settings, 'LLM_PRICING_JSON', '{}')
    with pytest.raises(ValueError):
        metering.model_price('openai', 'unknown')
    assert metering.model_price('ollama', 'local')[:2] == (Decimal(0), Decimal(0))


def test_cost_rounds_up_instead_of_losing_small_charges():
    assert metering.token_cost(1, 0, Decimal('0.001'), Decimal(0)) == Decimal('0.00000001')


def test_invalid_usage_does_not_release_the_reservation():
    assert metering.valid_usage(-1, 10) is None
    assert metering.valid_usage(True, 10) is None
    assert metering.valid_usage(1.5, 10) is None


def test_worker_releases_its_lock_when_initial_database_load_fails(monkeypatch):
    from app import worker
    from unittest.mock import MagicMock
    session = MagicMock()
    session.__aenter__ = AsyncMock(side_effect=RuntimeError('Database unavailable'))
    monkeypatch.setattr(worker, 'AsyncSessionLocal', lambda: session)
    monkeypatch.setattr(worker, 'stop_job', AsyncMock())
    connection = SimpleNamespace(close=AsyncMock())
    asyncio.run(worker.execute_claim((uuid.uuid4(), uuid.uuid4(), connection), None))
    connection.close.assert_awaited_once()
