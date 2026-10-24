from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Money = Decimal


class GenerateRequest(BaseModel):
    idempotency_key: UUID
    topic: str = Field(min_length=1, max_length=500)
    tone_urls: list[str] = Field(default_factory=list, max_length=10)
    profile_id: UUID | None = None
    target_domain: str = Field(default='', max_length=2048)
    selected_bins: list[UUID] = Field(default_factory=list, max_length=10)
    use_local: bool = False
    model_provider: Literal['openai', 'anthropic', 'google'] = 'openai'
    model_name: str = Field(default='gpt-5.1', max_length=150)
    style_profile: dict | None = None
    research_sources: list[Literal['web', 'social', 'academic', 'internal']] = Field(default_factory=lambda: ['web', 'internal'], max_length=4)
    deep_research_mode: bool = False
    blog_size: Literal['small', 'medium', 'large'] = 'medium'
    research_guidelines: list[str] = Field(default_factory=list, max_length=30)
    target_audience: str = Field(default='', max_length=2000)
    extra_context: str = Field(default='', max_length=50000)
    cost_limit_usd: Decimal = Field(default=Decimal('2'), gt=0, le=10000, max_digits=13, decimal_places=8)

    @field_validator('topic')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Topic cannot be blank')
        return value.strip()


class OutlineSection(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]+$', max_length=100)
    title: str = Field(min_length=1, max_length=500)
    intent: str = Field(max_length=10000)
    source_ids: list[str] = Field(default_factory=list, max_length=100)
    content: str | None = None


class ResumeJob(BaseModel):
    approved_outline: list[OutlineSection] | None = Field(default=None, min_length=1, max_length=30)
    cost_limit_usd: Decimal | None = Field(default=None, gt=0, le=10000, max_digits=13, decimal_places=8)

    @field_validator('approved_outline')
    @classmethod
    def unique_sections(cls, value):
        if value and len({item.id for item in value}) != len(value):
            raise ValueError('Section IDs must be unique')
        return value


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(default='', max_length=1000000)

    @field_validator('title')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Title cannot be blank')
        return value.strip()


class ArticleSave(ArticleCreate):
    expected_version: int = Field(ge=1)


class RestoreRevision(BaseModel):
    revision_id: UUID
    expected_version: int = Field(ge=1)


class UpdateSpendingLimit(BaseModel):
    monthly_limit_usd: Decimal = Field(ge=0, le=100000, max_digits=14, decimal_places=8)
