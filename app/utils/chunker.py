import re
from typing import List

def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 50) -> List[str]:
    """
    Splits text into chunks of specified word length with overlap.
    Averages around 300-400 tokens per chunk.
    """
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split(' ')
    
    if len(words) <= chunk_size_words:
        return [text]
    
    chunks = []
    i = 0
    while i < len(words):
        # Slice words for the chunk
        chunk_words = words[i:i + chunk_size_words]
        chunk_text = " ".join(chunk_words)
        chunks.append(chunk_text)
        
        # Advance with overlap
        i += (chunk_size_words - overlap_words)
        
        # Avoid infinite loops or tiny final chunks
        if i >= len(words) - overlap_words:
            # If the remaining words are less than overlap, add them and stop
            if i < len(words):
                last_chunk = " ".join(words[i:])
                if len(last_chunk.split()) > 10:  # Only add if it's meaningful
                    chunks.append(last_chunk)
            break
            
    return chunks
