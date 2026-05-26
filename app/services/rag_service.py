import os
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

from app.vectorstore import database as db
from app.services.embedding_service import generate_embedding
from app.services.llm_service import call_llm

load_dotenv(override=True)

logger = logging.getLogger("rag_assistant")

# Configurations
DEFAULT_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))
DEFAULT_TOP_K = int(os.getenv("TOP_K", "3"))

def execute_rag_query(session_id: str, message: str) -> Dict[str, Any]:
    """
    Executes the complete RAG workflow:
    1. Embed user query
    2. Search vector database for top-k matches
    3. Filter by similarity threshold
    4. Fetch chat history for context continuity
    5. Build grounded prompt and run LLM
    6. Record history in the database
    """
    logger.info(f"Received query for session '{session_id}': '{message}'")
    
    # Check threshold and top_k from environment
    threshold = float(os.getenv("SIMILARITY_THRESHOLD", str(DEFAULT_THRESHOLD)))
    top_k = int(os.getenv("TOP_K", str(DEFAULT_TOP_K)))

    # Step 1: Embed user query
    logger.info("Generating embedding for query...")
    query_vector = generate_embedding(message)
    
    # Step 2: Retrieve similar chunks
    logger.info(f"Searching similar chunks in SQLite (Top-K={top_k})...")
    similar_chunks = db.search_similar_chunks(query_vector, top_k=top_k)
    
    # Extract similarity scores for logging/diagnostics
    scores = [chunk["score"] for chunk in similar_chunks]
    logger.info(f"Similarity scores found: {scores}")
    
    # Step 3: Apply similarity threshold
    best_score = scores[0] if scores else 0.0
    
    # Grounding check:
    if not similar_chunks or best_score < threshold:
        logger.warning(f"Best score {best_score} is below threshold {threshold}. Returning fallback response.")
        
        reply = "I could not find enough information in the knowledge base to answer this question."
        
        # Save user message and fallback answer to keep conversational flow consistent
        db.save_chat_message(session_id, "user", message)
        db.save_chat_message(session_id, "assistant", reply)
        
        return {
            "reply": reply,
            "tokensUsed": 0,
            "retrievedChunks": 0,
            "modelName": "system-grounding-guard",
            "similarityScores": scores
        }
        
    # Build context from chunks that pass threshold
    filtered_chunks = [chunk for chunk in similar_chunks if chunk["score"] >= threshold]
    context_parts = []
    for idx, chunk in enumerate(filtered_chunks):
        context_parts.append(
            f"[Source {idx+1}] Document: {chunk['title']}\nContent: {chunk['content']}"
        )
    context_str = "\n\n".join(context_parts)
    
    # Step 4: Retrieve chat history (limit to last 6 messages = 3 turns)
    history_list = db.get_chat_history(session_id, limit=6)
    history_parts = []
    for msg in history_list:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_parts.append(f"{role}: {msg['content']}")
    history_str = "\n".join(history_parts) if history_parts else "No previous history."
    
    # Step 5: Build final grounded RAG prompt
    prompt = f"""You are a helpful assistant.

Use ONLY the provided context to answer the user's question. If the context does not contain the answer, reply stating you don't have enough information. Do not use external facts.

Context:
{context_str}

Conversation History:
{history_str}

Question:
{message}

Answer:"""

    # Step 6: Call LLM API
    reply_text, tokens_used, model_name = call_llm(prompt)
    
    # Step 7: Record chat history
    db.save_chat_message(session_id, "user", message)
    db.save_chat_message(session_id, "assistant", reply_text)
    
    return {
        "reply": reply_text,
        "tokensUsed": tokens_used,
        "retrievedChunks": len(filtered_chunks),
        "modelName": model_name,
        "similarityScores": [chunk["score"] for chunk in filtered_chunks]
    }
