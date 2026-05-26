from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Authentication Schemas
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")

class UserLogin(BaseModel):
    username: str = Field(...)
    password: str = Field(...)

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

# Chat Schemas
class ChatRequest(BaseModel):
    sessionId: str = Field(..., description="Unique chat session identifier")
    message: str = Field(..., min_length=1, description="User question or statement")

class ChatResponse(BaseModel):
    reply: str = Field(..., description="Grounded response from the assistant")
    tokensUsed: int = Field(0, description="Approximate token usage for this query")
    retrievedChunks: int = Field(0, description="Number of relevant database chunks retrieved")
    modelName: str = Field("Unknown", description="Model used to generate the answer")
    similarityScores: List[float] = Field(default_factory=list, description="Cosine similarity scores of retrieved chunks")

# Document Schemas
class DocItem(BaseModel):
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document text content")

class DocsList(BaseModel):
    documents: List[DocItem]

class DocUploadResponse(BaseModel):
    status: str
    inserted_documents: int
    total_chunks: int

# Health Schema
class HealthResponse(BaseModel):
    status: str
    database: str
    embedding_model: str
    llm_provider: str
