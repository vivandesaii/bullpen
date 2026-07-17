#app/routes/documents.py
from fastapi import APIRouter, File, Form, HTTPException, Depends, UploadFile
from app.services.s3_service import generate_presigned_upload_url, delete_file, generate_presigned_url, get_file_bytes, upload_file
from app.config import settings
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit
# from app.db.connections import get_db
import uuid

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload", tags=["documents"], dependencies=[Depends(check_rate_limit)])
async def upload(file: UploadFile = File(...),
                 document_type: str = Form(...),
                 user_id: int = Depends(get_session)):
                 # db: Session = Depends(get_db):
    """
    Endpoint to generate a presigned URL for uploading a document to S3.
    """

    # Validate the document type
    ALLOWED = {"application/pdf", "image/jpeg", "image/png"}
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Invalid document type")

    # Validate file size
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB — must stay <= LARGE_FILE_THRESHOLD in s3_service
    file_bytes = await file.read()
    if len(file_bytes) >= MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the maximum limit of 10 MB")
    
    # Build s3 key using user_id and a unique identifier
    key = (
        f"documents/{user_id}/{document_type}/{uuid.uuid4()}-{file.filename}"
    )

    # Upload to s3
    await upload_file(file_bytes, key, file.content_type)
    # TODO: Store metadata in postgres

    return {
        "s3_key": key,
        "status": "uploaded"
    }

@router.get("/download", tags=["documents"], dependencies=[Depends(check_rate_limit)])
async def download(s3_key: str, user_id: int = Depends(get_session)):
    """
    Endpoint to generate a presigned URL for downloading a document from S3.
    """
    
    # TODO: Validate that the user has access to the requested document based on metadata stored in Postgres
    # SELECT FROM documents WHERE id = key AND user_id = user["user_id"]

    url = await generate_presigned_url(s3_key, expiration=settings.s3_presigned_url_expiration)

    return {
        "url": url,
        "expires_in": settings.s3_presigned_url_expiration
    }

@router.post("/upload-url", tags=["documents"], dependencies=[Depends(check_rate_limit)])
async def get_upload_url(document_type: str = Form(...),
                     filename: str = Form(...),
                     content_type: str = Form(...),
                     user_id: int = Depends(get_session)):
    """
    Client-facing endpoint to generate a presigned URL for uploading a document to S3.
    """

    ALLOWED = {"application/pdf", "image/jpeg", "image/png"}
    if content_type not in ALLOWED:
        raise HTTPException(400, detail="File type not allowed")
    
    key = (f"documents/{user_id}/{document_type}/{uuid.uuid4()}-{filename}")
    
    url = await generate_presigned_upload_url(key=key, content_type=content_type, expiration=settings.s3_presigned_url_expiration)

    return {
        "upload_url": url,
        "key": key,
        "expires_in": settings.s3_presigned_url_expiration
    }

@router.delete("/delete", tags=["documents"], dependencies=[Depends(check_rate_limit)])
async def delete(s3_key: str, user_id: int = Depends(get_session)):
    """
    Deletes a document from S3.
    Only permitted for certain document types.
    Statements and trade confirmations cannot be deleted
    due to regulatory retention requirements.
    TODO Module 10: look up document by id from Postgres,
    verify ownership, check document_type before deleting.
    """

    # TODO Module 10: replace this with a Postgres lookup
    # SELECT document_type FROM documents
    # WHERE s3_key = :key AND user_id = :user_id
    # for now we infer document type from the key string
    # this is a temporary workaround until DB is wired in

    # ownership check: keys are documents/{user_id}/{document_type}/...
    if not s3_key.startswith(f"documents/{user_id}/"):
        raise HTTPException(status_code=403, detail="Not your document")

    # regulatory protection -- cannot delete these document types
    # (document_type is the third segment of the key)
    PROTECTED_TYPES = {"statements", "confirmations"}
    parts = s3_key.split("/")
    if len(parts) > 2 and parts[2] in PROTECTED_TYPES:
        raise HTTPException(
            status_code=403,
            detail="Regulatory documents cannot be deleted"
        )

    await delete_file(s3_key)

    return {"status": "deleted", "s3_key": s3_key}