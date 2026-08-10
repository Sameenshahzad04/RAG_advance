# ============================================================
# backend/config.py — Configuration Settings
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# ===== FIND .env FILE =====
# Current file location: backend/config.py
# .env is in: AI/.env (2 levels up from config.py)

# Get the path to backend/ folder
BACKEND_DIR = Path(__file__).resolve().parent

# Get the path to project root (where main.py is)
PROJECT_ROOT = BACKEND_DIR.parent

# Get the path to AI/ folder (where .env actually is)
ENV_DIR = PROJECT_ROOT.parent

# Try to load .env from multiple locations
env_loaded = False

# Try 1: Project root (AI/Antigravityworksapec/.env)
if (PROJECT_ROOT / ".env").exists():
    load_dotenv(PROJECT_ROOT / ".env")
    env_loaded = True
    print(f"✅ Loaded .env from: {PROJECT_ROOT / '.env'}")

# Try 2: AI/ folder (AI/.env)
elif (ENV_DIR / ".env").exists():
    load_dotenv(ENV_DIR / ".env")
    env_loaded = True
    print(f"✅ Loaded .env from: {ENV_DIR / '.env'}")

# Try 3: Current directory
else:
    load_dotenv()
    print(f"⚠️ Loaded .env from current directory (may not exist)")

if not env_loaded:
    print("❌ WARNING: No .env file found!")

BASE_DIR = PROJECT_ROOT


class Config:
    """All configuration settings."""

    # Database
    POSTGRES_DB_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:root@localhost:5432/RAG_DB"
    )

    # Embedding Model
    MODELS_DIR = BASE_DIR / "models"
    LOCAL_MODEL_PATH = MODELS_DIR / "all-MiniLM-L6-v2"
    # EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    OPENROUTER_EMBEDDING_MODEL = os.getenv("OPENROUTER_EMBEDDING_MODEL")

    # ChromaDB
    CHROMA_COLLECTION_NAME = "rag_documents"
    CHROMA_DB_DIR = BASE_DIR / "chroma_db"

    # File Storage
    STORAGE_DIR = BASE_DIR / "storage"

    # LLM (OpenRouter API)
    # OPEN_MODEL = os.getenv("OPENROUTER_MODEL", "cohere/north-mini-code:free")
    OPEN_MODEL = os.getenv("OPENROUTER_MODEL")
    API_KEY = os.getenv("OPENROUTER_API_KEY")
    # BASE_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
    BASE_URL = os.getenv("OPENROUTER_URL")
    # RAG Configuration
    RAG_TOP_K: int = 20
    RAG_MAX_TOKENS: int = 1024

    # Create directories
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ===== DEBUG: Print config on load =====
    print(f"\n{'='*60}")
    print(f"✅ Config loaded:")
    print(f"   - API_KEY present: {bool(API_KEY)}")
    print(f"   - API_KEY length: {len(API_KEY) if API_KEY else 0}")
    # print(f"   - API_KEY starts with: {API_KEY[:15] + '...' if API_KEY and len(API_KEY) > 15 else 'N/A'}")
    print(f"   - BASE_URL: {BASE_URL}")
    print(f"   - MODEL: {OPEN_MODEL}")
    print(f"   - TOP_K: {RAG_TOP_K}")
    print(f"   - OPENROUTER_EMBEDDING_MODEL: {OPENROUTER_EMBEDDING_MODEL}")
    print(f"{'='*60}\n")


config = Config()