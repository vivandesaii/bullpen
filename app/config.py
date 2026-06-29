from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket: str
    sqs_queue_name: str
    sqs_dlq_name: str
    postgres_db: str
    postgres_user: str
    postgres_password: str

    class Config:
        env_file = ".env"

settings = Settings() 
