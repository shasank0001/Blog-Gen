from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.core.database import get_db
from app.api import deps
from app.core.models import User, Thread, ThreadStatus
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter()

class ThreadResponse(BaseModel):
    id: uuid.UUID
    topic: str
    status: ThreadStatus
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

@router.get("/", response_model=List[ThreadResponse])
async def list_threads(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    stmt = select(Thread).where(Thread.user_id == current_user.id).order_by(desc(Thread.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    threads = result.scalars().all()
    return threads

@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    stmt = select(Thread).where(Thread.id == thread_id, Thread.user_id == current_user.id)
    result = await db.execute(stmt)
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread
