
# Manages the ChromaDB persistent vector database and the local
# sentence-transformers embedding model.
#
# On first run: downloads the model and saves it to ./models/
# On subsequent runs: loads directly from disk (no internet needed)

from PIL.Image import logger
import logging
from typing import List, Dict, Any, Union
import requests
import chromadb  
# from sentence_transformers import SentenceTransformer  
from backend.config import config



# Type alias for ChromaDB metadata values (must be primitive types)
MetadataValue = Union[str, int, float, bool]


class VectorStoreManager:
    """
    Handles all ChromaDB operations:
    - Adding document chunks with embeddings
    - Checking if a document is already embedded
    - Counting vectors for a document
    - Deleting vectors for a document
    """

    def __init__(self) -> None:
        # Connect to ChromaDB (persistent = saved to disk, survives restarts)
        self.chroma_client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))

        # Get or create the collection where we store vectors
        self.collection = self.chroma_client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            metadata={"description": "RAG Document Vectors"}
        )

        # # Load the embedding model from local disk or download it
        # if config.LOCAL_MODEL_PATH.exists() and any(config.LOCAL_MODEL_PATH.iterdir()):
        #     self.embed_model = SentenceTransformer(str(config.LOCAL_MODEL_PATH))
        # else:
        #     self.embed_model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
        #     # Save model to disk so we never need to download again
        #     self.embed_model.save(str(config.LOCAL_MODEL_PATH))




    def _get_openrouter_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Helper method to fetch embeddings directly from OpenRouter API using config variables."""
        if not config.API_KEY:
            raise ValueError("OpenRouter API Key is missing in config.")
            
        # Fallback to the free model if it's not set in the .env
        model = config.OPENROUTER_EMBEDDING_MODEL
        
        # Standard OpenRouter endpoint for embeddings
        url = "https://openrouter.ai/api/v1/embeddings"
        
        headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501", # Optional, but good practice for OpenRouter
            "X-Title": "RAG Chatbot"
        }
        
        all_embeddings = []
        batch_size = 128  # Safe limit under the 256 maximum threshold
        
               # Loop through texts in batches of 128
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            payload = {
                "model": model,
                "input": batch_texts
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=300)
            
            if response.status_code == 200:
                data = response.json()
                # Sort to ensure the embedding order matches the input text order
                items = sorted(data.get("data", []), key=lambda x: x["index"])
                all_embeddings.extend([item["embedding"] for item in items])
            else:
                logger.error(f"Embedding failed: {response.text}")
                raise Exception(f"OpenRouter API Error {response.status_code}: {response.text}")

        return all_embeddings

    def add_document_chunks(
        self,
        doc_id: int,
        filename: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Generate embeddings for all chunks and store them in ChromaDB.
        Returns the number of vectors stored.
        """
        if not chunks:
            return 0

        # If re-embedding, remove old vectors first
        self.delete_document_vectors(doc_id)

        # Prepare data for ChromaDB
        texts: List[str] = [str(c["content"]) for c in chunks]
        ids: List[str] = [f"doc_{doc_id}_chunk_{c['chunk_index']}" for c in chunks]
        metadatas: List[Dict[str, Any]] = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": int(c["chunk_index"]),
                "is_table": bool(c["is_table"]),
            }
            for c in chunks
        ]

        # Generate embeddings using the local model
        # embeddings = self.embed_model.encode(texts, show_progress_bar=False).tolist()

        embeddings = self._get_openrouter_embeddings(texts)
        # Store everything in ChromaDB
        self.collection.add(  # type: ignore[arg-type]
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,# pyrefly: ignore
        )
        return len(ids)

    def is_document_embedded(self, doc_id: int) -> bool:
        """Check if any vectors exist in ChromaDB for this document."""
        results = self.collection.get(where={"doc_id": doc_id})
        ids = results.get("ids", []) if results else []
        return len(ids) > 0  # type: ignore[arg-type]

    def get_document_vector_count(self, doc_id: int) -> int:
        """Count how many vector chunks exist in ChromaDB for this document."""
        results = self.collection.get(where={"doc_id": doc_id})
        ids = results.get("ids", []) if results else []
        return len(ids)  # type: ignore[return-value]

    def delete_document_vectors(self, doc_id: int) -> None:
        """Remove all vectors for a document from ChromaDB."""
        try:
            results = self.collection.get(where={"doc_id": doc_id})
            ids = results.get("ids", []) if results else []
            if ids:
                self.collection.delete(ids=ids)
        except Exception as e:
            logger.error(f"Error deleting vectors for doc_id={doc_id}: {e}")


# Create a single shared instance (singleton pattern)
vector_store = VectorStoreManager()
