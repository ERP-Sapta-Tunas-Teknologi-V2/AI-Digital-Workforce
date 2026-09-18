const form = document.getElementById("chat-form");
const input = document.getElementById("question");
const button = form.querySelector("button");
const messages = document.getElementById("messages");

let isLoading = false;
let sessionId = null;
let lastRequestId = null;
let sources = [];

const sessionListEl = document.getElementById("session-list");
const newChatButton = document.getElementById("new-chat-button");

const STORAGE_KEY = "ke_session_ids";

function getStoredSessionIds() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch {
        return [];
    }
}

function saveSessionId(id) {
    const ids = getStoredSessionIds();
    if (!ids.includes(id)) {
        ids.unshift(id);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    }
}

async function loadSidebar() {
    const ids = getStoredSessionIds();
    sessionListEl.innerHTML = "";

    if (!ids.length) return;

    try {
        const response = await fetch("/api/sessions", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({session_ids: ids})
        });

        const sessions = await response.json();

        sessions.forEach(s => {
            const item = document.createElement("div");
            item.className = "session-item" + (s.session_id === sessionId ? " active" : "");

            const label = document.createElement("span");
            label.className = "session-item-label";
            label.textContent = s.title || "(tanpa judul)";
            label.addEventListener("click", () => loadSession(s.session_id));

            const deleteBtn = document.createElement("button");
            deleteBtn.className = "session-delete-button";
            deleteBtn.textContent = "×";
            deleteBtn.title = "Hapus percakapan";
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteSession(s.session_id);
            });

            item.appendChild(label);
            item.appendChild(deleteBtn);
            sessionListEl.appendChild(item);
        });
    } catch (error) {
        console.error("Failed to load sidebar:", error);
    }
}

async function loadSession(id) {
    try {
        const response = await fetch(`/api/sessions/${id}`);
        if (!response.ok) return;

        const data = await response.json();

        sessionId = data.session_id;
        messages.innerHTML = "";

        data.messages.forEach(m => {
            addMessage(m.content, m.role === "user" ? "user" : "bot");
        });

        loadSidebar();
    } catch (error) {
        console.error("Failed to load session:", error);
    }
}

function removeStoredSessionId(id) {
    const ids = getStoredSessionIds().filter(existing => existing !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

async function deleteSession(id) {
    if (!confirm("Hapus percakapan ini?")) {
        return;
    }

    try {
        await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    } catch (error) {
        console.error("Failed to delete session:", error);
    } finally {
        removeStoredSessionId(id);

        if (id === sessionId) {
            sessionId = null;
            lastRequestId = null;
            messages.innerHTML = "";
            addMessage("Halo, ada yang bisa saya bantu?", "bot");
        }

        loadSidebar();
    }
}

newChatButton.addEventListener("click", () => {
    sessionId = null;
    lastRequestId = null;
    messages.innerHTML = "";
    addMessage("Halo, ada yang bisa saya bantu?", "bot");
    loadSidebar();
});

loadSidebar();

function addMessage(text, type) {
    const el = document.createElement("div");
    el.className = `message ${type}`;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
}

function addTyping() {
    const el = document.createElement("div");
    el.className = "message bot typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
}

function setLoading(loading) {
    isLoading = loading;
    button.disabled = loading;
    button.textContent = loading ? "Menunggu..." : "Kirim";
}

function addFeedbackControls(bot, requestId) {
    const wrap = document.createElement("div");
    wrap.className = "feedback";

    const up = document.createElement("button");
    up.textContent = "👍";
    up.type = "button";

    const down = document.createElement("button");
    down.textContent = "👎";
    down.type = "button";

    const status = document.createElement("span");
    status.className = "feedback-status";

    up.addEventListener("click", () => {
        const reason = prompt("Tuliskan alasan dari feedback Anda (opsional)");
        submitFeedback(requestId, "up", reason || null, wrap, status);
    });
    down.addEventListener("click", () => {
        const reason = prompt("Tuliskan alasan dari feedback Anda (opsional)");
        submitFeedback(requestId, "down", reason || null, wrap, status);
    });

    wrap.appendChild(up);
    wrap.appendChild(down);
    wrap.appendChild(status);
    bot.appendChild(wrap);
}

async function submitFeedback(requestId, rating, reason, wrap, status) {
    wrap.querySelectorAll("button").forEach(b => b.disabled = true);

    try {
        const response = await fetch("/api/feedback", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({request_id: requestId, rating, reason})
        });

        if (!response.ok) {
            throw new Error();
        }

        status.textContent = "Terima kasih atas feedback Anda.";
    } catch {
        status.textContent = "Gagal mengirim feedback.";
        wrap.querySelectorAll("button").forEach(b => b.disabled = false);
    }
}

form.addEventListener("submit", async e => {
    e.preventDefault();

    if (isLoading) {
        return;
    }

    const question = input.value.trim();

    if (!question) {
        return;
    }

    addMessage(question, "user");
    input.value = "";
    setLoading(true);

    const bot = addTyping();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question, session_id: sessionId})
        });

        if (!response.ok) {
            const error = await response.json();
            bot.className = "message bot";
            bot.textContent = response.status === 429
                ? "Terlalu banyak permintaan. Silakan coba lagi nanti."
                : error.error || "Terjadi kesalahan.";
            return;
        }

        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            const data = await response.json();
            sessionId = data.session_id;

            saveSessionId(sessionId);
            loadSidebar();

            bot.className = "message bot";
            bot.textContent = data.answer;

            if (data.request_id) {
                addFeedbackControls(bot, data.request_id);
            }

            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let buffer = "";
        let answer = "";
        let sources = [];
        let started = false;

        while (true) {
            const {value, done} = await reader.read();

            if (done) {
                break;
            }

            buffer += decoder.decode(value, {stream: true});

            const events = buffer.split("\n\n");
            buffer = events.pop();

            for (const event of events) {
                if (!event.startsWith("data: ")) {
                    continue;
                }

                const data = JSON.parse(event.slice(6));

                if (data.type === "metadata") {
                    sessionId = data.session_id;
                    saveSessionId(sessionId);
                    sources = data.sources || [];
                    lastRequestId = data.request_id;
                }

                if (data.type === "token") {
                    if (!started) {
                        bot.className = "message bot";
                        bot.textContent = "";
                        started = true;
                    }

                    answer += data.content;
                    bot.textContent = answer;
                    messages.scrollTop = messages.scrollHeight;
                }

                if (data.type === "answer") {
                    answer = data.content;
                }

                if (data.type === "sources") {
                    sources = data.sources || [];
                }

                if (data.type === "done") {
                    if (sources.length) {
                        const sourceEl = document.createElement("div");
                        sourceEl.className = "sources";

                        const title = document.createElement("b");
                        title.textContent = "Sumber:";
                        sourceEl.appendChild(title);

                        sources.forEach(source => {
                            const item = document.createElement("div");
                            const index = `[${source.citation}] `
                            const name = source.source || "Dokumen";
                            const page = source.page ? ` [Halaman ${source.page}]` : "";
                            item.textContent = `${index}${name}${page}`;
                            sourceEl.appendChild(item);
                        });

                        bot.appendChild(sourceEl);
                    }

                    if (lastRequestId) {
                        addFeedbackControls(bot, lastRequestId);
                    }

                    loadSidebar();
                }
            }
        }
    } catch (error) {
        console.error("Chat error:", error);
        bot.className = "message bot";
        bot.textContent = "Terjadi kesalahan saat menghubungi server.";
    } finally {
        setLoading(false);
        input.focus();
    }
});