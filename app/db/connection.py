import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.config import settings

connection_pool = pool.ThreadedConnectionPool(
    minconn=1,  # opened eagerly at import time (before uvicorn finishes
                # loading the app) — kept low so a constrained Postgres
                # connection limit can't stall startup
    maxconn=20,
    dsn=settings.database_url,
    cursor_factory=RealDictCursor,
    connect_timeout=10  # fail fast and loud on a bad/unreachable host instead
                        # of hanging silently past the platform healthcheck window
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)