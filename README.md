# ⚡ RAG Data Ingestion Pipeline

A production-grade, modular RAG (Retrieval-Augmented Generation) document ingestion application featuring a Streamlit Dark Theme UI, FastAPI backend, PostgreSQL document metadata storage, and local ChromaDB vector store.

---

## 🌟 Key Features

1. **Smart File Deduplication Logic**:
   - **Identical Content (SHA-256 Hash Match)**: Upload is **blocked** immediately.
   - **Identical Filename, Different Content**: Upload is **allowed** with automatic filename disambiguation (`report.pdf` ➡️ `report (1).pdf`).
2. **PostgreSQL Document Store**: Stores document metadata `(id, filename, filepath, filehash)` without cluttering the database with raw extracted text.
3. **Smart Extraction & Chunking**:
   - Extracts text and tables from **PDF**, **DOCX**, and **TXT** files.
   - Preserves tables as **whole single chunks** to keep tabular data structured.
   - Uses **LangChain RecursiveCharacterTextSplitter** for text chunking.
4. **Local Embedding & Vector DB**:
   - **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (100% Free, runs locally).
   - **Vector Store**: **ChromaDB** persistent store (`chromadb.PersistentClient`).
   - **Persistence Fix**: Querying persistent ChromaDB for document IDs ensures restarting or re-running the app **never loses track** of indexed documents!
5. **Streamlit Dark Theme UI**:
   - **Card Grid View**: Displays documents in glowing card visual progress:
     - 🔴 **RED**: Uploaded / Processing
     - 🟡 **YELLOW**: Chunked (Ready to Embed)
     - 🟢 **GREEN**: Embedded in ChromaDB
   - **Card Delete Action**: Atomically removes document from Postgres DB, local disk storage, and ChromaDB.
   - **Detail Page View**: View extracted text & table chunks and click **🚀 Start Embedding** to process vectors.

---

## 📁 Directory Structure

```
Antigravity_workSpace/
├── backend/
│   ├── config.py             # App paths, DB URLs, & Model settings
│   ├── db/
│   │   ├── session.py        # Database connection engine & session maker
│   │   └── models.py         # SQLAlchemy Document model (id, filename, filepath, filehash)
│   ├── schema/
│   │   └── document.py       # Pydantic schemas
│   ├── util/
│   │   ├── hashing.py        # SHA-256 content hashing
│   │   └── file_utils.py     # Filename disambiguation logic ("filename (1).ext")
│   ├── handler/
│   │   ├── extractor.py      # PDF, DOCX, TXT text & table parser
│   │   ├── chunker.py        # Recursive text splitter + Table whole-chunking
│   │   ├── vector_store.py   # ChromaDB manager + sentence-transformers model
│   │   └── doc_handler.py    # Deduplication, Postgres DB ops, & status resolver
│   └── router/
│       └── doc_router.py     # FastAPI REST API endpoints
├── frontend/
│   ├── app.py                # Streamlit UI application
│   └── styles.css            # Dark Theme CSS stylesheet
├── storage/                  # Raw document files directory
├── chroma_db/                # Local ChromaDB persistent vector database
├── main.py                   # FastAPI server entrypoint
├── requirements.txt          # Dependencies list
└── README.md
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Database (Optional)
By default, the app uses standard PostgreSQL connection `postgresql://postgres:postgres@localhost:5432/rag_db`.
If local PostgreSQL is not running, it automatically falls back to local SQLite (`rag_app.db`) for seamless zero-setup execution.

### 3. Run FastAPI Backend

```bash
python main.py
```
*Backend API will run at `http://127.0.0.1:8000` (Swagger docs at `http://127.0.0.1:8000/docs`).*

### 4. Run Streamlit Frontend

```bash
streamlit run frontend/app.py
```
*Frontend UI will open automatically in your browser.*
