const API_BASE = "/api";
const MAX_LEN = 1000;

let sessionId = localStorage.getItem("active_session_id") || null;
let knownSessionIds = JSON.parse(localStorage.getItem("session_ids") || "[]");
let isStreaming = false;
let searchDebounce = null;

const messagesEl = document.getElementById("messages");
const questionEl = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const charCountEl = document.getElementById("char-count");
const sessionListEl = document.getElementById("session-list");
const sessionSearchEl = document.getElementById("session-search");

questionEl.addEventListener("input", () => {
    charCountEl.textContent = `${questionEl.value.length} / ${MAX_LEN}`;
    questionEl.style.height = "auto";
    questionEl.style.height = Math.min(questionEl.scrollHeight, 140) + "px";
});

questionEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function clearWelcome() {
    const w = document.getElementById("welcome");
    if (w) w.remove();
}

function addMessage(role, text) {
    clearWelcome();
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return { row, bubble };
}

function addTypingIndicator() {
    clearWelcome();
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.id = "typing-row";
    row.innerHTML = `<div class="bubble typing"><span></span><span></span><span></span></div>`;
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return row;
}

function renderSources(container, sources) {
    if (!sources || !sources.length) return;
    const wrap = document.createElement("div");
    wrap.className = "sources";
    sources.forEach(s => {
        const chip = document.createElement("div");
        chip.className = "source-chip";
        chip.innerHTML = `<b>[${s.citation}]</b> ${s.source || "-"} ${s.page ? "· hlm. " + (Array.isArray(s.page)?s.page.join(","):s.page) : ""} ${s.category ? "· " + s.category : ""}`;
        wrap.appendChild(chip);
    });
    container.appendChild(wrap);
}

function renderFeedback(container, requestId) {
    const row = document.createElement("div");
    row.className = "feedback-row";
    row.innerHTML = `
        <button class="fb-btn" data-rating="up">👍</button>
        <button class="fb-btn" data-rating="down">👎</button>
    `;

    const reasonWrap = document.createElement("div");
    reasonWrap.className = "feedback-reason";
    reasonWrap.innerHTML = `
        <input type="text" class="reason-input" placeholder="Apa alasan Anda?" maxlength="500">
        <button class="reason-btn">Kirim</button>
    `;
    reasonWrap.style.display = "none";

    row.querySelectorAll(".fb-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            row.querySelectorAll(".fb-btn").forEach(b => b.classList.remove("selected"));
            btn.classList.add("selected");
            reasonWrap.style.display = "flex";
            reasonWrap.querySelector(".reason-input").focus();
        });
    });

    reasonWrap.querySelector(".reason-btn").addEventListener("click", async () => {
        const selected = row.querySelector(".fb-btn.selected");
        const input = reasonWrap.querySelector(".reason-input");
        if (!selected) return;

        const reason = input.value.trim();
        const success = await sendFeedback(requestId, selected.dataset.rating, reason);

        if (success) {
            input.disabled = true;
            reasonWrap.querySelector(".reason-btn").disabled = true;
            reasonWrap.querySelector(".reason-btn").textContent = "Terkirim";
        }
    });

    container.appendChild(row);
    container.appendChild(reasonWrap);
}

async function sendFeedback(requestId, rating, reason) {
    try {
        const res = await fetch(`${API_BASE}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                request_id: requestId,
                rating,
                reason: reason || null
            })
        });

        if (!res.ok) {
            console.error("feedback failed:", await res.text());
            return false;
        }

        return true;
    } catch (e) {
        console.error("feedback failed", e);
        return false;
    }
}

function saveSessionId(id) {
    sessionId = id;
    localStorage.setItem("active_session_id", id);
    if (!knownSessionIds.includes(id)) {
        knownSessionIds.unshift(id);
        localStorage.setItem("session_ids", JSON.stringify(knownSessionIds));
    }
}

function startNewChat() {
    sessionId = null;
    localStorage.removeItem("active_session_id");
    messagesEl.innerHTML = `
        <div id="welcome">
            <h2>Selamat datang</h2>
            <p>Tanyakan sesuatu berdasarkan knowledge base perusahaan. Jawaban disertai sitasi sumber.</p>
        </div>`;
    highlightActiveSession();
}

async function loadSessionList() {
    if (!knownSessionIds.length) return;
    try {
        const res = await fetch(`${API_BASE}/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_ids: knownSessionIds })
        });
        const sessions = await res.json();
        sessionListEl.innerHTML = "";
        sessions.forEach(s => {
            const item = document.createElement("div");
            item.className = "session-item" + (s.session_id === sessionId ? " active" : "");
            item.dataset.id = s.session_id;
            item.innerHTML = `<span>${s.title || "Percakapan baru"}</span><button class="del-btn" title="Hapus">✕</button>`;
            item.querySelector("span").addEventListener("click", () => openSession(s.session_id));
            item.querySelector(".del-btn").addEventListener("click", (e) => {
                e.stopPropagation();
                openDeleteConfirm(s.session_id);
            });
            sessionListEl.appendChild(item);
        });
    } catch (e) { console.error("load sessions failed", e); }
}

function highlightActiveSession() {
    document.querySelectorAll(".session-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === sessionId);
    });
}

async function openSession(id) {
    try {
        const res = await fetch(`${API_BASE}/sessions/${id}`);
        if (!res.ok) return;
        const data = await res.json();
        saveSessionId(id);
        messagesEl.innerHTML = "";
        (data.messages || []).forEach(m => {
            const { row } = addMessage(m.role === "user" ? "user" : "bot", m.content);
            if (m.role === "assistant" && m.sources) renderSources(row, m.sources);
        });
        highlightActiveSession();
    } catch (e) { console.error("open session failed", e); }
}

const confirmModal = document.getElementById("confirm-modal");
const confirmCancelBtn = document.getElementById("confirm-cancel-btn");
const confirmOkBtn = document.getElementById("confirm-ok-btn");
let pendingDeleteId = null;

function openDeleteConfirm(id) {
    pendingDeleteId = id;
    confirmModal.classList.add("open");
}

function closeDeleteConfirm() {
    pendingDeleteId = null;
    confirmModal.classList.remove("open");
}

confirmCancelBtn.addEventListener("click", closeDeleteConfirm);
confirmModal.addEventListener("click", (e) => {
    if (e.target === confirmModal) closeDeleteConfirm();
});
confirmOkBtn.addEventListener("click", async () => {
    const id = pendingDeleteId;
    closeDeleteConfirm();
    if (id) await deleteSession(id);
});

async function deleteSession(id) {
    try {
        await fetch(`${API_BASE}/sessions/${id}`, { method: "DELETE" });
        knownSessionIds = knownSessionIds.filter(s => s !== id);
        localStorage.setItem("session_ids", JSON.stringify(knownSessionIds));
        if (id === sessionId) startNewChat();
        await loadSessionList();
        window.location.reload();
    } catch (e) { console.error("delete session failed", e); }
}

async function sendMessage() {
    const question = questionEl.value.trim();
    if (!question || isStreaming) return;
    if (question.length > MAX_LEN) return;

    isStreaming = true;
    sendBtn.disabled = true;
    questionEl.value = "";
    questionEl.style.height = "auto";
    charCountEl.textContent = `0 / ${MAX_LEN}`;

    addMessage("user", question);
    const typingRow = addTypingIndicator();

    let botBubbleEl = null;
    let botRowEl = null;
    let currentRequestId = null;
    let answerBuffer = "";

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, session_id: sessionId })
        });

        if (!res.ok || !res.body) {
            typingRow.remove();
            addMessage("bot", "Request gagal diproses.");
            isStreaming = false;
            sendBtn.disabled = false;
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n\n");
            buffer = parts.pop();

            for (const part of parts) {
                if (!part.startsWith("data:")) continue;
                const jsonStr = part.slice(5).trim();
                if (!jsonStr) continue;

                let evt;
                try { evt = JSON.parse(jsonStr); } catch { continue; }

                if (evt.type === "metadata") {
                    saveSessionId(evt.session_id);
                    currentRequestId = evt.request_id;
                    highlightActiveSession();
                    loadSessionList();
                }

                if (evt.type === "token") {
                    if (!botBubbleEl) {
                        typingRow.remove();
                        const { row, bubble } = addMessage("bot", "");
                        botRowEl = row;
                        botBubbleEl = bubble;
                    }
                    answerBuffer += evt.content;
                    botBubbleEl.textContent = answerBuffer;
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                }

                if (evt.type === "answer") {
                    answerBuffer = evt.content;
                    if (botBubbleEl) botBubbleEl.textContent = answerBuffer;
                }

                if (evt.type === "sources") {
                    if (botRowEl) {
                        renderSources(botRowEl, evt.sources);
                        if (currentRequestId) renderFeedback(botRowEl, currentRequestId);
                    }
                }

                if (evt.type === "error") {
                    typingRow.remove();
                    if (!botBubbleEl) addMessage("bot", evt.content);
                }
            }
        }

        if (!botBubbleEl && typingRow.parentNode) {
            typingRow.remove();
        }

    } catch (e) {
        console.error("chat stream failed", e);
        if (typingRow.parentNode) typingRow.remove();
        if (!botBubbleEl) addMessage("bot", "Request gagal diproses.");
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        questionEl.focus();
    }
}

sessionSearchEl.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    const q = sessionSearchEl.value.trim();

    searchDebounce = setTimeout(async () => {
        if (!q) {
            loadSessionList();
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/sessions/search?q=${encodeURIComponent(q)}`);
            const results = await res.json();
            renderSearchResults(results);
        } catch (e) { console.error("search failed", e); }
    }, 300);
});

function renderSearchResults(results) {
    sessionListEl.innerHTML = "";
    if (!results.length) {
        sessionListEl.innerHTML = `<div class="empty-state">Tidak ditemukan</div>`;
        return;
    }
    results.forEach(r => {
        const item = document.createElement("div");
        item.className = "session-item";
        item.dataset.id = r.session_id;
        item.innerHTML = `<span>${r.title || "Percakapan"}<br><small>${r.snippet}</small></span>`;
        item.querySelector("span").addEventListener("click", () => openSession(r.session_id));
        sessionListEl.appendChild(item);
    });
}

// init
loadSessionList();
if (sessionId) openSession(sessionId);