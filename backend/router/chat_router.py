# ============================================================
# backend/router/chat_router.py — FastAPI Chat Endpoints
# ============================================================

from fastapi import APIRouter, HTTPException
import logging
from typing import List, Dict, Any, Optional

from backend.schema.chat_schema import ChatRequest, ChatResponse
from backend.handler.retrieval_handler import rag_retrieval

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat with your uploaded documents.
    
    Full endpoint: POST /api/chat/
    """
    logger.info(f"💬 Chat request received: {request.message[:50]}...")
    logger.info(f"   Top K: {request.top_k}")
    logger.info(f"   Doc ID: {request.doc_id}")
    
    try:
        # Ensure top_k is at least 1 and defaults to 20
        top_k = request.top_k if request.top_k else 20
        
        result = rag_retrieval(
            query=request.message,
            top_k=top_k,
            doc_id=request.doc_id,
            conversation_history=request.conversation_history
        )
        
        logger.info(f"✅ Chat response generated")
        # logger.info(f"   Answer length: {len(result['answer'])} chars")
        logger.info(f"   Chunks used: {result['count']}")
        
        return ChatResponse(
            answer=result["answer"],
            query=result["query"],
            count=result["count"],
            saved_file=result.get("saved_file")
        )
        
    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
def test_endpoint():
    """Test endpoint to verify router is working."""
    logger.info("🧪 Test endpoint called")
    return {"status": "ok", "message": "Chat router is working!"}