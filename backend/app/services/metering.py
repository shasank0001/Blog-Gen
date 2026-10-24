"""Reserve estimated model charges before calls; retain uncertain reservations."""
import json
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING

from langchain_core.callbacks import AsyncCallbackHandler
from sqlalchemy import select, func, case
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.workspace_models import SpendingAccount, LLMCall, GenerationJob

MILLION = Decimal(1_000_000)
PRECISION = Decimal('0.00000001')


class BudgetExceeded(Exception):
    pass


@dataclass
class MeterContext:
    user_id: uuid.UUID
    job_id: uuid.UUID | None = None
    lease_owner: uuid.UUID | None = None
    stop_reason: str | None = None


current_meter: ContextVar[MeterContext | None] = ContextVar('generation_meter', default=None)


def prices():
    try:
        values = json.loads(settings.LLM_PRICING_JSON)
        if not isinstance(values, dict):
            raise ValueError('must be an object')
        result = {}
        for key, raw in values.items():
            if ':' not in key or key.split(':', 1)[0] not in {'openai', 'anthropic', 'google'} or not key.split(':', 1)[1]:
                raise ValueError('invalid provider/model key')
            input_rate = Decimal(str(raw['input_per_million']))
            output_rate = Decimal(str(raw['output_per_million']))
            maximum = int(raw.get('max_output_tokens', 4096))
            if (not input_rate.is_finite() or not output_rate.is_finite()
                    or input_rate < 0 or output_rate < 0 or not 256 <= maximum <= 32768):
                raise ValueError('invalid model price or output limit')
            result[key] = (input_rate, output_rate, maximum)
        return result
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        raise ValueError('LLM_PRICING_JSON contains invalid price configuration') from exc


def model_price(provider, model):
    if provider == 'ollama':
        return Decimal(0), Decimal(0), 4096
    result = prices().get(f'{provider}:{model}')
    if result is None:
        raise ValueError(f'No price is configured for {provider}/{model}. Ask an administrator to configure it or use local processing.')
    return result


def token_cost(input_tokens, output_tokens, input_rate, output_rate):
    return ((Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / MILLION).quantize(
        PRECISION, rounding=ROUND_CEILING)


def month_start():
    return datetime.now(timezone.utc).replace(tzinfo=None, day=1, hour=0, minute=0, second=0, microsecond=0)


committed_amount = case((LLMCall.status == 'recorded', LLMCall.estimated_usd), else_=LLMCall.reserved_usd)


async def account_for_update(db, user_id):
    await db.execute(insert(SpendingAccount).values(
        user_id=user_id, monthly_limit_usd=Decimal(str(settings.DEFAULT_MONTHLY_LIMIT_USD))
    ).on_conflict_do_nothing(index_elements=['user_id']))
    return (await db.execute(select(SpendingAccount).where(
        SpendingAccount.user_id == user_id).with_for_update())).scalar_one()


async def committed(db, user_id, job_id=None):
    statement = select(func.coalesce(func.sum(committed_amount), 0)).where(LLMCall.user_id == user_id)
    if job_id is None:
        statement = statement.where(LLMCall.created_at >= month_start())
    else:
        statement = statement.where(LLMCall.job_id == job_id)
    return (await db.execute(statement)).scalar_one()


async def reserve(context, call_id, provider, model, input_bound, output_bound, rates):
    if context.stop_reason:
        raise BudgetExceeded(context.stop_reason)
    input_rate, output_rate = rates
    amount = token_cost(input_bound, output_bound, input_rate, output_rate)
    async with AsyncSessionLocal() as db, db.begin():
        account = await account_for_update(db, context.user_id)
        if context.job_id:
            job = (await db.execute(select(GenerationJob).where(
                GenerationJob.id == context.job_id, GenerationJob.user_id == context.user_id
            ).with_for_update())).scalar_one()
            if (job.cancel_requested or job.status != 'running' or job.lease_owner != context.lease_owner):
                context.stop_reason = 'Generation was cancelled or the worker lease changed'
                raise BudgetExceeded(context.stop_reason)
            if await committed(db, context.user_id, context.job_id) + amount > job.cost_limit_usd:
                context.stop_reason = 'The next model call would exceed this run’s spending limit'
                raise BudgetExceeded(context.stop_reason)
        if await committed(db, context.user_id) + amount > account.monthly_limit_usd:
            context.stop_reason = 'The next model call would exceed your monthly spending limit'
            raise BudgetExceeded(context.stop_reason)
        db.add(LLMCall(id=call_id, user_id=context.user_id, job_id=context.job_id,
                       provider=provider, model=model, input_rate=input_rate, output_rate=output_rate,
                       reserved_usd=amount, status='reserved'))


async def reconcile(context, call_id, usage=None):
    async with AsyncSessionLocal() as db, db.begin():
        await account_for_update(db, context.user_id)
        call = await db.get(LLMCall, call_id, with_for_update=True)
        if not call or call.status == 'recorded':
            return
        if usage is None:
            call.status = 'unresolved'
            return
        input_tokens, output_tokens = usage
        call.input_tokens = input_tokens
        call.output_tokens = output_tokens
        call.estimated_usd = token_cost(input_tokens, output_tokens, call.input_rate, call.output_rate)
        call.status = 'recorded'
        if call.estimated_usd > call.reserved_usd:
            context.stop_reason = 'Reported usage exceeded the reserved estimate; review the run before continuing'


def valid_usage(input_tokens, output_tokens):
    if type(input_tokens) is int and type(output_tokens) is int and min(input_tokens, output_tokens) >= 0:
        return input_tokens, output_tokens
    return None


def extract_usage(response):
    for group in response.generations:
        for generation in group:
            message = getattr(generation, 'message', None)
            usage = getattr(message, 'usage_metadata', None)
            if usage and 'input_tokens' in usage and 'output_tokens' in usage:
                return valid_usage(usage['input_tokens'], usage['output_tokens'])
    raw = response.llm_output or {}
    usage = raw.get('token_usage') or raw.get('usage') or {}
    if 'prompt_tokens' in usage and 'completion_tokens' in usage:
        return valid_usage(usage['prompt_tokens'], usage['completion_tokens'])
    return None


class UsageMeter(AsyncCallbackHandler):
    raise_error = True

    def __init__(self, context, provider, model, price):
        self.context = context
        self.provider = provider
        self.model = model
        self.price = price

    async def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        # One UTF-8 byte per possible token plus protocol/tool overhead is a
        # deliberately conservative reservation, not a provider token estimate.
        payload = {'messages': [[message.model_dump() for message in group] for group in messages],
                   'params': kwargs.get('invocation_params', {})}
        input_bound = len(json.dumps(payload, default=str, ensure_ascii=False).encode('utf-8')) + 4096
        await reserve(self.context, run_id, self.provider, self.model, input_bound, self.price[2], self.price[:2])

    async def on_llm_end(self, response, *, run_id, **kwargs):
        usage = extract_usage(response)
        await reconcile(self.context, run_id, usage)
        if usage is None and (self.price[0] or self.price[1]):
            self.context.stop_reason = 'The provider returned no token usage. Its reservation is held; review usage before resuming.'

    async def on_llm_error(self, error, *, run_id, **kwargs):
        # An interrupted/failed request can still incur provider charges.
        await reconcile(self.context, run_id)
