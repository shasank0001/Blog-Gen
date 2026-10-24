import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.core.database import get_db
from app.core.models import User
from app.core.workspace_models import Article, ArticleRevision, utcnow
from app.schemas_workspace import ArticleCreate, ArticleSave, RestoreRevision
from app.services.workspace import owned_article, article_data, add_revision, stamp

router = APIRouter()


@router.get('')
async def list_articles(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                        db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    articles = (await db.execute(select(Article).where(Article.user_id == user.id).order_by(desc(Article.updated_at))
                                .offset(skip).limit(limit + 1))).scalars().all()
    return {'items': [{key: value for key, value in article_data(item).items() if key != 'content'}
                      for item in articles[:limit]], 'has_more': len(articles) > limit}


@router.post('', status_code=201)
async def create_article(body: ArticleCreate, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    article = Article(user_id=user.id, title=body.title, content=body.content, version=1)
    db.add(article)
    await db.flush()
    add_revision(db, article, 'created')
    await db.commit()
    return article_data(article)


@router.get('/{article_id}')
async def get_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    return article_data(await owned_article(db, user.id, article_id))


@router.patch('/{article_id}')
async def save_article(article_id: uuid.UUID, body: ArticleSave,
                       db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    article = await owned_article(db, user.id, article_id, lock=True)
    # A retried save after a lost response is harmless if the server has that text.
    if article.title == body.title and article.content == body.content:
        return article_data(article)
    if article.version != body.expected_version:
        raise HTTPException(409, {'message': 'This draft changed in another tab. Reload its latest version before saving.',
                                  'current_version': article.version})
    article.title, article.content = body.title, body.content
    article.version += 1
    article.updated_at = utcnow()
    add_revision(db, article, 'autosave')
    await db.commit()
    return article_data(article)


@router.get('/{article_id}/revisions')
async def revisions(article_id: uuid.UUID, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                    db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    await owned_article(db, user.id, article_id)
    rows = (await db.execute(select(ArticleRevision).where(ArticleRevision.article_id == article_id)
                            .order_by(desc(ArticleRevision.version)).offset(skip).limit(limit + 1))).scalars().all()
    return {'items': [dict(id=str(row.id), version=row.version, title=row.title, reason=row.reason,
                           created_at=stamp(row.created_at)) for row in rows[:limit]], 'has_more': len(rows) > limit}


@router.get('/{article_id}/revisions/{revision_id}')
async def revision(article_id: uuid.UUID, revision_id: uuid.UUID,
                   db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    await owned_article(db, user.id, article_id)
    row = (await db.execute(select(ArticleRevision).where(ArticleRevision.id == revision_id,
                                                          ArticleRevision.article_id == article_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, 'Revision not found')
    return dict(id=str(row.id), version=row.version, title=row.title, content=row.content, reason=row.reason,
                created_at=stamp(row.created_at))


@router.post('/{article_id}/restore')
async def restore(article_id: uuid.UUID, body: RestoreRevision,
                  db: AsyncSession = Depends(get_db), user: User = Depends(deps.get_current_user)):
    article = await owned_article(db, user.id, article_id, lock=True)
    if article.version != body.expected_version:
        raise HTTPException(409, 'The draft changed. Reload before restoring a revision.')
    row = (await db.execute(select(ArticleRevision).where(ArticleRevision.id == body.revision_id,
                                                          ArticleRevision.article_id == article_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, 'Revision not found')
    article.title, article.content = row.title, row.content
    article.version += 1
    article.updated_at = utcnow()
    add_revision(db, article, 'restored')
    await db.commit()
    return article_data(article)
