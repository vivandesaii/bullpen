#app/routes/documents.py
from fastapi import APIRouter, File, Form, HTTPException, Depends, UploadFile
from app.services.s3_service import generate_presigned_upload_url, delete_file, generate_presigned_url, get_file_bytes, upload_file
from app.config import settings
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit
from app.db.connection import get_connection
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
    conn = get_connection()
    cursor = conn.cursor()

    try:

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

        cursor.execute(
            """
            INSERT INTO documents (user_id, s3_key, document_type, content_type)
            VALUES (%s,%s,%s,%s)
            RETURNING id
            """,
            (user_id, key, document_type, file.content_type)
        )

        document_id = cursor.fetchone()["id"]
        conn.commit()

        return {
            "s3_key": key,
            "status": "uploaded"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Upload failed.")

    finally:
        cursor.close()
        conn.close()


@router.get("/download", tags=["documents"], dependencies=[Depends(check_rate_limit)])
async def download(s3_key: str, user_id: int = Depends(get_session)):
    """
    Endpoint to generate a presigned URL for downloading a document from S3.
    """

    conn = get_connection()
    cursor = conn.cursor()
    try:
        
        cursor.execute(
            """
            SELECT id, s3_key, user_id FROM documents
            WHERE s3_key = %s AND user_id = %s
            """,
            (s3_key, user_id)
        )

        doc = cursor.fetchone()

        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found.")

        url = await generate_presigned_url(s3_key, expiration=settings.s3_presigned_url_expiration)

        return {
            "url": url,
            "expires_in": settings.s3_presigned_url_expiration
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail="Download failed.")

    finally:
        cursor.close()
        conn.close()

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
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:

        cursor.execute(
            """
            SELECT id, document_type FROM documents
            WHERE s3_key = %s AND user_id = %s
            """,
            (s3_key, user_id)
        )

        doc = cursor.fetchone()

        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found.")

    # regulatory protection -- cannot delete these document types
        PROTECTED_TYPES = {"statements", "confirmations"}
        if doc["document_type"] in PROTECTED_TYPES:
            raise HTTPException(
                status_code=403,
                detail="Regulatory documents cannot be deleted"
            )

        await delete_file(s3_key)

        return {"status": "deleted", "s3_key": s3_key}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Delete failed.")

    finally:
        cursor.close()
        conn.close()
