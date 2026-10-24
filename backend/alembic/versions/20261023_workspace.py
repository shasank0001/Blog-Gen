"""Durable jobs, editable articles and LLM usage ledger.

Revision ID: 20261023_workspace
Revises: b8f8c2ac5f5d
"""
from alembic import op

revision = '20261023_workspace'
down_revision = 'b8f8c2ac5f5d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE generation_jobs (
    id UUID NOT NULL,
    user_id UUID NOT NULL,
    idempotency_key UUID NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    input_state JSONB NOT NULL,
    resume_payload JSONB,
    outline JSONB NOT NULL,
    cost_limit_usd NUMERIC(16, 8) NOT NULL,
    cancel_requested BOOLEAN NOT NULL,
    error TEXT,
    active_step VARCHAR(64),
    lease_owner UUID,
    lease_expires_at TIMESTAMP WITHOUT TIME ZONE,
    attempts INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (user_id, idempotency_key),
    CHECK (cost_limit_usd > 0),
    CHECK (status IN ('queued','running','awaiting_approval','completed','failed','cancelled','budget_exceeded')),
    FOREIGN KEY(id) REFERENCES threads (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)
""")
    op.execute("""
CREATE INDEX ix_generation_jobs_lease_expires_at ON generation_jobs (lease_expires_at)
""")
    op.execute("""
CREATE INDEX ix_generation_jobs_status ON generation_jobs (status)
""")
    op.execute("""
CREATE INDEX ix_generation_jobs_user_id ON generation_jobs (user_id)
""")
    op.execute("""
CREATE TABLE job_events (
    id BIGSERIAL NOT NULL,
    job_id UUID NOT NULL,
    event VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(job_id) REFERENCES generation_jobs (id) ON DELETE CASCADE
)
""")
    op.execute("""
CREATE INDEX ix_job_events_job_id ON job_events (job_id)
""")
    op.execute("""
CREATE TABLE articles (
    id UUID NOT NULL,
    user_id UUID NOT NULL,
    job_id UUID,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (job_id),
    FOREIGN KEY(job_id) REFERENCES generation_jobs (id) ON DELETE SET NULL
)
""")
    op.execute("""
CREATE INDEX ix_articles_user_id ON articles (user_id)
""")
    op.execute("""
CREATE TABLE article_revisions (
    id UUID NOT NULL,
    article_id UUID NOT NULL,
    version INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    reason VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (article_id, version),
    FOREIGN KEY(article_id) REFERENCES articles (id) ON DELETE CASCADE
)
""")
    op.execute("""
CREATE INDEX ix_article_revisions_article_id ON article_revisions (article_id)
""")
    op.execute("""
CREATE TABLE spending_accounts (
    user_id UUID NOT NULL,
    monthly_limit_usd NUMERIC(16, 8) NOT NULL,
    PRIMARY KEY (user_id),
    CHECK (monthly_limit_usd >= 0),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)
""")
    op.execute("""
CREATE TABLE llm_calls (
    id UUID NOT NULL,
    user_id UUID NOT NULL,
    job_id UUID,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(150) NOT NULL,
    input_tokens BIGINT,
    output_tokens BIGINT,
    input_rate NUMERIC(16, 8) NOT NULL,
    output_rate NUMERIC(16, 8) NOT NULL,
    reserved_usd NUMERIC(16, 8) NOT NULL,
    estimated_usd NUMERIC(16, 8),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (status IN ('reserved','recorded','unresolved')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES generation_jobs (id) ON DELETE SET NULL
)
""")
    op.execute("""
CREATE INDEX ix_llm_calls_job_id ON llm_calls (job_id)
""")
    op.execute("""
CREATE INDEX ix_llm_calls_user_id ON llm_calls (user_id)
""")


def downgrade():
    op.drop_table('llm_calls')
    op.drop_table('spending_accounts')
    op.drop_table('article_revisions')
    op.drop_table('articles')
    op.drop_table('job_events')
    op.drop_table('generation_jobs')
