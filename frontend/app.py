import sys
from pathlib import Path
import streamlit as st
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend.chat import render_chat_page

# FastAPI backend URL — everything in this file talks to the backend
# over HTTP so that Streamlit and FastAPI always see the SAME ChromaDB
# state (both processes previously opened their own private
# PersistentClient copy, which is what caused new docs to "disappear"
# during chat).
API_BASE = "http://localhost:8000/api"

# Config & CSS setup
st.set_page_config(page_title="RAG Data Ingestion", page_icon="⚡", layout="wide")

css_file = ROOT_DIR / "frontend" / "styles.css"
if css_file.exists():
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# State initialization
if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"
if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = None


# ============================================================
# Backend helper functions — thin wrappers around HTTP calls
# ============================================================

def api_list_documents() -> list:
    """GET /api/documents/ — list all documents with status."""
    try:
        res = requests.get(f"{API_BASE}/documents/", timeout=10)
        if res.status_code == 200:
            return res.json()
        st.error(f"Failed to load documents: {res.status_code} — {res.text}")
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`).")
    except Exception as e:
        st.error(f"Failed to load documents: {e}")
    return []


def api_get_document_detail(doc_id: int):
    """GET /api/documents/{id} — detail view with status + chunks."""
    try:
        res = requests.get(f"{API_BASE}/documents/{doc_id}", timeout=30)
        if res.status_code == 200:
            return res.json()
        st.error(f"Failed to load document detail: {res.status_code} — {res.text}")
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`).")
    except Exception as e:
        st.error(f"Failed to load document detail: {e}")
    return None


def api_upload_document(filename: str, file_bytes: bytes):
    """POST /api/documents/upload — upload a new file."""
    try:
        files = {"file": (filename, file_bytes)}
        res = requests.post(f"{API_BASE}/documents/upload", files=files, timeout=60)
        if res.status_code == 200:
            return res.json(), None
        return None, f"{res.status_code} — {res.text}"
    except requests.exceptions.ConnectionError:
        return None, "❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`)."
    except Exception as e:
        return None, str(e)


def api_embed_document(doc_id: int):
    """POST /api/documents/{id}/embed — extract, chunk, and embed."""
    try:
        res = requests.post(f"{API_BASE}/documents/{doc_id}/embed", timeout=120)
        if res.status_code == 200:
            return res.json(), None
        return None, f"{res.status_code} — {res.text}"
    except requests.exceptions.ConnectionError:
        return None, "❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`)."
    except Exception as e:
        return None, str(e)


def api_delete_document(doc_id: int):
    """DELETE /api/documents/{id} — remove from DB, disk, and ChromaDB."""
    try:
        res = requests.delete(f"{API_BASE}/documents/{doc_id}", timeout=30)
        if res.status_code == 200:
            return True, None
        return False, f"{res.status_code} — {res.text}"
    except requests.exceptions.ConnectionError:
        return False, "❌ Cannot connect to backend. Ensure FastAPI server is running (`uvicorn main:app --reload --port 8000`)."
    except Exception as e:
        return False, str(e)


# ============================================================
# Page rendering
# ============================================================

def render_header_nav():
    """Top navigation bar."""
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗂️ Data Ingestion Dashboard", use_container_width=True, type="primary" if st.session_state["page"] in ["dashboard", "detail"] else "secondary"):
            st.session_state["page"] = "dashboard"
            st.rerun()
    with c2:
        if st.button("💬 Knowledge Base Chatbot", use_container_width=True, type="primary" if st.session_state["page"] == "chat" else "secondary"):
            st.session_state["page"] = "chat"
            st.rerun()
    st.markdown("<hr style='margin:10px 0 20px 0;'>", unsafe_allow_html=True)


def render_dashboard():
    st.title("⚡ Document Ingestion Dashboard")

    # Upload Section
    with st.container(border=True):
        st.subheader("📤 Upload New Document")
        col_file, col_btn = st.columns([3, 1])
        with col_file:
            uploaded_file = st.file_uploader("Choose a document", type=["pdf", "docx", "txt"], label_visibility="collapsed")
        with col_btn:
            if st.button("Upload File", use_container_width=True, type="primary"):
                if uploaded_file is not None:
                    result, err = api_upload_document(uploaded_file.name, uploaded_file.read())
                    if err:
                        st.error(f"Upload failed: {err}")
                    elif result and result.get("status") == "duplicate_blocked":
                        st.warning(f"🛑 {result.get('message')}")
                    else:
                        st.toast(f"✅ {result.get('message', 'Uploaded successfully.')}")
                        st.rerun()
                else:
                    st.warning("Please select a file first.")

    # Document Cards Section
    st.markdown("### 🗂️ Managed Documents")

    docs = api_list_documents()

    if not docs:
        st.info("No documents uploaded yet. Upload a file above to get started.")
        return

    cols = st.columns(2)
    for i, doc in enumerate(docs):
        doc_id = doc["id"]
        filename = doc["filename"]
        filehash = doc.get("filehash", "")
        status = doc["status"]
        v_count = doc.get("vector_count", 0)

        with cols[i % 2]:
            with st.container(border=True):
                is_embedded = status == "embedded" or v_count > 0
                badge = f"<span class='badge badge-embedded'>🟢 EMBEDDED ({v_count} Vectors)</span>" if is_embedded else "<span class='badge badge-ready'>🔵 READY TO EMBED</span>"

                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span class="doc-card-title">📄 {filename}</span>
                        {badge}
                    </div>
                    <div class="doc-card-hash">SHA-256: {filehash[:20]}...</div>
                    """,
                    unsafe_allow_html=True,
                )

                btn_c1, btn_c2 = st.columns([3, 1])
                with btn_c1:
                    if st.button("🔍 Open Detail", key=f"det_{doc_id}", use_container_width=True):
                        st.session_state["selected_doc_id"] = doc_id
                        st.session_state["page"] = "detail"
                        st.rerun()
                with btn_c2:
                    if st.button("🗑️ Delete", key=f"del_{doc_id}", use_container_width=True):
                        ok, err = api_delete_document(doc_id)
                        if ok:
                            st.toast(f"Deleted {filename}")
                            st.rerun()
                        else:
                            st.error(f"Delete failed: {err}")


def render_detail_page():
    doc_id = st.session_state.get("selected_doc_id")
    if not doc_id:
        st.session_state["page"] = "dashboard"
        st.rerun()
        return

    if st.button("⬅️ Back to Dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    detail = api_get_document_detail(doc_id)
    if detail is None:
        st.error("Could not load this document from the backend.")
        return

    document = detail["document"]
    filename = document["filename"]
    status_str = document["status"]
    v_count = document.get("vector_count", 0)

    st.title(f"📄 Detail View: {filename}")

    with st.container(border=True):
        c1, c2 = st.columns([3, 2])
        with c1:
            st.subheader("Document Status")
            if status_str == "embedded" or v_count > 0:
                st.success(f"🟢 Embedded ({v_count} vectors indexed in ChromaDB)")
            else:
                st.info("🔵 Uploaded — Ready for extraction & embedding")

        with c2:
            st.subheader("Actions")
            if st.button("🚀 Extract & Embed in ChromaDB", type="primary", use_container_width=True):
                with st.spinner("Extracting text, chunking, and embedding vectors into ChromaDB..."):
                    result, err = api_embed_document(doc_id)
                    if err:
                        st.error(f"Embedding failed: {err}")
                    else:
                        st.success(result.get("message", "Embedded successfully."))
                        st.rerun()


# ============================================================
# Application Routing
# ============================================================

if st.session_state["page"] == "chat":
    # Dedicated single back button for Chat page header
    if st.button("⬅️ Back to Dashboard", type="secondary"):
        st.session_state["page"] = "dashboard"
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    render_chat_page()
else:
    render_header_nav()
    if st.session_state["page"] == "dashboard":
        render_dashboard()
    elif st.session_state["page"] == "detail":
        render_detail_page()