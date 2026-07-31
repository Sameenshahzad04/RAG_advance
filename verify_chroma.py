import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.handler.vector_store import vector_store

def verify_chroma_storage():
    collection = vector_store.collection
    results = collection.get(include=["embeddings", "documents", "metadatas"])

    ids = results.get("ids", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    embeddings = results.get("embeddings", [])

    print(f"\n========================================================")
    print(f" TOTAL STORED VECTORS IN CHROMADB: {len(ids)}")
    print(f"========================================================\n")

    for i in range(len(ids)):
        print(f"🔹 Point ID: {ids[i]}")
        print(f" ├── MetaData: {metadatas[i]}")
        print(f" ├── Chunk Text: {documents[i][:100]}...")
        if embeddings is not None and len(embeddings) > i:
            vec = embeddings[i]
            print(f" └── Vector: Dimension={len(vec)} | First 5 values={vec[:5]}")
        print("-" * 55)

if __name__ == "__main__":
    verify_chroma_storage()