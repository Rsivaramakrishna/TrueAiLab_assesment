# TrueAiLab_assesment
Production-Grade GenAI RAG Assistant
2. Architecture Diagram & Workflow
System Architecture
The application separates the static user interface and the python web backend, using SQLite for metadata and vector persistence.

Mermaid diagram
RAG Execution Sequence
Request: The browser sends a POST /api/chat request containing the user's message and session ID, authorized with a JWT Bearer token.
Scoping: The backend validates the JWT and scopes the sessionId to the verified username to isolate user chats.
Query Embedding: The embedding service embeds the user message using the local SentenceTransformers model.
Retrieval: The vector store queries the SQLite database, pulls all chunk coordinates, and calculates the Cosine Similarity between the query vector and chunk vectors.
Threshold Filter: Matches are filtered using a grounding threshold (0.35).
Fallback: If the similarity score of the best match is below the threshold, the system immediately returns a safe fallback message ("I could not find enough information in the knowledge base to answer this question."), bypassing the LLM call to save tokens and prevent hallucination.
Prompt Assembly: The top chunks are formatted into a context string. The chat history (last 3-5 message pairs) is retrieved from SQLite. Both are injected into the grounding prompt.
Generation: The prompt is sent to the dynamically resolved Gemini 3.5 Flash model with a temperature of 0.2 for deterministic, grounded results.
Save: The message pair is saved to the SQLite conversation log, and the API returns the grounded response, token metrics, and matching score diagnostics.
3. Core Technical Decisions
A. Embedding Strategy
Model: Local sentence-transformers/all-MiniLM-L6-v2 (384-dimensional dense vectors).
Decision Rationale: Running embeddings locally eliminates external API request overhead, is cost-free, and handles standard internal corporate document matching with high semantic fidelity.
Chunking Strategy: Word-based recursive sliding window chunking with a chunk size of 250 words and an overlap of 50 words (~300-350 tokens). The overlap preserves context boundaries across splits.
B. Similarity Search Logic
Metric: Cosine Similarity.
Formula: Cosine Similarity= 
∥A∥∥B∥
A⋅B
​
 = 
∑ 
i=1
n
​
 A 
i
2
​
 
​
  
∑ 
i=1
n
​
 B 
i
2
​
 
​
 
∑ 
i=1
n
​
 A 
i
​
 B 
i
​
 
​
 
Calibration: A threshold of 0.35 was calibrated specifically for the all-MiniLM-L6-v2 space. Query testing proves that out-of-scope prompts (e.g., "Who is the president?") match with scores <0.15 and are safely rejected, while in-scope prompts (e.g., "SSID coordinates") match with scores >0.55.
C. Prompt Design & Grounding
text


You are a helpful assistant.
Use ONLY the provided context to answer the user's question. If the context does not contain the answer, reply stating you don't have enough information. Do not use external facts.
Context:
{retrieved_context}
Conversation History:
{history}
Question:
{user_question}
Answer:
Reasoning: The system prompt forces constraints (restricting the model from hallucinating or retrieving pre-training knowledge). Using a low temperature (0.2) ensures the generator remains factual and behaves deterministically.
4. Implementation Features (Inc. Bonus)
Persistent Vector Store (SQLite): Persists raw text, title, document ID, and serialized embedding coordinates alongside chat history logs.
JWT Authentication: Implements standard password hashing via bcrypt and signed JWT session token generation using PyJWT (HS256).
Multi-Document Retrieval: Combines top-K matching chunks across multiple files in the SQLite database to compose a unified grounded answer.
Dynamic LLM Resolver: Queries Google AI Studio capabilities on boot to dynamically select the latest active flash model (resolving to gemini-3.5-flash or gemini-2.0-flash according to the key's region).
Simple Minimal UI: Clean, light-themed academic layout focusing on clarity, plain-text similarity score outputs, and a one-click guest startup wrapper.
5. Setup & Running Instructions
Install Dependencies:
bash


pip install -r requirements.txt
Configure Environment Variables: Create a .env file containing:
env


LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
EMBEDDING_PROVIDER=local
SIMILARITY_THRESHOLD=0.35
TOP_K=3
JWT_SECRET=stellar_tech_jwt_secret_key_1234567890
DATABASE_URL=sqlite:///./rag_assistant.db
Run Application:
bash


uvicorn app.main:app --host 127.0.0.1 --port 8000
Open http://127.0.0.1:8000 in the browser. Click "Quick Guest Start" to log in automatically.
