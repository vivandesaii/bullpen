from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Configuration for the application settings, including database, Redis, secret key, AWS S3 and SQS, and PostgreSQL credentials
    database_url: str
    redis_url: str
    secret_key: str
    # AWS S3 and SQS configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket: str
    s3_presigned_url_expiration: int = 3600  # Default expiration time for presigned URLs in seconds
    sqs_queue_url: str
    sqs_dlq_url: str
    aws_endpoint_url: str = "http://localstack:4566"

    # These are only used to configure the Postgres/SQS containers
    # themselves in docker-compose.yaml — the app connects via
    # database_url / sqs_queue_url / sqs_dlq_url, never these directly.
    # Optional so a deploy target missing them (e.g. Railway) doesn't
    # crash the whole app over unused config.
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    sqs_queue_name: Optional[str] = None
    sqs_dlq_name: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
