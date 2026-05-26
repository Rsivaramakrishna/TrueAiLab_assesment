import sqlite3
import json
import os
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_PATH = os.getenv("DATABASE_URL", "sqlite:///./rag_assistant.db").replace("sqlite:///./", "").replace("sqlite:///", "")

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create Chunks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        embedding TEXT NOT NULL, -- Stored as JSON string
        FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """)
    
    # Create Chat History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL, -- 'user' or 'assistant'
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

# ----------------- User Management -----------------

def create_user(username: str, password_hash: str) -> bool:
    """Insert a new user. Returns True if successful, False if username exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user details by username."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

# ----------------- Document Management -----------------

def insert_document(title: str, content: str) -> int:
    """Insert a document and return its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO documents (title, content) VALUES (?, ?)",
        (title, content)
    )
    doc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return doc_id

def delete_all_documents():
    """Clear all documents and chunks for re-indexing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks")
    cursor.execute("DELETE FROM documents")
    conn.commit()
    conn.close()

def get_all_documents() -> List[Dict[str, Any]]:
    """Get all documents in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ----------------- Chunk & Vector Management -----------------

def insert_chunk(doc_id: int, text: str, embedding: List[float]):
    """Insert a document chunk and its embedding vector."""
    conn = get_db_connection()
    cursor = conn.cursor()
    embedding_json = json.dumps(embedding)
    cursor.execute(
        "INSERT INTO chunks (doc_id, text, embedding) VALUES (?, ?, ?)",
        (doc_id, text, embedding_json)
    )
    conn.commit()
    conn.close()

def search_similar_chunks(query_vector: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Perform Cosine Similarity search over all stored chunks.
    Formula: cos_sim = (A . B) / (||A|| * ||B||)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Retrieve all chunks along with document titles
    cursor.execute("""
        SELECT chunks.id, chunks.text, chunks.embedding, documents.title as doc_title
        FROM chunks 
        JOIN documents ON chunks.doc_id = documents.id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []
    
    query_arr = np.array(query_vector, dtype=np.float32)
    query_norm = np.linalg.norm(query_arr)
    
    if query_norm == 0:
        return []
        
    results = []
    for row in rows:
        chunk_id = row['id']
        chunk_text = row['text']
        doc_title = row['doc_title']
        
        # Load embedding vector
        vector_arr = np.array(json.loads(row['embedding']), dtype=np.float32)
        vector_norm = np.linalg.norm(vector_arr)
        
        if vector_norm == 0:
            similarity = 0.0
        else:
            # Cosine similarity calculation
            dot_product = np.dot(query_arr, vector_arr)
            similarity = float(dot_product / (query_norm * vector_norm))
        
        results.append({
            "chunk_id": chunk_id,
            "title": doc_title,
            "content": chunk_text,
            "score": similarity
        })
        
    # Sort by similarity score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

# ----------------- Chat History Management -----------------

def save_chat_message(session_id: str, role: str, content: str):
    """Save a chat message in the session history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()

def get_chat_history(session_id: str, limit: int = 6) -> List[Dict[str, str]]:
    """
    Fetch the last N messages for a sessionId, ordered chronologically.
    A limit of 6 represents the last 3 user-assistant pairs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content 
        FROM chat_history 
        WHERE session_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    """, (session_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # We query descending to get the newest, but we return chronologically ordered (ascending)
    history = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
    return history

def clear_session_chat_history(session_id: str):
    """Delete all chat logs for a sessionId."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
