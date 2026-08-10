# =============================================================
# chunker.py — Text Chunking with LangChain
# =============================================================
# Splits extracted text into smaller chunks using LangChain's
# RecursiveCharacterTextSplitter.
#
# Rule: Tables are kept as ONE whole chunk (not split).
#       Text is split into ~500 character chunks with overlap.
# =============================================================

from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter  


def chunk_extracted_elements(
    elements: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Takes the output of extractor.py and produces numbered chunks.

    Args:
        elements: List of {"type": "text"/"table", "content": "..."}
        chunk_size: Max characters per text chunk
        chunk_overlap: Overlap between consecutive text chunks

    Returns:
        List of {"chunk_index": 0, "content": "...", "is_table": True/False}
    """
    # LangChain splitter for text — splits on paragraphs, then lines, then words
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    chunks: List[Dict[str, Any]] = []
    idx = 0  # Running chunk counter

    for item in elements:
        content = item.get("content", "")
        if not content or not content.strip():
            continue

        if item.get("type") == "table":
            # Tables stay as ONE whole chunk — don't split them
            chunks.append({
                "chunk_index": idx,
                "content": content,
                "is_table": True
            })
            idx += 1
        else:
            # Split text into smaller pieces using recursive splitter
            for piece in splitter.split_text(content):
                if piece.strip():
                    chunks.append({
                        "chunk_index": idx,
                        "content": piece.strip(),
                        "is_table": False
                    })
                    idx += 1

    return chunks
