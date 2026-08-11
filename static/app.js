
const API_BASE = "/api";

// STATE — plain in-memory JS objects only.

const state = {
    documents: [],        // cache of GET /api/documents/
    currentDetailDocId: null,
    chatMessages: [],      // { role: "user" | "assistant", content: string, count?: number }
};

// DOM refs

const navDashboard = document.getElementById("navDashboard");
const navChat = document.getElementById("navChat");
const backToDashboard = document.getElementById("backToDashboard");

const dashboardView = document.getElementById("dashboardView");
const detailView = document.getElementById("detailView");
const chatView = document.getElementById("chatView");

const fileInput = document.getElementById("fileInput");
const fileNameLabel = document.getElementById("fileNameLabel");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const documentGrid = document.getElementById("documentGrid");
const dashboardEmpty = document.getElementById("dashboardEmpty");

const detailFilename = document.getElementById("detailFilename");
const detailStatusBox = document.getElementById("detailStatusBox");
const embedBtn = document.getElementById("embedBtn");
const embedStatus = document.getElementById("embedStatus");

const docSelect = document.getElementById("docSelect");
const topKSlider = document.getElementById("topKSlider");
const topKValue = document.getElementById("topKValue");
const clearChatBtn = document.getElementById("clearChatBtn");
const chatMessagesBox = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");

// =============================================================
// VIEW SWITCHING — just toggling a CSS class, never a page load
// =============================================================
function showView(name) {
    [dashboardView, detailView, chatView].forEach((v) => v.classList.remove("active"));
    navDashboard.classList.remove("primary");
    navChat.classList.remove("primary");

    if (name === "dashboard") {
        dashboardView.classList.add("active");
        navDashboard.classList.add("primary");
        loadDocuments();
    } else if (name === "detail") {
        detailView.classList.add("active");
    } else if (name === "chat") {
        chatView.classList.add("active");
        navChat.classList.add("primary");
    }
}

navDashboard.addEventListener("click", () => showView("dashboard"));
navChat.addEventListener("click", () => showView("chat"));
backToDashboard.addEventListener("click", () => showView("dashboard"));

// API HELPERS — every call is fetch() with an explicit method.
// GET for reads, POST for writes/uploads, DELETE for removal.

async function apiListDocuments() {
    const res = await fetch(`${API_BASE}/documents/`, { method: "GET" });
    if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);
    return res.json();
}

async function apiUploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file); // field name must match FastAPI's `file: UploadFile = File(...)`
    // NOTE: don't set Content-Type manually here — the browser sets the
    // correct multipart boundary automatically when you pass FormData.
    const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Upload failed (${res.status})`);
    return data;
}

async function apiEmbedDocument(docId) {
    const res = await fetch(`${API_BASE}/documents/${docId}/embed`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Embedding failed (${res.status})`);
    return data;
}

async function apiDeleteDocument(docId) {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: "DELETE" });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Delete failed (${res.status})`);
    }
    return true;
}

async function apiChat(payload) {
    // POST with a JSON body. This matches the ChatRequest schema your
    // backend's active /api/chat/ handler reads (message, top_k, doc_id,
    // conversation_history). QUERY (RFC 10008) is also registered on
    // this route, but POST is the dependable choice today.
    const res = await fetch(`${API_BASE}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Backend error (${res.status})`);
    return data;
}

// =============================================================
// DASHBOARD — list, upload, delete
// =============================================================
async function loadDocuments() {
    try {
        state.documents = await apiListDocuments();
    } catch (err) {
        documentGrid.innerHTML = "";
        dashboardEmpty.style.display = "block";
        dashboardEmpty.textContent = `❌ ${err.message}. Is the FastAPI server running on port 8000?`;
        populateDocSelect();
        return;
    }
    renderDocumentGrid();
    populateDocSelect();
}

function statusBadge(status, vectorCount) {
    const isEmbedded = status === "embedded" || vectorCount > 0;
    return isEmbedded
        ? `<span class="badge badge-embedded">🟢 EMBEDDED (${vectorCount} Vectors)</span>`
        : `<span class="badge badge-ready">🔵 READY TO EMBED</span>`;
}

function renderDocumentGrid() {
    documentGrid.innerHTML = "";

    if (state.documents.length === 0) {
        dashboardEmpty.style.display = "block";
        dashboardEmpty.textContent = "No documents uploaded yet. Upload a file above to get started.";
        return;
    }
    dashboardEmpty.style.display = "none";

    for (const doc of state.documents) {
        const card = document.createElement("div");
        card.className = "doc-card";
        card.innerHTML = `
      <div>
        <div class="doc-header">
          <span class="doc-title">📄 ${escapeHtml(doc.filename)}</span>
          ${statusBadge(doc.status, doc.vector_count || 0)}
        </div>
        <div class="doc-hash">SHA-256: ${escapeHtml((doc.filehash || "").slice(0, 20))}...</div>
      </div>
      <div class="doc-actions">
        <button type="button" data-action="detail" data-id="${doc.id}">🔍 Open Detail</button>
        <button type="button" class="btn-delete" data-action="delete" data-id="${doc.id}">🗑️ Delete</button>
      </div>
    `;
        documentGrid.appendChild(card);
    }
}

// Event delegation: one listener handles every card's buttons,
// including ones added after the initial render.
documentGrid.addEventListener("click", async (event) => {
    const btn = event.target.closest("button[data-action]");
    if (!btn) return;
    const docId = Number(btn.dataset.id);

    if (btn.dataset.action === "detail") {
        openDetail(docId);
    } else if (btn.dataset.action === "delete") {
        const card = btn.closest(".doc-card");
        if (card && !card.classList.contains("confirming")) {
            card.classList.add("confirming");
            const originalHTML = btn.innerHTML;
            btn.innerHTML = "⚠️ Confirm Delete?";
            setTimeout(() => {
                if (card.classList.contains("confirming")) {
                    card.classList.remove("confirming");
                    btn.innerHTML = originalHTML;
                }
            }, 4000);
            return;
        }

        btn.disabled = true;
        try {
            await apiDeleteDocument(docId);
            await loadDocuments();
        } catch (err) {
            console.error(`Delete failed: ${err.message}`);
            btn.disabled = false;
        }
    }

    //else if (btn.dataset.action === "delete") {
    //     const doc = state.documents.find((d) => d.id === docId);
    //     if (!confirm(`Delete "${doc?.filename ?? "this document"}"? This cannot be undone.`)) return;
    //     btn.disabled = true;
    //     try {
    //         await apiDeleteDocument(docId);
    //         await loadDocuments();
    //     } catch (err) {
    //         alert(`Delete failed: ${err.message}`);
    //         btn.disabled = false;
    //     }
    // }
});

fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    fileNameLabel.textContent = file ? file.name : "Choose a document (PDF, DOCX, TXT)";
    fileNameLabel.parentElement.classList.toggle("has-file", Boolean(file));
});

uploadBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        uploadStatus.textContent = "⚠️ Please select a file first.";
        return;
    }

    uploadBtn.disabled = true;
    uploadStatus.innerHTML = `<span class="spinner"></span>Uploading and processing...`;

    try {
        const result = await apiUploadDocument(file);
        if (result.status === "duplicate_blocked") {
            uploadStatus.textContent = `🛑 ${result.message}`;
        } else {
            uploadStatus.textContent = `✅ ${result.message}`;
            fileInput.value = "";
            fileNameLabel.textContent = "Choose a document (PDF, DOCX, TXT)";
            fileNameLabel.parentElement.classList.remove("has-file");
            await loadDocuments();
        }
    } catch (err) {
        uploadStatus.textContent = `❌ Upload failed: ${err.message}`;
    } finally {
        uploadBtn.disabled = false;
    }
});

// =============================================================
// DETAIL VIEW
//
// Deliberately does NOT call GET /api/documents/{id} — that endpoint
// re-extracts and re-chunks the whole file from scratch every time
// it's hit (see extract_and_chunk_doc on the backend), which is slow
// and pointless just to show a status box. Instead we reuse the
// lightweight list data (state.documents) that's already in memory
// from GET /api/documents/.
// =============================================================
function renderDetailFromCache(docId) {
    const doc = state.documents.find((d) => d.id === docId);
    embedStatus.textContent = "";
    if (!doc) {
        detailFilename.textContent = "📄 Detail View";
        detailStatusBox.textContent = "❌ Document not found — it may have been deleted.";
        embedBtn.disabled = true;
        return;
    }

    const isEmbedded = doc.status === "embedded" || (doc.vector_count || 0) > 0;

    detailFilename.textContent = `📄 Detail View: ${doc.filename}`;
    detailStatusBox.className = `status-box ${isEmbedded ? "embedded" : "ready"}`;
    detailStatusBox.textContent = isEmbedded
        ? `🟢 Embedded (${doc.vector_count} vectors indexed in ChromaDB)`
        : "🔵 Uploaded — Ready for extraction & embedding";

    embedBtn.disabled = false;
}

function openDetail(docId) {
    state.currentDetailDocId = docId;
    showView("detail");
    renderDetailFromCache(docId);
}

async function embedCurrentDocument() {
    const docId = state.currentDetailDocId;
    if (!docId) return;
    embedBtn.disabled = true;
    const originalText = embedBtn.textContent;
    embedBtn.innerHTML = `<span class="spinner"></span>Extracting, chunking, and embedding...`;
    embedStatus.textContent = "";

    try {
        const result = await apiEmbedDocument(docId);
        // Refresh the lightweight document list only — no second heavy
        // extraction/chunking round-trip — then re-render from cache.
        await loadDocuments();
        embedBtn.textContent = originalText;
        renderDetailFromCache(docId);
        embedStatus.textContent = `✅ ${result.message || "Embedded successfully."}`;
    } catch (err) {
        embedBtn.textContent = originalText;
        embedStatus.textContent = `❌ Embedding failed: ${err.message}`;
    } finally {
        embedBtn.disabled = false;
    }
}

embedBtn.addEventListener("click", (event) => {
    event.preventDefault();
    embedCurrentDocument();
});

// =============================================================
// CHAT VIEW
// =============================================================
function populateDocSelect() {
    const previousValue = docSelect.value;
    docSelect.innerHTML = `<option value="">All Documents</option>`;
    for (const doc of state.documents) {
        const opt = document.createElement("option");
        opt.value = doc.id;
        opt.textContent = `📄 ${doc.filename}`;
        docSelect.appendChild(opt);
    }
    if ([...docSelect.options].some((o) => o.value === previousValue)) {
        docSelect.value = previousValue;
    }
}

topKSlider.addEventListener("input", () => {
    topKValue.textContent = topKSlider.value;
});

clearChatBtn.addEventListener("click", () => {
    state.chatMessages = [];
    chatMessagesBox.innerHTML = "";
});

function formatMarkdown(text) {
    if (!text) return "";
    let safeText = escapeHtml(text);

    safeText = safeText.replace(/^### (.*$)/gim, '<strong>$1</strong><br>');
    safeText = safeText.replace(/^## (.*$)/gim, '<strong style="font-size: 1.1em;">$1</strong><br>');
    safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    safeText = safeText.replace(/^\s*[-*]\s+(.*)$/gim, '• $1<br>');
    safeText = safeText.replace(/\n/g, '<br>');

    return safeText;
}
function appendChatMessage(role, content, meta) {
    const bubble = document.createElement("div");
    bubble.className = `message ${role}`;
    if (role === "assistant" || role === "assistant loading") {
        bubble.innerHTML = formatMarkdown(content);
    } else {
        bubble.textContent = content;
    }
    chatMessagesBox.appendChild(bubble);

    if (meta) {
        const caption = document.createElement("div");
        caption.className = "context-info";
        caption.style.alignSelf = role === "user" ? "flex-end" : "flex-start";
        caption.textContent = meta;
        chatMessagesBox.appendChild(caption);
    }

    chatMessagesBox.scrollTop = chatMessagesBox.scrollHeight;
    return bubble;
}

async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Build history the same way chat.py does: last 5 prior messages,
    // role/content only, BEFORE the new question is appended.
    const historyForModel = state.chatMessages
        .slice(-5)
        .map((m) => ({ role: m.role, content: m.content }));

    state.chatMessages.push({ role: "user", content: text });
    appendChatMessage("user", text);

    chatInput.value = "";
    chatInput.disabled = true;
    sendBtn.disabled = true;

    const pendingBubble = appendChatMessage(
        "assistant loading",
        "🔍 Embedding query & running cosine vector retrieval..."
    );

    try {
        const payload = {
            message: text,
            top_k: Number(topKSlider.value),
            doc_id: docSelect.value ? Number(docSelect.value) : null,
            conversation_history: historyForModel,
        };

        const data = await apiChat(payload);
        const answer = data.answer || "No answer generated by LLM.";
        const count = data.count ?? 0;

        state.chatMessages.push({ role: "assistant", content: answer, count });

        // pendingBubble.textContent = answer;
        pendingBubble.innerHTML = formatMarkdown(answer);
        pendingBubble.className = "message assistant";

        const caption = document.createElement("div");
        caption.className = "context-info";
        caption.textContent = `📊 Context: ${count} chunks retrieved`;
        chatMessagesBox.appendChild(caption);
        chatMessagesBox.scrollTop = chatMessagesBox.scrollHeight;
    } catch (err) {
        pendingBubble.textContent = `❌ ${err.message}`;
        pendingBubble.className = "message assistant error";
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// No <form> anywhere in the chat markup, so there is no default
// browser submit behavior to fight. preventDefault() here is just a
// defensive habit in case this input is ever moved inside a form.
sendBtn.addEventListener("click", (event) => {
    event.preventDefault();
    sendChatMessage();
});

chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        sendChatMessage();
    }
});

// =============================================================
// UTIL
// =============================================================
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
}

// =============================================================
// INIT
// =============================================================
loadDocuments();