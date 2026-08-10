import sys
from pathlib import Path
import streamlit as st
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# FastAPI backend URL
API_BASE = "http://localhost:8000/api"
@st.cache_data(ttl=30)  # re-fetch at most once every 30 seconds, not every rerun
def get_docs_safe() -> list:
    """Fetch all uploaded documents to populate the dropdown context selector."""
    try:
        res = requests.get(f"{API_BASE}/documents/", timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, list) else data.get("documents", [])
    except Exception:
        pass
    return []

def extract_chunk_list(data: dict) -> list:
    """Extracts chunks from common backend RAG response formats."""
    raw_chunks = (
        data.get("retrieved_chunks") 
        or data.get("chunks") 
        or data.get("context_chunks") 
        or data.get("sources") 
        or data.get("context") 
        or []
    )
    
    normalized = []
    if isinstance(raw_chunks, list):
        for idx, item in enumerate(raw_chunks, start=1):
            if isinstance(item, str):
                normalized.append({
                    "chunk_id": f"chunk_{idx}",
                    "content": item,
                    "page": "N/A",
                    "similarity_score": "N/A"
                })
            elif isinstance(item, dict):
                content = (
                    item.get("content") 
                    or item.get("text") 
                    or item.get("document") 
                    or item.get("page_content") 
                    or ""
                )
                meta = item.get("metadata", {})
                page = item.get("page", meta.get("page", "N/A"))
                score = item.get("similarity_score", item.get("score", meta.get("score", "N/A")))
                
                normalized.append({
                    "chunk_id": item.get("chunk_id", f"chunk_{idx}"),
                    "content": content,
                    "page": page,
                    "similarity_score": score
                })
    return normalized

def render_error(message: str) -> None:
    """Custom error renderer to strictly avoid default red colors."""
    st.markdown(
        f"""
        <div style="background-color: #1A0D33; color: #F8F9FA; border: 1px solid #A855F7; 
        padding: 12px; border-radius: 8px; margin-bottom: 12px;">
            {message}
        </div>
        """,
        unsafe_allow_html=True
    )

def render_chat_page() -> None:
    # Top Header & Single Navigation Back Button
    nav_col, title_col = st.columns([1, 4])
    with nav_col:
        if st.button("⬅️ Back to Dashboard", use_container_width=True):
            st.session_state["page"] = "dashboard"
            st.rerun()

    with title_col:
        st.markdown("<h3 style='margin:0; padding-top:4px;'>💬 Knowledge Base Chat</h3>", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

    # Document Selection Controls
    c1, c2, c3 = st.columns([3, 1.5, 1])

    docs = get_docs_safe()
    doc_options = {"All Documents": None}
    for d in docs:
        fname = d.get("filename") or d.get("file_name") or f"Doc #{d.get('id')}"
        doc_options[f"📄 {fname}"] = d.get("id")

    with c1:
        selected_label = st.selectbox(
            "Document Context",
            options=list(doc_options.keys()),
            label_visibility="collapsed"
        )
        selected_doc_id = doc_options[selected_label]

    with c2:
        top_k = st.slider(
            "Top-K Chunks",
            min_value=1,
            max_value=30,
            value=20,  # Default to 20 context chunks
            step=1,
            label_visibility="collapsed",
            help="Number of cosine vector matches to search"
        )

    with c3:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown("<hr style='margin: 10px 0 15px 0; border-color: #28164C;'>", unsafe_allow_html=True)

    # Session State Initialization
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display Conversation History & Retrieved Chunks
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if message["role"] == "assistant":
                if "count" in message:
                    st.caption(f"📊 Retrieved Context: {message['count']} chunks")
                
                # Render inline retrieved context accordion for assistant messages
                msg_chunks = message.get("retrieved_chunks", [])
                if msg_chunks:
                    with st.expander(f"🔍 Inspect {len(msg_chunks)} Context Chunks Used"):
                        for c_idx, c in enumerate(msg_chunks, start=1):
                            p = c.get("page", "N/A")
                            s = c.get("similarity_score", "N/A")
                            if isinstance(s, (int, float)):
                                s = f"{round(s * 100, 1)}%" if s <= 1.0 else f"{round(s, 1)}%"
                            
                            st.markdown(f"**Chunk {c_idx} (Page {p} | Score: {s}):**")
                            st.code(c.get("content", ""), language=None)

    # Handle User Query Input
    if prompt := st.chat_input("Ask about your documents..."):
        # Display User Input
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call Backend RAG Pipeline
        with st.chat_message("assistant"):
            with st.spinner("🔍 Embedding query & running cosine vector retrieval..."):
                try:


                    # Build last-5-message history from what's already in session state,
                    # excluding the question we're about to ask (that gets added separately)
                    history_for_model = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[:-1][-5:]
                    ]
                    # Construct precise ChatRequest schema matching backend router
                    payload = {
                        "message": prompt,
                        "top_k": top_k,
                        "doc_id": selected_doc_id,  # Passes int ID or None for all docs
                        "conversation_history": history_for_model
                    }

                    # Execute HTTP POST request to FastAPI endpoint
                    response = requests.post(
                        f"{API_BASE}/chat/",
                        json=payload,
                        timeout=120
                    )

                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("answer", "No answer generated by LLM.")
                        
                        # Extract chunks safely for UI rendering
                        retrieved_chunks = extract_chunk_list(data)
                        count = data.get("count", len(retrieved_chunks))

                        # If zero chunks retrieved, warn explicitly without red
                        if count == 0 and "not found" not in answer.lower():
                            render_error("⚠️ No matching context chunks were retrieved from ChromaDB.")

                        st.markdown(answer)
                        st.caption(f"📊 Context: {count} chunks retrieved")

                        # Append Assistant Response & Chunks to Chat History
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "count": count,
                            "retrieved_chunks": retrieved_chunks
                        })
                        st.rerun()
                    else:
                        render_error(f"❌ Backend Error {response.status_code}: {response.text}")

                except requests.exceptions.Timeout:
                    render_error("⏰ Server timeout (120 seconds). The LLM or vector search took too long.")
                except requests.exceptions.ConnectionError:
                    render_error("❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`).")
                except Exception as e:
                    render_error(f"❌ Error: {str(e)}")