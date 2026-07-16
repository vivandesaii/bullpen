from pydantic_settings import BaseSettings

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
    sqs_queue_name: str
    sqs_dlq_name: str
    sqs_queue_url: str
    sqs_dlq_url: str
    # PostgreSQL configuration
    postgres_db: str
    postgres_user: str
    postgres_password: str

    class Config:
        env_file = ".env"

settings = Settings() 
