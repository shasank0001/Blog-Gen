import psycopg2
from psycopg2 import pool
from app.core.config import settings
from contextlib import contextmanager

class PostgresService:
    def __init__(self):
        self.connection_pool = None
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,
                dsn=settings.DATABASE_URL
            )
            print("PostgreSQL connection pool created successfully")
        except (Exception, psycopg2.DatabaseError) as error:
            print("Error while connecting to PostgreSQL", error)

    @contextmanager
    def get_cursor(self):
        conn = self.connection_pool.getconn()
        try:
            yield conn.cursor()
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.connection_pool.putconn(conn)

    def close(self):
        if self.connection_pool:
            self.connection_pool.closeall()
            print("PostgreSQL connection pool is closed")

postgres_service = PostgresService()
