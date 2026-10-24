"""Persistent jobs, article revisions and conservative LLM cost accounting."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Column, String, Text, DateTime, ForeignKey, Integer, BigInteger,
                        Boolean, Numeric, UniqueConstraint, CheckConstraint)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GenerationJob(Base):
    __tablename__ = 'generation_jobs'
    __table_args__ = (
        UniqueConstraint('user_id', 'idempotency_key'),
        CheckConstraint('cost_limit_usd > 0'),
        CheckConstraint("status IN ('queued','running','awaiting_approval','completed','failed','cancelled','budget_exceeded')"),
    )
    id = Column(UUID(as_uuid=True), ForeignKey('threads.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    idempotency_key = Column(UUID(as_uuid=True), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default='queued', index=True)
    input_state = Column(JSONB, nullable=False)
    resume_payload = Column(JSONB)
    outline = Column(JSONB, nullable=False, default=list)
    cost_limit_usd = Column(Numeric(16, 8), nullable=False)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    error = Column(Text)
    active_step = Column(String(64))
    lease_owner = Column(UUID(as_uuid=True))
    lease_expires_at = Column(DateTime, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class JobEvent(Base):
    __tablename__ = 'job_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('generation_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    event = Column(String(32), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Article(Base):
    __tablename__ = 'articles'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('generation_jobs.id', ondelete='SET NULL'), unique=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ArticleRevision(Base):
    __tablename__ = 'article_revisions'
    __table_args__ = (UniqueConstraint('article_id', 'version'),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    reason = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class SpendingAccount(Base):
    __tablename__ = 'spending_accounts'
    __table_args__ = (CheckConstraint('monthly_limit_usd >= 0'),)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    monthly_limit_usd = Column(Numeric(16, 8), nullable=False, default=10)


class LLMCall(Base):
    __tablename__ = 'llm_calls'
    __table_args__ = (CheckConstraint("status IN ('reserved','recorded','unresolved')"),)
    id = Column(UUID(as_uuid=True), primary_key=True)  # LangChain callback run ID
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey('generation_jobs.id', ondelete='SET NULL'), index=True)
    provider = Column(String(32), nullable=False)
    model = Column(String(150), nullable=False)
    input_tokens = Column(BigInteger)
    output_tokens = Column(BigInteger)
    input_rate = Column(Numeric(16, 8), nullable=False)
    output_rate = Column(Numeric(16, 8), nullable=False)
    reserved_usd = Column(Numeric(16, 8), nullable=False)
    estimated_usd = Column(Numeric(16, 8))
    status = Column(String(20), nullable=False, default='reserved')
    created_at = Column(DateTime, nullable=False, default=utcnow)
