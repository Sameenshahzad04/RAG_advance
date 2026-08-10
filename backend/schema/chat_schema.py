

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    message: str
    doc_id: Optional[int] = None
    top_k: int = 5
    conversation_history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    answer: str
    query: str
    count: int
    saved_files: Optional[str] = None