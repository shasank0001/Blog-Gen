from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.core.config import settings
from app.core.database import get_db
from app.core.models import User
from app.core.workspace_models import LLMCall, SpendingAccount
from app.schemas_workspace import UpdateSpendingLimit
from app.services.metering import month_start, committed, account_for_update, prices
from app.services.workspace import stamp

router = APIRouter()


@router.get('/models')
async def available_models(user: User = Depends(deps.get_current_user)):
    try:
        configured = prices()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {'models': [dict(provider=key.split(':', 1)[0], model=key.split(':', 1)[1], input_per_million=str(rate[0]),
                            output_per_million=str(rate[1]), max_output_tokens=rate[2])
                       for key, rate in configured.items()] + [dict(provider='ollama', model=settings.OLLAMA_MODEL,
                           input_per_million='0', output_per_million='0', max_output_tokens=4096)]}


@router.get('')
async def dashboard(db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    account = await account_for_update(db, user.id)
    await db.commit()
    period = month_start()
    measured = case((LLMCall.status == 'recorded', LLMCall.estimated_usd), else_=0)
    held = case((LLMCall.status != 'recorded', LLMCall.reserved_usd), else_=0)
    rows = (await db.execute(select(LLMCall.provider, LLMCall.model, func.sum(measured), func.sum(held),
                                     func.coalesce(func.sum(LLMCall.input_tokens), 0),
                                     func.coalesce(func.sum(LLMCall.output_tokens), 0), func.count(LLMCall.id))
                            .where(LLMCall.user_id == user.id, LLMCall.created_at >= period)
                            .group_by(LLMCall.provider, LLMCall.model))).all()
    spent = sum((row[2] for row in rows), start=0)
    reserved = sum((row[3] for row in rows), start=0)
    return dict(period_start=stamp(period), monthly_limit_usd=str(account.monthly_limit_usd),
                estimated_usd=str(spent), held_usd=str(reserved), committed_usd=str(spent + reserved),
                remaining_usd=str(max(0, account.monthly_limit_usd - spent - reserved)),
                models=[dict(provider=row[0], model=row[1], estimated_usd=str(row[2]), held_usd=str(row[3]),
                             input_tokens=row[4], output_tokens=row[5], calls=row[6]) for row in rows])


@router.patch('/limit')
async def update_limit(body: UpdateSpendingLimit, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    account = await account_for_update(db, user.id)
    if body.monthly_limit_usd < await committed(db, user.id):
        raise HTTPException(409, 'The monthly limit cannot be below spending and held reservations for this month')
    account.monthly_limit_usd = body.monthly_limit_usd
    await db.commit()
    return {'monthly_limit_usd': str(account.monthly_limit_usd)}


@router.get('/calls')
async def calls(skip: int = 0, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    if skip < 0:
        raise HTTPException(422, 'Offset must be nonnegative')
    rows = (await db.execute(select(LLMCall).where(LLMCall.user_id == user.id)
                            .order_by(LLMCall.created_at.desc(), LLMCall.id).offset(skip).limit(21))).scalars().all()
    return {'items': [dict(id=str(row.id), job_id=str(row.job_id) if row.job_id else None, provider=row.provider,
                          model=row.model, input_tokens=row.input_tokens, output_tokens=row.output_tokens,
                          estimated_usd=str(row.estimated_usd) if row.estimated_usd is not None else None,
                          reserved_usd=str(row.reserved_usd), status=row.status, created_at=stamp(row.created_at))
                      for row in rows[:20]], 'has_more': len(rows) > 20}
