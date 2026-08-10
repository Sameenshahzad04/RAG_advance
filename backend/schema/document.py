# =============================================================
# document.py — Pydantic Schemas (Request/Response Models)
# =============================================================
# These classes define the shape of data sent to/from the API.
# FastAPI uses them to validate and serialize JSON responses.
# =============================================================

from pydantic import BaseModel, ConfigDict  # type: ignore
from typing import List, Optional,Any


class DocumentResponse(BaseModel):
    """Response schema for a single document."""
    id: int
    filename: str
    filepath: str
    filehash: str
    status: str           # "processing", "chunked", or "embedded"
    vector_count: Optional[int] = 0  # Number of vectors in ChromaDB
    extracted_text: Optional[str] = None
    tables_json: Optional[List[Any]] = []

    # Allows creating this model directly from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)


class UploadResult(BaseModel):
    """Response schema after uploading a document."""
    message: str          # Success or error message
    status: str           # "uploaded" or "duplicate_blocked"
    document: Optional[DocumentResponse] = None


class ChunkDetail(BaseModel):
    """Schema for a single text/table chunk extracted from a document."""
    index: int            # Chunk position number
    content: str          # The actual text content
    is_table: bool        # True if this chunk is a table
    char_length: int      # Character count of the content


class DocumentDetailResponse(BaseModel):
    """Response schema for the document detail page."""
    document: DocumentResponse
    total_chunks: int
    chunks: List[ChunkDetail]
    is_embedded: bool     # True if vectors exist in ChromaDB
