import boto3
import asyncio
import logging
from app.config import Settings
from app.utils.retry import with_retry

LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB

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
            Bucket=Settings().s3_documents_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type
            ServerSideEncryption="AES256"  # Optional: Enable server-side encryption
        )
        
    await asyncio.to_thread(_upload)
    logger.info(f"File uploaded to S3 with key: {key}")
    return key 


async def get_file_bytes(key: str) -> bytes: # Avoid using for large files, as it loads the entire file into memory. Consider using streaming for large files.
    """
    For small files (<10MB): loads entire file into memory.
    For large files (>=10MB): streams in chunks to avoid
    memory exhaustion.
    Size is checked from ContentLength before reading bytes.
    """
    def _get():
        response = s3_client.get_object(Bucket=Settings().s3_documents_bucket, Key=key)
        file_size = response['ContentLength']
        logger.info(
            f"Retriving: {key} "
             f"({file_size / 1024 / 1024:.1f}MB)"
        )

        if file_size < LARGE_FILE_THRESHOLD:
            # For small files, read the entire content into memory
            return response['Body'].read()
        else:
            # For large files, stream the content in chunks
            chunks = []
            chuck_size = 1024 * 1024  # 1 MB
            while True:
                chunk = response['Body'].read(chuck_size)
                if not chunk:
                    break
                chunks.append(chunk)
                
            return b''.join(chunks)
    file_bytes = await asyncio.to_thread(_get)
    logger.info(f"Retrieved: {key} ({len(file_bytes)} bytes)")
    return file_bytes