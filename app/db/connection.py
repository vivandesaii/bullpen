import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.config import settings

connection_pool = pool.ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    dsn=settings.database_url,
    cursor_factory=RealDictCursor
)

def get_connection():
    return connection_pool.getconn()

def release_connection(conn):
    connection_pool.putconn(conn)