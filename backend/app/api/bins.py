from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.core.database import get_db
from app.core.models import KnowledgeBin, User, Document, DocumentStatus
from app.schemas import BinCreate, BinResponse, DocumentResponse, BinUpdate
from app.services.pinecone_service import pinecone_service
from app.services.ingestion_service import process_document_task
import uuid
import os

router = APIRouter()

@router.get("/", response_model=List[BinResponse])
async def get_bins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Retrieve all bins for current user.
    """
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.user_id == current_user.id))
    return result.scalars().all()

@router.post("/", response_model=BinResponse)
async def create_bin(
    bin_in: BinCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Create new bin.
    """
    bin = KnowledgeBin(
        name=bin_in.name,
        description=bin_in.description,
        user_id=current_user.id
    )
    db.add(bin)
    await db.commit()
    await db.refresh(bin)
    return bin

@router.patch("/{bin_id}", response_model=BinResponse)
async def update_bin(
    bin_id: uuid.UUID,
    bin_in: BinUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Update bin name or description.
    """
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id == bin_id, KnowledgeBin.user_id == current_user.id))
    bin = result.scalars().first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")
    
    if bin_in.name is not None:
        bin.name = bin_in.name
    if bin_in.description is not None:
        bin.description = bin_in.description
        
    await db.commit()
    await db.refresh(bin)
    return bin

@router.delete("/{bin_id}", response_model=BinResponse)
async def delete_bin(
    bin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Delete a Knowledge Bin and all associated documents.
    
    - Verifies ownership.
    - Deletes the corresponding Pinecone namespace (all vectors).
    - Deletes the Bin record from the database (cascading delete removes Documents).
    """
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id == bin_id, KnowledgeBin.user_id == current_user.id))
    bin = result.scalars().first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")
    
    try:
        # Delete from Pinecone
        namespace = f"{current_user.id}_{bin.id}"
        pinecone_service.delete_namespace(namespace)
        
        await db.delete(bin)
        await db.commit()
        return bin
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete bin: {str(e)}")

@router.delete("/documents/{doc_id}", response_model=DocumentResponse)
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Delete a document and its vectors.
    """
    # We need to join with KnowledgeBin to verify user ownership
    result = await db.execute(
        select(Document)
        .join(KnowledgeBin)
        .where(Document.id == doc_id, KnowledgeBin.user_id == current_user.id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete vectors from Pinecone
        # Namespace is {user_id}_{bin_id}
        namespace = f"{current_user.id}_{doc.bin_id}"
        pinecone_service.delete_vectors(namespace=namespace, filter={"doc_id": str(doc_id)})
        
        await db.delete(doc)
        await db.commit()
        return doc
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.post("/{bin_id}/resync", response_model=List[DocumentResponse])
async def resync_bin(
    bin_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Resync stuck documents (PARSING/EMBEDDING) in a bin.
    """
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id == bin_id, KnowledgeBin.user_id == current_user.id))
    bin = result.scalars().first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")
        
    # Find stuck documents
    result = await db.execute(
        select(Document)
        .where(
            Document.bin_id == bin_id, 
            Document.status.in_([DocumentStatus.PARSING, DocumentStatus.EMBEDDING])
        )
    )
    stuck_docs = result.scalars().all()
    
    namespace = f"{current_user.id}_{bin_id}"
    
    for doc in stuck_docs:
        if doc.file_path and os.path.exists(doc.file_path):
            with open(doc.file_path, "rb") as f:
                content = f.read()
            
            # Reset status
            doc.status = DocumentStatus.UPLOADED
            doc.error_message = None
            
            background_tasks.add_task(process_document_task, doc.id, content, doc.filename, namespace)
        else:
            doc.status = DocumentStatus.FAILED
            doc.error_message = "File not found on server. Please re-upload."
        
    await db.commit()
    
    # Return all docs
    result = await db.execute(select(Document).where(Document.bin_id == bin_id))
    return result.scalars().all()

@router.get("/{bin_id}/files", response_model=List[DocumentResponse])
async def get_bin_files(
    bin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get files in a bin.
    """
    # Verify bin ownership
    result = await db.execute(select(KnowledgeBin).where(KnowledgeBin.id == bin_id, KnowledgeBin.user_id == current_user.id))
    bin = result.scalars().first()
    if not bin:
        raise HTTPException(status_code=404, detail="Bin not found")
        
    result = await db.execute(select(Document).where(Document.bin_id == bin_id))
    return result.scalars().all()
