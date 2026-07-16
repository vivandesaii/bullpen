import boto3
import asyncio
import logging
from app.config import settings
from app.utils.retry import with_retry

LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB

logger = logging.getLogger("s3_service")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region,
)

async def upload_file(file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """
    Uploads a file to S3 and returns the S3 object key.
    Only supports files under LARGE_FILE_THRESHOLD; larger files
    need multipart upload (not yet implemented).
    """
    if len(file_bytes) >= LARGE_FILE_THRESHOLD:
        # put_object loads the whole payload into memory; large files
        # need multipart upload instead
        raise NotImplementedError("Multipart upload not yet implemented for files >= 10MB")

    def _upload():
        s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    # with_retry is sync (uses time.sleep), so run the whole
    # retry loop in a thread to avoid blocking the event loop
    await asyncio.to_thread(with_retry, _upload, operation_name=f"s3_upload:{key}")
    logger.info(f"File uploaded to S3 with key: {key}")
    return key


async def get_file_bytes(key: str) -> bytes:
    """
    For small files (<10MB): loads entire file into memory.
    For large files (>=10MB): streams in chunks to avoid
    memory exhaustion.
    Size is checked from ContentLength before reading bytes.
    """
    def _get():
        response = s3_client.get_object(Bucket=settings.s3_bucket, Key=key)
        file_size = response['ContentLength']
        logger.info(
            f"Retrieving: {key} "
            f"({file_size / 1024 / 1024:.1f}MB)"
        )

        if file_size < LARGE_FILE_THRESHOLD:
            # For small files, read the entire content into memory
            return response['Body'].read()
        else:
            # For large files, stream the content in chunks
            chunks = []
            chunk_size = 1024 * 1024  # 1 MB
            while True:
                chunk = response['Body'].read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)

            return b''.join(chunks)

    file_bytes = await asyncio.to_thread(with_retry, _get, operation_name=f"s3_get:{key}")
    logger.info(f"Retrieved: {key} ({len(file_bytes)} bytes)")
    return file_bytes

async def generate_presigned_url(key: str, expiration: int | None = None) -> str:
    """
    Generates a presigned URL for accessing an S3 object.
    """
    # Resolved at call time so the settings default isn't baked in at import
    expiration = expiration if expiration is not None else settings.s3_presigned_url_expiration

    def _generate():
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.s3_bucket, 'Key': key},
            ExpiresIn=expiration
        )

    presigned_url = await asyncio.to_thread(_generate)
    logger.info(f"Generated presigned URL for key: {key}"
                f" (expires in {expiration} seconds)")
    return presigned_url


async def generate_presigned_upload_url(key: str, expiration: int | None = None) -> str:
    """
    Generates a presigned URL for uploading an S3 object.
    """
    expiration = expiration if expiration is not None else settings.s3_presigned_url_expiration

    def _generate():
        return s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': settings.s3_bucket, 'Key': key},
            ExpiresIn=expiration
        )

    presigned_upload_url = await asyncio.to_thread(_generate)
    logger.info(f"Generated presigned upload URL for key: {key}"
                f" (expires in {expiration} seconds)")
    return presigned_upload_url
