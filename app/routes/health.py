import os
from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.vectorstore import database as db

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check():
    """Verify system health, database accessibility, and configurations."""
    # Check database connectivity
    try:
        conn = db.get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return HealthResponse(
        status="healthy",
        database=db_status,
        embedding_model=os.getenv("EMBEDDING_PROVIDER", "local"),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini")
    )
