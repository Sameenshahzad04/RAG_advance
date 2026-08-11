# =============================================================
# main.py — FastAPI Application Entry Point
# =============================================================
# This is the file you run with: uvicorn main:app --reload
# It creates the FastAPI app and mounts all routes.
# =============================================================

import logging
from fastapi import FastAPI  # type: ignore
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from backend.router.doc_router import router as doc_router
from backend.router.chat_router import router as chat_router
# from backend.router.search_chunk import router as search_router
from backend.database import engine
from backend.models.documents import Document
from backend.database import Base
from fastapi.responses import FileResponse



# Setup logging so we can see what's happening in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


print("Using DB:", engine.url)
Base.metadata.create_all(bind=engine)
print("Tables created:", Base.metadata.tables.keys())
# Create the FastAPI application
app = FastAPI(title="RAG Data Ingestion Pipeline API")



# Allow Streamlit frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Register all document-related API routes
app.include_router(doc_router)
app.include_router(chat_router)  
#app.include_router(search_router)
@app.get("/")
def serve_frontend():
    """Serves the vanilla HTML/JS frontend."""
    return FileResponse("static/index.html")

@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint — confirms the API is running."""
    return {"status": "online", "service": "RAG Data Ingestion Pipeline API"}

# Allow running directly with: python main.py
if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
