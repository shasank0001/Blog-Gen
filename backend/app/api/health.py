"""Readiness checks are local and never call paid external providers."""
import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services.graph_runner import runner

router = APIRouter()


@router.get('/health/live')
async def live():
    return {'status': 'ok'}


async def check_database():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SELECT 1 FROM generation_jobs LIMIT 1'))


@router.get('/health/ready')
async def ready():
    if runner.graph is None:
        return JSONResponse({'status': 'not_ready'}, status_code=503)
    try:
        await asyncio.wait_for(check_database(), timeout=3)
    except Exception:
        return JSONResponse({'status': 'not_ready'}, status_code=503)
    return {'status': 'ready'}
