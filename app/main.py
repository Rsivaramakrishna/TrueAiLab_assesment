import os
import json
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.vectorstore import database as db
from app.routes import auth, chat, docs, health
from app.routes.docs import index_document_content

load_dotenv(override=True)

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rag_assistant")

app = FastAPI(
    title="Production-Grade RAG Assistant",
    description="FastAPI + SQLite Vector Search RAG Chatbot with JWT & Persistent DB.",
    version="1.0.0"
)

# CORS configurations for local frontend development or domain access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(docs.router)

# Database Table Initialization & Bootstrapping
@app.on_event("startup")
def startup_db_setup():
    logger.info("Initializing database...")
    db.init_db()
    
    # Check if we have documents indexed. If empty, bootstrap from docs.json
    try:
        existing_docs = db.get_all_documents()
        if not existing_docs:
            logger.info("Database is empty. Bootstrapping knowledge base from docs.json...")
            docs_path = "docs.json"
            if os.path.exists(docs_path):
                with open(docs_path, "r", encoding="utf-8") as f:
                    docs_data = json.load(f)
                
                for doc in docs_data:
                    title = doc.get("title", "Untitled")
                    content = doc.get("content", "").strip()
                    if content:
                        doc_id = db.insert_document(title, content)
                        index_document_content(doc_id, title, content)
                logger.info("Bootstrapping complete. Default documents indexed.")
            else:
                logger.warning("docs.json file not found in workspace root. Skipping bootstrapping.")
        else:
            logger.info(f"Database contains {len(existing_docs)} documents. Skipping bootstrap.")
    except Exception as e:
        logger.error(f"Error during bootstrapping: {e}", exc_info=True)

# Exception handlers for structured production error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": f"An internal server error occurred: {str(exc)}"}
    )

# Serve Frontend static assets
# Ensure the 'frontend' directory exists before mounting to avoid errors
frontend_dir = "frontend"
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)
    
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
