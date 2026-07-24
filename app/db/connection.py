import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import settings

def get_connection():
    return psycopg2.connect(
        settings.database_url,
        cursor_factory=RealDictCursor
    )


