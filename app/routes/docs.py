import json
import os
import logging
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.models.schemas import DocsList, DocUploadResponse
from app.routes.chat import get_current_user
from app.utils.chunker import chunk_text
from app.services.embedding_service import generate_embedding
from app.vectorstore import database as db

router = APIRouter(prefix="/api/docs", tags=["documents"])
logger = logging.getLogger("rag_assistant")

def index_document_content(doc_id: int, title: str, content: str) -> int:
    """Helper to chunk content, generate vectors, and persist them."""
    # 1. Chunk document
    # Using 250 words per chunk with 50 words overlap (roughly 300-350 tokens)
    chunks = chunk_text(content, chunk_size_words=250, overlap_words=50)
    
    # 2. Embed and store each chunk
    for chunk in chunks:
        vector = generate_embedding(chunk)
        db.insert_chunk(doc_id, chunk, vector)
        
    return len(chunks)

@router.get("", response_model=List[dict])
def get_documents(username: str = Depends(get_current_user)):
    """List all documents currently indexed in the system."""
    return db.get_all_documents()

@router.post("/upload", response_model=DocUploadResponse)
def upload_documents(payload: DocsList, username: str = Depends(get_current_user)):
    """
    Index a list of custom documents. 
    Clears existing docs and re-indexes them.
    """
    if not payload.documents:
        raise HTTPException(status_code=400, detail="Document list cannot be empty.")
        
    try:
        # Clear existing tables for a fresh index (can be adjusted for incremental indexing)
        db.delete_all_documents()
        
        inserted_docs_count = 0
        total_chunks_count = 0
        
        for doc in payload.documents:
            # Save document
            doc_id = db.insert_document(doc.title, doc.content)
            inserted_docs_count += 1
            
            # Chunk, embed and insert vector chunks
            chunks_created = index_document_content(doc_id, doc.title, doc.content)
            total_chunks_count += chunks_created
            
        return DocUploadResponse(
            status="success",
            inserted_documents=inserted_docs_count,
            total_chunks=total_chunks_count
        )
    except Exception as e:
        logger.error(f"Error during document indexing: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process and index documents: {str(e)}"
        )

@router.post("/reindex-default", response_model=DocUploadResponse)
def reindex_default(username: str = Depends(get_current_user)):
    """
    Load documents from the root docs.json file and index them.
    """
    docs_path = "docs.json"
    if not os.path.exists(docs_path):
        raise HTTPException(status_code=404, detail="Default docs.json not found in root directory.")
        
    try:
        with open(docs_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
            
        db.delete_all_documents()
        inserted_docs_count = 0
        total_chunks_count = 0
        
        for doc in docs:
            title = doc.get("title", "Untitled")
            content = doc.get("content", "").strip()
            
            if not content:
                continue
                
            doc_id = db.insert_document(title, content)
            inserted_docs_count += 1
            
            chunks_created = index_document_content(doc_id, title, content)
            total_chunks_count += chunks_created
            
        logger.info(f"Successfully re-indexed docs.json. Total documents: {inserted_docs_count}, Total chunks: {total_chunks_count}")
        return DocUploadResponse(
            status="success",
            inserted_documents=inserted_docs_count,
            total_chunks=total_chunks_count
        )
        
    except Exception as e:
        logger.error(f"Error reindexing docs.json: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Re-indexing failed: {str(e)}"
        )
