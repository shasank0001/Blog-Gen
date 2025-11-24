import uuid
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models import Document, DocumentStatus
from app.services.pdf_service import pdf_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.pinecone_service import pinecone_service
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def process_document_task(doc_id: uuid.UUID, file_content: bytes, filename: str, namespace: str):
    """
    Background task to process document.
    
    Steps:
    1. Update status to PARSING.
    2. Extract text from PDF (CPU bound).
    3. Chunk text (CPU bound).
    4. Embed chunks (IO bound).
    5. Upsert to Pinecone (IO bound).
    6. Update status to READY.
    
    Handles errors by updating status to FAILED and logging the exception.
    """
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            logger.error(f"Document {doc_id} not found in background task")
            return

        try:
            logger.info(f"Starting processing for document {doc_id} ({filename})")
            
            # Update status to PARSING
            doc.status = DocumentStatus.PARSING
            await db.commit()
            
            # 1. Parse PDF (CPU bound)
            try:
                pages_content = await asyncio.to_thread(pdf_service.extract_text_with_metadata, file_content, filename)
            except Exception as e:
                raise ValueError(f"PDF Parsing failed: {str(e)}")
            
            # 2. Chunk Text (CPU bound)
            try:
                chunks = await asyncio.to_thread(chunking_service.split_documents, pages_content)
            except Exception as e:
                raise ValueError(f"Chunking failed: {str(e)}")
            
            if not chunks:
                 logger.warning(f"No text extracted from document {doc_id}")
                 doc.status = DocumentStatus.FAILED
                 doc.error_message = "No text extracted from document"
                 await db.commit()
                 return

            # Update status to EMBEDDING
            doc.status = DocumentStatus.EMBEDDING
            await db.commit()

            # 3. Embed Chunks (IO bound but sync client)
            try:
                texts = [chunk["text"] for chunk in chunks]
                embeddings = await asyncio.to_thread(embedding_service.embed_documents, texts)
            except Exception as e:
                raise ValueError(f"Embedding failed: {str(e)}")
            
            # 4. Prepare Vectors for Pinecone
            vectors = []
            for i, chunk in enumerate(chunks):
                vector_id = str(uuid.uuid4())
                vectors.append((
                    vector_id,
                    embeddings[i],
                    {
                        "text": chunk["text"],
                        **chunk["metadata"],
                        "doc_id": str(doc_id)
                    }
                ))
                
            # 5. Upsert to Pinecone (IO bound but sync client)
            try:
                await asyncio.to_thread(pinecone_service.upsert_vectors, vectors, namespace)
            except Exception as e:
                raise ValueError(f"Pinecone upsert failed: {str(e)}")
            
            # Update status to READY
            doc.status = DocumentStatus.READY
            await db.commit()
            logger.info(f"Successfully processed document {doc_id}")

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}", exc_info=True)
            # Re-fetch doc to avoid stale state issues if commit failed previously
            # But here we are in the same session.
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)
            try:
                await db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to save error state for document {doc_id}: {commit_error}")
