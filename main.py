# =============================================================
# main.py — FastAPI Application Entry Point
# =============================================================
# This is the file you run with: uvicorn main:app --reload
# It creates the FastAPI app and mounts all routes.
# =============================================================

import logging
from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from backend.router.doc_router import router as doc_router
from backend.database import engine
from backend.models.documents import Document
from backend.database import Base

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

# Register all document-related API routes
app.include_router(doc_router)


@app.get("/")
def root() -> dict[str, str]:
    """Health check endpoint — confirms the API is running."""
    return {"status": "online", "service": "RAG Data Ingestion Pipeline API"}


# Allow running directly with: python main.py
if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
