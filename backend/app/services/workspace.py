from fastapi import HTTPException
from sqlalchemy import select, func
from app.core.workspace_models import GenerationJob, Article, ArticleRevision, JobEvent, LLMCall
from app.services.metering import committed


def stamp(value):
    return value.isoformat() + 'Z' if value else None


async def owned_job(db, user_id, job_id, lock=False):
    statement = select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    job = (await db.execute(statement)).scalar_one_or_none()
    if not job:
        raise HTTPException(404, 'Run not found')
    return job


async def owned_article(db, user_id, article_id, lock=False):
    statement = select(Article).where(Article.id == article_id, Article.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    article = (await db.execute(statement)).scalar_one_or_none()
    if not article:
        raise HTTPException(404, 'Draft not found')
    return article


def article_data(article):
    return dict(id=str(article.id), job_id=str(article.job_id) if article.job_id else None,
                title=article.title, content=article.content, version=article.version,
                created_at=stamp(article.created_at), updated_at=stamp(article.updated_at))


def add_revision(db, article, reason):
    db.add(ArticleRevision(article_id=article.id, version=article.version, title=article.title,
                           content=article.content, reason=reason))


async def job_data(db, job):
    article_id = (await db.execute(select(Article.id).where(Article.job_id == job.id))).scalar_one_or_none()
    last_event_id = (await db.execute(select(func.max(JobEvent.id)).where(JobEvent.job_id == job.id))).scalar_one()
    tokens = (await db.execute(select(func.coalesce(func.sum(LLMCall.input_tokens), 0),
                                     func.coalesce(func.sum(LLMCall.output_tokens), 0)).where(LLMCall.job_id == job.id))).one()
    return dict(id=str(job.id), topic=job.input_state['topic'], status=job.status, outline=job.outline,
                cancel_requested=job.cancel_requested, error=job.error, active_step=job.active_step,
                cost_limit_usd=str(job.cost_limit_usd), committed_usd=str(await committed(db, job.user_id, job.id)),
                input_tokens=tokens[0], output_tokens=tokens[1], article_id=str(article_id) if article_id else None,
                last_event_id=last_event_id or 0, created_at=stamp(job.created_at), updated_at=stamp(job.updated_at))
