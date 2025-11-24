import logging
import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.core.database import get_db
from app.core.models import Document, User, DocumentStatus, KnowledgeBin
from app.services.ingestion_service import process_document_task
from sqlalchemy import select
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bin_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Upload a PDF document to a specific Knowledge Bin.
    
    - Validates file type (PDF only).
    - Verifies bin ownership.
    - Saves file to local disk.
    - Creates a Document record with status 'UPLOADED'.
    - Triggers a background task for processing (Parse -> Chunk -> Embed -> Upsert).
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE/1024/1024}MB")

    # Verify bin ownership
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id == bin_id, KnowledgeBin.user_id == current_user.id))
    bin = result.scalars().first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")

    try:
        # Create Document record
        doc = Document(
            bin_id=bin_id,
            filename=file.filename,
            status=DocumentStatus.UPLOADED
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        
        # Save file to disk
        file_path = os.path.join(UPLOAD_DIR, f"{doc.id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
            
        doc.file_path = file_path
        await db.commit()
        
        # Trigger background task
        # Namespace format: {user_id}_{bin_id}
        namespace = f"{current_user.id}_{bin_id}"
        
        background_tasks.add_task(process_document_task, doc.id, content, file.filename, namespace)
        
        logger.info(f"Document {doc.id} uploaded by user {current_user.id} to bin {bin_id}")
        
        return {
            "message": "Document uploaded and processing started",
            "document_id": doc.id,
            "status": "uploaded"
        }

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during upload")
