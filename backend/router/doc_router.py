# =============================================================
# doc_router.py — FastAPI REST API Endpoints
# =============================================================
# Defines all the HTTP endpoints that the frontend calls:
#   POST   /api/documents/upload     → Upload a document
#   GET    /api/documents/           → List all documents
#   GET    /api/documents/{id}       → Get document detail + chunks
#   POST   /api/documents/{id}/embed → Start embedding process
#   DELETE /api/documents/{id}       → Delete a document
# =============================================================

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from typing import List, Any, Dict

from backend.database import get_db
from backend.schema.document import (
    UploadResult,
    DocumentResponse,
    DocumentDetailResponse,
)
from backend.handler.doc_handler import (
    process_upload,
    get_all_documents_with_status,
    get_document_status,
    delete_document,
    extract_and_chunk_doc,
    embed_document,
    process_document
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


# ----- UPLOAD -----
@router.post("/upload", response_model=UploadResult)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
) -> UploadResult:
    """
    Upload a PDF, DOCX, or TXT file.
    Blocks duplicate content; renames if filename collides.
    """
    contents = await file.read()
    
    if not contents:
        raise HTTPException(status_code=400, detail="File is empty.")

    # file.filename can be None in some edge cases
    filename: str = file.filename or "untitled"

    status_code, message, doc = process_upload(db, filename, contents)

    # Build response
    doc_resp = None
    if doc is not None:

        # 3. Schedule background processing (Extract text & tables into Postgres)
        background_tasks.add_task(process_document, doc_id=doc.id, db=db)
        # pyrefly: ignore [bad-argument-type]
        st, vc = get_document_status(db, doc.id)
        doc_resp = DocumentResponse(
            id=doc.id,# pyrefly: ignore [bad-argument-type]
            filename=doc.filename,
            filepath=doc.filepath,
            filehash=doc.filehash,
            status=st,
            vector_count=vc,
            extracted_text=doc.extracted_text,
            tables_json=doc.tables_json or [],
        )


    return UploadResult(message=message, status=status_code, document=doc_resp)


# ----- LIST ALL -----
@router.get("/", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> List[DocumentResponse]:
    """Return all documents with their current status."""
    docs: List[Dict[str, Any]] = get_all_documents_with_status(db)
    return [
        DocumentResponse(
            id=d["id"],
            filename=d["filename"],
            filepath=d["filepath"],
            filehash=d["filehash"],
            status=d["status"],
            vector_count=d["vector_count"],
        )
        for d in docs
    ]


# ----- DETAIL VIEW -----
@router.get("/{doc_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    doc_id: int,
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    """Return document info + extracted chunks for the detail page."""
    try:
        data = extract_and_chunk_doc(db, doc_id)
        st, vc = get_document_status(db, doc_id)

        doc_resp = DocumentResponse(
            id=data["doc_id"],
            filename=data["filename"],
            filepath="",  # Not needed in detail view
            filehash="",  # Not needed in detail view
            status=st,
            vector_count=vc,
        )

        return DocumentDetailResponse(
            document=doc_resp,
            total_chunks=data["total_chunks"],
            chunks=data["chunks"],
            is_embedded=data["is_embedded"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- START EMBEDDING -----
@router.post("/{doc_id}/embed")
def trigger_embedding(
    doc_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate embeddings and store vectors in ChromaDB."""
    try:
        return embed_document(db, doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- DELETE -----
@router.delete("/{doc_id}")
def remove_document(
    doc_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Delete document from database, disk, and ChromaDB."""
    if not delete_document(db, doc_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": f"Document ID {doc_id} deleted."}
