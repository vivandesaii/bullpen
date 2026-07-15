import boto3
import asyncio
import logging
from app.config import Settings
from app.utils.retry import with_retry

logger = logging.getLogger("s3_service")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=Settings().aws_access_key_id,
    aws_secret_access_key=Settings().aws_secret_access_key,
    region_name=Settings().aws_region,
)

async def upload_file(file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """
    Uploads a file to S3 and returns the S3 object key.
    """
    def _upload():
        s3_client.put_object(
            Bucket=Settings().s3_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type
            ServerSideEncryption="AES256"  # Optional: Enable server-side encryption
        )
        
    await asyncio.to_thread(_upload)
    logger.info(f"File uploaded to S3 with key: {key}")
    return key 



