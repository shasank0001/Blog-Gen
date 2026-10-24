import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.agent.graph import build_graph
from app.core.config import settings


class AgentRunner:
    def __init__(self):
        self.graph = None
        self.pool = None
        self.checkpointer = None

    async def setup(self):
        dsn = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
        # Serialize schema initialization between the API and independent workers.
        async with await psycopg.AsyncConnection.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
            await conn.execute('SELECT pg_advisory_lock(73190218)')
            try:
                await AsyncPostgresSaver(conn).setup()
            finally:
                await conn.execute('SELECT pg_advisory_unlock(73190218)')
        self.pool = AsyncConnectionPool(dsn, open=False, min_size=1, max_size=5,
            kwargs={'autocommit': True, 'prepare_threshold': 0, 'row_factory': dict_row},
            check=AsyncConnectionPool.check_connection)
        await self.pool.open(wait=True)
        self.checkpointer = AsyncPostgresSaver(self.pool)
        self.graph = build_graph().compile(checkpointer=self.checkpointer)

    async def shutdown(self):
        self.graph = None
        if self.pool:
            await self.pool.close()
            self.pool = None


runner = AgentRunner()
