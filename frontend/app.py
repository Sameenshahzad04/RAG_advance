import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st  
from backend.database import SessionLocal
from backend.handler.doc_handler import (
    process_upload,
    get_all_documents_with_status,
    get_document_status,
    delete_document,
    embed_document,
)

# ----- PAGE CONFIG -----
st.set_page_config(page_title="RAG Data Ingestion", page_icon="🤖", layout="wide")

# ----- LOAD CUSTOM CSS -----
css_file = ROOT_DIR / "frontend" / "styles.css"
if css_file.exists():
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ----- SESSION STATE -----
if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"
if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = None


# =============================================================
# SIDEBAR — File Upload Section
# =============================================================
def render_sidebar() -> None:
    st.sidebar.title("⚡ Document Ingestion")
    st.sidebar.markdown("Upload PDF, DOCX, or TXT documents to start ingestion.")

    file = st.sidebar.file_uploader("Choose a file", type=["pdf", "docx", "txt"])

    if st.sidebar.button("📤 Upload Document", use_container_width=True):
        if file is not None:
            db = SessionLocal()
            try:
                status, msg, _doc = process_upload(db, file.name, file.read())
                if status == "duplicate_blocked":
                    st.sidebar.error(f"🛑 {msg}")
                else:
                    st.sidebar.success(f"✅ {msg}")
                    st.rerun()
            finally:
                db.close()
        else:
            st.sidebar.warning("Please select a file first.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📌 Status Legend")
    st.sidebar.markdown(
        """
        - <span class='badge badge-red'>🔴 Uploaded</span> Stored in DB & Disk
        - <span class='badge badge-green'>🟢 Embedded</span> Processed into Vector DB
        """,
        unsafe_allow_html=True,
    )


# =============================================================
# DASHBOARD PAGE — Document Cards Grid
# =============================================================
def render_dashboard() -> None:
    st.title("🗂️ Document Ingestion Dashboard")

    db = SessionLocal()
    try:
        docs = get_all_documents_with_status(db)
    finally:
        db.close()

    if not docs:
        st.info("No documents uploaded yet. Use the sidebar to upload files.")
        return

    cols = st.columns(2)
    for i, doc in enumerate(docs):
        with cols[i % 2]:
            status = doc["status"]
            if status == "embedded":
                badge = f"<span class='badge badge-green'>🟢 EMBEDDED ({doc['vector_count']} Vectors)</span>"
            else:
                badge = "<span class='badge badge-red'>🔴 UPLOADED</span>"

            st.markdown(
                f"""
                <div class="doc-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <div class="doc-title">📄 {doc['filename']}</div>
                        <div>{badge}</div>
                    </div>
                    <div class="doc-hash">Hash: {doc['filehash'][:16]}...</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns([3, 1])
            if c1.button("🔍 Open Detail", key=f"det_{doc['id']}", use_container_width=True):
                st.session_state["selected_doc_id"] = doc["id"]
                st.session_state["page"] = "detail"
                st.rerun()
            if c2.button("🗑️ Delete", key=f"del_{doc['id']}", use_container_width=True):
                db = SessionLocal()
                try:
                    delete_document(db, doc["id"])
                    st.toast(f"Deleted {doc['filename']}")
                    st.rerun()
                finally:
                    db.close()


# =============================================================
# DETAIL PAGE — Direct Vector Embedding Trigger
# =============================================================
def render_detail_page() -> None:
    doc_id = st.session_state.get("selected_doc_id")
    if not doc_id:
        st.session_state["page"] = "dashboard"
        st.rerun()
        return

    if st.button("⬅️ Back to Dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    db = SessionLocal()
    try:
        status_str, v_count = get_document_status(db, doc_id)
        from backend.models.documents import Document
        doc = db.query(Document).filter(Document.id == doc_id).first()
        filename = doc.filename if doc else f"Doc #{doc_id}"
    except Exception as e:
        st.error(f"Error loading document: {e}")
        return
    finally:
        db.close()

    st.title(f"📄 Detail View: {filename}")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Document Status")
        if status_str == "embedded":
            st.success(f"🟢 Embedded ({v_count} vectors indexed in ChromaDB)")
        else:
            st.warning("🔴 Uploaded — Ready for extraction & embedding")

    with c2:
        st.subheader("Actions")
        if st.button("🚀 Extract & Embed in ChromaDB", type="primary", use_container_width=True):
            with st.spinner("Extracting text, chunking, and embedding vectors into ChromaDB..."):
                db = SessionLocal()
                try:
                    res = embed_document(db, doc_id)
                    st.success(res["message"])
                    st.rerun()
                except Exception as ex:
                    st.error(f"Embedding failed: {ex}")
                finally:
                    db.close()


# =============================================================
# MAIN — Application Entrypoint
# =============================================================
render_sidebar()

if st.session_state["page"] == "dashboard":
    render_dashboard()
else:
    render_detail_page()