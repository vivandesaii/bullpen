"""
Migration runner for Bullpen.

Locally, Docker mounts app/db/migrations/001_create_tables.sql into
/docker-entrypoint-initdb.d/ and Postgres runs it automatically on first
start. Railway's Postgres has no such hook — it's a blank database — so
this script does the same job by hand: run every .sql file in
app/db/migrations/ that hasn't been applied yet, in filename order, and
record each one so it never runs twice.

Usage: python -m app.db.migrate
"""

import os
import logging
import psycopg2

from app.config import settings

logger = logging.getLogger("migrate")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def run_migrations():
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Tracks which migration files have already been applied, so
        # re-running this script is always safe.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()

        cursor.execute("SELECT filename FROM schema_migrations")
        already_applied = {row[0] for row in cursor.fetchall()}

        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
        )

        if not migration_files:
            logger.info("No migration files found in %s", MIGRATIONS_DIR)
            return

        for filename in migration_files:
            if filename in already_applied:
                logger.info("Skipping %s (already applied)", filename)
                continue

            path = os.path.join(MIGRATIONS_DIR, filename)
            with open(path, "r") as f:
                sql = f.read()

            logger.info("Applying %s...", filename)
            try:
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,)
                )
                conn.commit()
                logger.info("Applied %s", filename)
            except Exception:
                conn.rollback()
                logger.error("Failed to apply %s — rolled back", filename)
                raise

        logger.info("Migrations complete.")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migrations()
