
import os
from pathlib import Path
from dotenv import load_dotenv


# Load environment variables
load_dotenv()
# Find the project root directory (one level up from backend/)
BASE_DIR = Path(__file__).resolve().parent.parent



# --- Database URLs ---
# Format: postgresql://username:password@host:port/database_name


class Config:

    POSTGRES_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:root@localhost:5432/RAG_DB"
    )
    # Where the downloaded embedding model is saved locally
    MODELS_DIR = BASE_DIR / "models"
    # Path to the locally saved embedding model (avoids re-downloading)
    LOCAL_MODEL_PATH = MODELS_DIR / "all-MiniLM-L6-v2"

    # HuggingFace model name (free, runs locally, no API key needed)
    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    
    # ChromaDB collection name where vectors are stored
    CHROMA_COLLECTION_NAME = "rag_documents"


# --- Directory Paths ---

    # Where uploaded raw files are stored on disk
    STORAGE_DIR = BASE_DIR / "storage"

    # Where ChromaDB saves its vector database persistently
    CHROMA_DB_DIR = BASE_DIR / "chroma_db"


# Create these directories if they don't exist yet
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)



config = Config()