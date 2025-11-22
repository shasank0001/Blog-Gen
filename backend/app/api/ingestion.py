from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.pdf_service import pdf_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service
from app.services.pinecone_service import pinecone_service
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    bin_id: str = Form(...)
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        
        # 1. Parse PDF
        pages_content = pdf_service.extract_text_with_metadata(content, file.filename)
        
        # 2. Chunk Text
        chunks = chunking_service.split_documents(pages_content)
        
        if not chunks:
             return {"message": "No text extracted from document", "chunks": 0}

        # 3. Embed Chunks
        texts = [chunk["text"] for chunk in chunks]
        embeddings = embedding_service.embed_documents(texts)
        
        # 4. Prepare Vectors for Pinecone
        vectors = []
        for i, chunk in enumerate(chunks):
            vector_id = str(uuid.uuid4())
            vectors.append((
                vector_id,
                embeddings[i],
                {
                    "text": chunk["text"],
                    **chunk["metadata"]
                }
            ))
            
        # 5. Upsert to Pinecone
        namespace = f"{user_id}_{bin_id}"
        pinecone_service.upsert_vectors(vectors, namespace)
        
        return {
            "message": "Document processed successfully",
            "filename": file.filename,
            "chunks": len(chunks),
            "namespace": namespace
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
