import os
import logging
from typing import List
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger("rag_assistant")

# Singleton instance of the local model
_LOCAL_MODEL = None

def get_local_model():
    """Lazy load the sentence-transformers model to keep startup fast."""
    global _LOCAL_MODEL
    if _LOCAL_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers/all-MiniLM-L6-v2...")
            # This is a 90MB model, fast to load and run locally
            _LOCAL_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}. Falling back to mock embeddings.")
            _LOCAL_MODEL = "MOCK"
    return _LOCAL_MODEL

def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text based on provider settings.
    Supported: local (default), gemini, openai.
    """
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    
    if provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.embeddings.create(
                input=[text],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}. Falling back to local/mock.")
            # Fall back to local
            return _generate_local_embedding(text)
            
    elif provider == "gemini":
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY")
            # Fallback check if GEMINI_API_KEY is just the placeholder
            if not api_key or "your_" in api_key:
                # If there's an LLM_API_KEY, use it
                api_key = os.getenv("LLM_API_KEY")
            
            genai.configure(api_key=api_key)
            result = genai.embed_content(
                model="models/embedding-001",
                content=text
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Gemini embedding generation failed: {e}. Falling back to local/mock.")
            return _generate_local_embedding(text)
            
    else:
        return _generate_local_embedding(text)

def _generate_local_embedding(text: str) -> List[float]:
    """Helper to compute local SentenceTransformer embeddings."""
    model = get_local_model()
    if model == "MOCK":
        # Return a deterministic mock vector based on string hash for testing
        h = hash(text)
        np_rand = np_random_vector(h, 384)
        return np_rand.tolist()
    
    # Calculate embedding
    embedding = model.encode(text)
    return embedding.tolist()

def np_random_vector(seed: int, size: int) -> List[float]:
    """Generates a pseudo-random unit vector based on a seed."""
    import numpy as np
    state = np.random.RandomState(seed % (2**32))
    vec = state.randn(size)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()
