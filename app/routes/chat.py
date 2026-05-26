from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.schemas import ChatRequest, ChatResponse
from app.utils.auth_helper import decode_access_token
from app.services import rag_service
from app.vectorstore import database as db
import logging

router = APIRouter(prefix="/api", tags=["chat"])
security = HTTPBearer(auto_error=False)
logger = logging.getLogger("rag_assistant")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validate the JWT token and return the username.
    If no credentials are provided, we raise 401 since Auth is mandatory (bonus feature).
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing. Please log in."
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token. Please log in again."
        )
    
    return payload["sub"]

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, username: str = Depends(get_current_user)):
    """
    RAG Chat endpoint. Receives query, performs similarity search, 
    consults conversation history, calls LLM, and logs analytics.
    """
    # 1. Payload validation
    msg_stripped = request.message.strip()
    if not msg_stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message field cannot be empty or only spaces."
        )
        
    session_stripped = request.sessionId.strip()
    if not session_stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID is required."
        )
        
    # Associate session with username to avoid cross-user session tampering
    user_scoped_session = f"{username}:{session_stripped}"
    
    try:
        # 2. Execute RAG query
        result = rag_service.execute_rag_query(user_scoped_session, msg_stripped)
        
        return ChatResponse(
            reply=result["reply"],
            tokensUsed=result["tokensUsed"],
            retrievedChunks=result["retrievedChunks"],
            modelName=result["modelName"],
            similarityScores=result["similarityScores"]
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        # Check if it was an LLM service exception and propagate status code
        from app.services.llm_service import LLMException
        if isinstance(e, LLMException):
            raise HTTPException(status_code=e.status_code, detail=e.message)
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during chat generation: {str(e)}"
        )

@router.post("/chat/clear")
def clear_chat_history(request: ChatRequest, username: str = Depends(get_current_user)):
    """Clear chat logs for a specific session."""
    session_stripped = request.sessionId.strip()
    if not session_stripped:
        raise HTTPException(status_code=400, detail="Session ID is required.")
        
    user_scoped_session = f"{username}:{session_stripped}"
    db.clear_session_chat_history(user_scoped_session)
    return {"message": f"Chat history for session {session_stripped} cleared."}
