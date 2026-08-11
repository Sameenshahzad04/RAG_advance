
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import config
from backend.handler.vector_store import vector_store
import numpy as np
  
logger = logging.getLogger(__name__)



# Create 'chunk' directory at the root level of your project
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CHUNK_DIR = ROOT_DIR / "chunk"
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

import numpy as np
from typing import List

def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Manually calculates the cosine similarity between two vectors.
    Returns a float between -1.0 and 1.0 (higher means more similar).
    """
    # Convert lists to numpy arrays for fast math
    np_vec1 = np.array(vec1, dtype=float)
    np_vec2 = np.array(vec2, dtype=float)
    
    # Calculate Dot Product
    # Use float() to convert numpy dot product array/scalar into a native Python float
    dot_product = float(np.dot(np_vec1, np_vec2))
    
    # Calculate the magnitudes (norms) of both vectors
    # Convert norms into native Python floats check to cancel  text length biases
    norm1 = float(np.linalg.norm(np_vec1))
    norm2 = float(np.linalg.norm(np_vec2))
    
    # Prevent division by zero
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
   
        
    return dot_product / (norm1 * norm2)


def retrieve_chunks(
    query: str,
    top_k: int = None,
    doc_id: Optional[int] = None
) -> Dict[str, Any]:
    """Retrieve relevant chunks from ChromaDB."""
    
    if top_k is None:
        top_k = config.RAG_TOP_K
    
    logger.info(f"🔍 Retrieving top {top_k} chunks...")
    
    # query_embedding = vector_store.embed_model.encode([query]).tolist()[0]
   
    # CHANGED: Call the new helper method directly, extract first item [0], and remove .tolist()
    # query_embedding = vector_store._get_openrouter_embeddings([query])[0]
    embeddings_result = vector_store._get_openrouter_embeddings([query])
    if not embeddings_result:
        logger.error("❌ Failed to generate embedding for the query.")
        return {"query": query, "chunks": [], "count": 0}
        
    query_embedding = embeddings_result[0]
    where_filter = {"doc_id": doc_id} if doc_id else None
    
    # Dynamically build arguments to avoid passing where=None
    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents"]
    }
    if where_filter:
        query_kwargs["where"] = where_filter
    
    try:
        # 2. Fetch ALL vectors, documents, and metadatas from ChromaDB
        include_fields = ["embeddings", "documents", "metadatas"] if doc_id else ["embeddings", "documents"]
        results = vector_store.collection.get(include=include_fields)
        
        scored_chunks = []
        
        if results and "embeddings" in results and results["embeddings"] is not None:
            for i in range(len(results["ids"])):
                # 3. Filter by doc_id if provided
                if doc_id:
                    metadata = results["metadatas"][i]
                    if not metadata or metadata.get("doc_id") != doc_id:
                        continue
                
                # 4. Calculate similarity between query and stored chunk vector
                doc_embedding = results["embeddings"][i]
                similarity = calculate_cosine_similarity(query_embedding, doc_embedding)
                
                # Optional: Filter out low-similarity chunks (e.g., threshold > 0.3)
                if similarity > 0.2:
                    scored_chunks.append({
                        "document": results["documents"][i],
                        "similarity": similarity
                    })
                # scored_chunks.append({
                #     "document": results["documents"][i],
                #     "similarity": similarity
                # })
        
        # 5. Sort matches by highest score and take top_k
        scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
        top_chunks = [item["document"] for item in scored_chunks[:top_k]]
        
        logger.info(f"✅ Retrieved {len(top_chunks)} chunks manually")
        
        # Add this return block!
        return {
            "query": query,
            "chunks": top_chunks,
            "count": len(top_chunks)
        }


        # similarity search using chroma loacal mechnisam  
        # # Pass the unpacked arguments dictionary
        # results = vector_store.collection.query(**query_kwargs)
        
        # chunks = []
        # if results and results.get("documents"):
        #     chunks = results["documents"][0]
        
        # logger.info(f"✅ Retrieved {len(chunks)} chunks")


        # #manually using
        # return {
        #     "query": query,
        #     "chunks": chunks,
        #     "count": len(chunks)
        # }


    
    except Exception as e:
        logger.error(f"❌ ChromaDB error: {e}")
        return {"query": query, "chunks": [], "count": 0}


def build_context(chunks: List[str]) -> str:
    """Combine chunks into context."""
    if not chunks:
        return "NO_CONTEXT_AVAILABLE"
    return "\n\n---\n\n".join(chunks)


def call_llm(
    context: str,
    query: str,
    conversation_history: List[dict] = None
) -> str:
    """Send context + query to LLM."""
    
    logger.info("📞 Calling OpenRouter API...")
    
    if not config.API_KEY:
        logger.error("❌ API_KEY is empty!")
        return "Error: API key not configured."
    
#     # Build prompt
#     system_prompt = f"""You are a helpful assistant. Answer using ONLY the context below.

# CONTEXT:
# {context}

# INSTRUCTIONS:
# - Use ONLY the context above
# - If answer not in context, say "I don't have information about that in the provided documents."
# - If the user asks to summarize then follow the instruction and return the summary for the provided context.
# - Be concise
# """
    


    system_prompt = f"""You are a precise and reliable technical assistant. Your task is to answer user queries or summarize information strictly based on the provided CONTEXT.

### CONTEXT:
{context}

### INSTRUCTIONS:
1. **Strict Grounding:** Base your response EXCLUSIVELY on the facts present in the CONTEXT above. Do not use outside knowledge, assumptions, or extrapolation.
2. **Handling Missing Data:** If the answer cannot be found in the CONTEXT, you must respond with: "I don't have information about that in the provided documents."
3. **Summarization Rule:** If the user explicitly asks for a summary, synthesize the core points entirely from the CONTEXT. Never summarize outside information or ignore the context.
4. **Tone and Length:** Be concise, direct, and objective. Eliminate conversational filler.
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    if conversation_history:
        messages.extend(conversation_history[-5:])
    
    messages.append({"role": "user", "content": query})
    
    try:
        logger.info(f"📡 URL: {config.BASE_URL}")
        logger.info(f"🤖 Model: {config.OPEN_MODEL}")
        
        response = requests.post(
            config.BASE_URL,
            headers={
                "Authorization": f"Bearer {config.API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "RAG Chatbot"
            },
            json={
                "model": config.OPEN_MODEL,
                "messages": messages,
                "max_tokens": config.RAG_MAX_TOKENS,
                "temperature": 0.3
            },
            timeout=120  # Increased timeout (was 60)
        )
        
        logger.info(f"📥 Status: {response.status_code}")
        if response.status_code == 200:
            res_data = response.json()
            
            # Safely extract response depending on what keys are available because very online free mode  have different keuys 
            if "choices" in res_data and len(res_data["choices"]) > 0:
                answer = res_data["choices"][0]["message"]["content"]
            elif "message" in res_data:
                answer = res_data["message"]
            elif "response" in res_data:
                answer = res_data["response"]
            else:
                # Fallback if it returns raw text or unexpected dict
                answer = str(res_data)
                
            logger.info("✅ Got answer")

            logger.info(answer)
            return answer
        else:
            logger.error(f"❌ API error: {response.text}")
            return f"Error: Status {response.status_code}"
            
    except requests.exceptions.Timeout:
        logger.error("⏰ Timeout (120s)")
        return "Error: Request timed out. The model may be busy. Try again."
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return f"Error: {str(e)}"


def rag_retrieval(
    query: str,
    top_k: int = None,
    doc_id: Optional[int] = None,
    conversation_history: List[dict] = None
) -> Dict[str, Any]:
    """Complete RAG retrieval."""
    
    results = retrieve_chunks(query, top_k, doc_id)
    context = build_context(results["chunks"])
    _save_chunks_to_file(query, results["chunks"])
    answer = call_llm(context, query, conversation_history)
    
    return {
        "answer": answer,
        "query": query,
        "count": results["count"]
    }
def _save_chunks_to_file(query: str, chunks: List[str]) -> Path:
    """Helper function to create a .txt file inside the 'chunk' folder and log info."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = CHUNK_DIR / f"chunk_{timestamp}.txt"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"=== RETRIEVED CHUNKS LOG ===\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Query: {query}\n")
        f.write(f"Total Chunks: {len(chunks)}\n")
        f.write("=" * 60 + "\n\n")
        
        for idx, chunk in enumerate(chunks, 1):
            f.write(f"--- CHUNK {idx} ---\n")
            f.write(f"{chunk}\n\n")

    # Logger notification in terminal
    logger.info(f"📁 [SUCCESS] Created chunk file at: {file_path}")
    return file_path