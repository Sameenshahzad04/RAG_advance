#   1. Upload with deduplication (hash check + filename rename)
#   2. Document status detection (RED/YELLOW/GREEN)
#   3. Text extraction & chunking
#   4. Embedding generation & ChromaDB storage
#   5. Document deletion (DB + disk + ChromaDB cleanup)

import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from sqlalchemy.orm import Session
from backend.config import config
from backend.models.documents import Document
from backend.util.hashing import compute_sha256
from backend.util.file_utils import get_disambiguated_filename
from backend.handler.extractor import extract_content
from backend.handler.chunker import chunk_extracted_elements
from backend.handler.vector_store import vector_store

logger = logging.getLogger(__name__)

# Root folder where per-document chunk dumps are written, one
# subfolder per document, BEFORE embedding happens. Lets you
# inspect exactly what text is about to be turned into vectors.

# Create 'chunk_output' directory at the root level of your project
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CHUNK_DIR = ROOT_DIR / "chunk_output"
CHUNK_DIR.mkdir(parents=True, exist_ok=True)


def _safe_folder_name(filename: str) -> str:
    """Turn a filename like 'HR Policy (1).pdf' into a safe folder name."""
    stem = Path(filename).stem
    return re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "document"


def save_chunks_to_folder(doc_id: int, filename: str, chunks: List[Dict[str, Any]]) -> Path:
    """
    Write every chunk for this document to its own folder on disk,
    BEFORE embedding. One file per chunk, plus a summary index file.

    Layout:
        chunk_output/
            <doc_id>_<safe_filename>/
                index.txt                (summary of all chunks)
                chunk_0000_text.txt
                chunk_0001_table.txt
                ...
    """
    folder_name = f"{doc_id}_{_safe_folder_name(filename)}"
    doc_folder = CHUNK_DIR / folder_name
    doc_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    index_lines = [
        f"Document: {filename} (doc_id={doc_id})",
        f"Generated: {timestamp}",
        f"Total chunks: {len(chunks)}",
        "=" * 60,
    ]

    for c in chunks:
        kind = "table" if c["is_table"] else "text"
        chunk_filename = f"chunk_{c['chunk_index']:04d}_{kind}.txt"
        chunk_path = doc_folder / chunk_filename
        with open(chunk_path, "w", encoding="utf-8") as f:
            f.write(c["content"])

        index_lines.append(
            f"[{c['chunk_index']:04d}] {kind:5s} | {len(c['content'])} chars | {chunk_filename}"
        )

    index_path = doc_folder / "index.txt"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    logger.info(f"📁 Saved {len(chunks)} chunks for doc_id={doc_id} to {doc_folder}")
    return doc_folder


def check_duplicate(file_hash: str, db: Session) -> bool:
    """Check if file with same content exists."""
    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    return existing is not None


# ----- 1. UPLOAD WITH DEDUPLICATION -----

def process_upload(
    db: Session,
    original_filename: str,
    file_bytes: bytes
) -> Tuple[str, str, Optional[Document]]:
    """
    Upload a document with smart deduplication:
    - Same CONTENT (hash match) → BLOCK upload
    - Same FILENAME but different content → Allow, rename to "file (1).pdf"
    - New file → Allow as-is

    Returns: (status_string, message, document_or_none)
    """
    # Calculate SHA-256 hash of the file content
    file_hash: str = compute_sha256(file_bytes)

    # Check if a document with identical content already exists
    duplicate = db.query(Document).filter(Document.filehash == file_hash).first()
    if duplicate is not None:
        return (
            "duplicate_blocked",
            f"Blocked! Content is identical to existing file '{duplicate.filename}'.",
            None,
        )

    # Check if filename already exists → rename if needed
    all_docs = db.query(Document).all()
    existing_names: set[str] = {str(d.filename) for d in all_docs}
    final_filename: str = get_disambiguated_filename(original_filename, existing_names)

    # Save the file to the storage/ directory on disk
    filepath: str = os.path.join(str(config.STORAGE_DIR), final_filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    # Create a new row in the documents table
    doc = Document(
        filename=final_filename,
        filepath=filepath,
        filehash=file_hash,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)  # Reload to get the auto-generated ID

    return ("uploaded", f"Successfully uploaded as '{final_filename}'.", doc)


def process_document(doc_id: int, db: Session) -> Document:
    """
    Extracts text and tables from the file on disk and updates PostgreSQL.
    Can be called directly or run as a FastAPI BackgroundTask.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc or not os.path.exists(doc.filepath):
        raise ValueError(f"Document with ID {doc_id} not found.")

    # Extract elements from disk file
    elements = extract_content(doc.filepath)

    # Separate text and table content
    all_text = [el["content"] for el in elements if el.get("type") == "text"]
    all_tables = [
        {"content": el["content"], "type": "table"}
        for el in elements if el.get("type") == "table"
    ]

    # Save extraction results into PostgreSQL
    doc.extracted_text = "\n\n".join(all_text)
    doc.tables_json = all_tables
    db.commit()
    db.refresh(doc)

    return doc


# ----- 2. DOCUMENT STATUS DETECTION -----

def get_document_status(db: Session, doc_id: int) -> Tuple[str, int]:
    """
    Determine document status dynamically:
    - GREEN  "embedded"   → Vectors exist in ChromaDB
    - YELLOW "chunked"    → File exists on disk, ready for embedding
    - RED    "processing" → Just uploaded, file might be missing

    Returns: (status_string, vector_count)
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        return ("not_found", 0)

    # Check ChromaDB for existing vectors
    if vector_store.is_document_embedded(doc_id):
        count = vector_store.get_document_vector_count(doc_id)
        return ("embedded", count)

    # File exists on disk → it can be chunked/embedded
    if os.path.exists(str(doc.filepath)):
        return ("chunked", 0)

    return ("processing", 0)


# ----- 3. LIST ALL DOCUMENTS WITH STATUS -----

def get_all_documents_with_status(db: Session) -> List[Dict[str, Any]]:
    """Get all documents from DB with their current status."""
    docs = db.query(Document).order_by(Document.id.desc()).all()
    result: List[Dict[str, Any]] = []

    for d in docs:
        # pyrefly: ignore [bad-argument-type]
        status, v_count = get_document_status(db, d.id)
        result.append({
            "id": d.id,
            "filename": d.filename,
            "filepath": d.filepath,
            "filehash": d.filehash,
            "status": status,
            "vector_count": v_count,
        })

    return result


# ----- 4. DELETE DOCUMENT -----

def delete_document(db: Session, doc_id: int) -> bool:
    """
    Delete a document completely:
    1. Remove vectors from ChromaDB
    2. Remove file from disk
    3. Remove row from database
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        return False

    # Step 1: Remove vectors from ChromaDB
    vector_store.delete_document_vectors(doc_id)

    # Step 2: Remove file from disk
    if os.path.exists(str(doc.filepath)):
        try:
            os.remove(str(doc.filepath))
        except Exception as e:
            raise ValueError(f"Error deleting file from disk: {e}")

    # Step 3: Remove from database
    db.delete(doc)
    db.commit()
    return True


# ----- 5. EXTRACT & CHUNK DOCUMENT -----

def extract_and_chunk_doc(db: Session, doc_id: int) -> Dict[str, Any]:
    """
    Extract text/tables from the document file and split into chunks.
    Used for the detail page view.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None or not os.path.exists(str(doc.filepath)):
        raise ValueError(f"Document ID {doc_id} not found on disk.")

    # Extract text and tables from the file
    elements = extract_content(str(doc.filepath))

    # 2. Separate text and table content
    all_text = [el["content"] for el in elements if el.get("type") == "text"]
    all_tables = [
        {"content": el["content"], "type": "table"}
        for el in elements if el.get("type") == "table"
    ]

    # 3. Save to PostgreSQL
    doc.extracted_text = "\n\n".join(all_text)
    doc.tables_json = all_tables
    db.commit()
    db.refresh(doc)

    # Split into chunks (tables stay whole, text gets split)
    chunks = chunk_extracted_elements(elements)

    # Build detailed info for each chunk
    chunk_details: List[Dict[str, Any]] = [
        {
            "index": c["chunk_index"],
            "content": c["content"],
            "is_table": c["is_table"],
            "char_length": len(c["content"]),
        }
        for c in chunks
    ]

    return {
        "doc_id": doc.id,
        "filename": doc.filename,
        "total_chunks": len(chunks),
        "chunks": chunk_details,
        "is_embedded": vector_store.is_document_embedded(doc_id),
        "raw_chunks": chunks,  # Needed internally by embed_document()
    }


# ----- 6. EMBED DOCUMENT INTO CHROMADB -----

def embed_document(db: Session, doc_id: int) -> Dict[str, Any]:
    """
    Called when user clicks "Start Embedding" button.
    Extracts text → chunks it → generates embeddings → stores in ChromaDB.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc is None:
        raise ValueError(f"Document ID {doc_id} does not exist.")

    # Extract and chunk the document
    extracted = extract_and_chunk_doc(db, doc_id)

    # Save every chunk to disk BEFORE embedding, so you can inspect
    # exactly what text is about to be vectorized.
    save_chunks_to_folder(
        doc_id=doc.id,
        filename=doc.filename,
        chunks=extracted["raw_chunks"],
    )

    # Generate embeddings and store in ChromaDB
    vectors_stored = vector_store.add_document_chunks(
        doc_id=doc.id,
        filename=doc.filename,
        chunks=extracted["raw_chunks"],
    )

    return {
        "message": f"Embedded '{doc.filename}' with {vectors_stored} vectors in ChromaDB.",
        "doc_id": doc.id,
        "vectors_stored": vectors_stored,
        "status": "embedded",
    }