const API_BASE = "/api";
const ADMIN_BASE = "/api/admin";
// TODO: sesuaikan dengan mekanisme auth nyata (mis. ambil dari session/login), lihat utils/permissions.py require_role("Admin")
const ADMIN_ROLE_HEADER = { "X-User-Role": "Admin" };

const CATEGORIES = ["general", "sop", "pricelist", "case", "meeting", "training", "solution", "proposal", "guide", "competitive", "datasheet", "sow"];

// ---------- Utilities ----------

function toast(message, type = "") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    document.getElementById("toast-container").appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function fmtCurrency(n) {
    const val = Number(n || 0);
    return "$" + val.toFixed(4);
}

function fmtNumber(n) {
    return Number(n || 0).toLocaleString("id-ID");
}

function fmtDateTime(value) {
    if (!value) return "-";

    let dateValue = value;
    if (typeof value === "string") {
        const wibMatch = value.trim().match(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) WIB$/i);
        if (wibMatch) dateValue = `${wibMatch[1]}T${wibMatch[2]}+07:00`;
    }

    const date = new Date(dateValue);
    if (Number.isNaN(date.getTime())) return value;

    return date.toLocaleString("id-ID", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
    });
}

async function apiGet(url, headers = {}) {
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
    return res.json();
}

async function apiJson(url, method, body, headers = {}) {
    const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", ...headers },
        body: body ? JSON.stringify(body) : undefined
    });
    let data = null;
    try { data = await res.json(); } catch { /* no body */ }
    if (!res.ok) {
        const msg = (data && (data.error || data.message)) || `${method} ${url} failed: ${res.status}`;
        throw new Error(msg);
    }
    return data;
}

// ---------- Navigation ----------

const VIEW_TITLES = {
    overview: "Ringkasan",
    documents: "Dokumen",
    faq: "Top FAQ",
    feedback: "Jawaban Bermasalah",
    flags: "Dokumen Ditandai"
};

function switchView(view) {
    document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === view));
    document.querySelectorAll(".view").forEach(el => el.classList.toggle("active", el.id === `view-${view}`));
    document.getElementById("topbar-title").textContent = VIEW_TITLES[view] || view;

    if (view === "overview") loadOverview();
    if (view === "documents") loadDocuments();
    if (view === "faq") loadFaq();
    if (view === "feedback") loadProblematicAnswers();
    if (view === "flags") loadFlaggedDocuments();
}

document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
});

// ---------- Overview ----------

async function loadOverview() {
    const days = document.getElementById("overview-days").value;
    try {
        const data = await apiGet(`${API_BASE}/analytics/dashboard-summary?days=${days}`, ADMIN_ROLE_HEADER);

        document.getElementById("stat-total-queries").textContent = fmtNumber(data.total_queries);
        document.getElementById("stat-total-feedback").textContent = fmtNumber(data.total_feedback);
        document.getElementById("stat-positive-rate").textContent = `${data.positive_feedback_rate ?? 0}%`;

        renderVolumeChart(data.query_volume || []);
        renderTopDocs(data.top_referenced_documents || []);
    } catch (e) {
        console.error(e);
        toast("Gagal memuat ringkasan", "error");
    }
}

function renderVolumeChart(volume) {
    const el = document.getElementById("volume-chart");
    el.innerHTML = "";
    if (!volume.length) {
        el.innerHTML = `<div class="empty-state">Belum ada data</div>`;
        return;
    }
    const max = Math.max(...volume.map(v => v.total), 1);
    volume.forEach(v => {
        const col = document.createElement("div");
        col.className = "bar-col";
        const heightPct = Math.max((v.total / max) * 100, 2);
        col.innerHTML = `
            <div class="bar" style="height:${heightPct}%" title="${v.total} pertanyaan"></div>
            <span class="bar-label">${new Date(v.date).toLocaleDateString("id-ID", { day: "2-digit", month: "short" })}</span>
        `;
        el.appendChild(col);
    });
}

function renderTopDocs(docs) {
    const body = document.getElementById("top-docs-body");
    body.innerHTML = "";
    if (!docs.length) {
        body.innerHTML = `<tr><td colspan="3" class="empty-state">Belum ada data</td></tr>`;
        return;
    }
    docs.forEach(d => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${d.source}</td><td>${d.category || "-"}</td><td>${fmtNumber(d.referenced_count)}</td>`;
        body.appendChild(tr);
    });
}

document.getElementById("overview-days").addEventListener("change", loadOverview);

// ---------- Documents (admin.py) ----------

async function loadDocuments() {
    const category = document.getElementById("doc-category-filter").value;
    const url = category ? `${ADMIN_BASE}/documents?category=${category}` : `${ADMIN_BASE}/documents`;
    const body = document.getElementById("documents-body");
    body.innerHTML = `<tr><td colspan="8" class="empty-state">Memuat...</td></tr>`;

    try {
        const files = await apiGet(url, ADMIN_ROLE_HEADER);
        body.innerHTML = "";

        if (!files.length) {
            body.innerHTML = `<tr><td colspan="8" class="empty-state">Tidak ada dokumen</td></tr>`;
            return;
        }

        files.forEach(f => {
            const tr = document.createElement("tr");
            const flagsHtml = (f.flags || [])
                .map(fl => `<span class="flag-tag" title="${fl.detail || ""}">${fl.type}</span>`)
                .join("");

            const statusClass = f.version_status === "superseded" ? "superseded" : (f.ingest_status || "not_ingested");

            tr.innerHTML = `
                <td>${f.filename}${f.is_archived ? ' <span class="badge">arsip</span>' : ""}</td>
                <td>${f.category}</td>
                <td><span class="badge ${statusClass}">${f.version_status === "superseded" ? "superseded" : f.ingest_status}</span></td>
                <td>${f.version_status || "-"}</td>
                <td>${flagsHtml || "-"}</td>
                <td>${fmtDateTime(f.uploaded_at_wib || f.uploaded_at)}</td>
                <td>${fmtDateTime(f.last_ingested_at_wib || f.last_ingested_at)}</td>
                <td class="row-actions"></td>
            `;

            const actionsCell = tr.querySelector(".row-actions");
            actionsCell.appendChild(makeActionBtn("Ingest", () => runIngest(f.category, f.filename)));
            actionsCell.appendChild(makeActionBtn("Un-ingest", () => runUnIngest(f.category, f.filename)));
            actionsCell.appendChild(makeActionBtn("Unduh", () => downloadDocument(f.category, f.filename)));
            const delBtn = makeActionBtn("Hapus", () => confirmAction(
                "Hapus Dokumen",
                `Hapus "${f.filename}" secara permanen dari storage dan index?`,
                () => deleteDocument(f.category, f.filename)
            ));
            delBtn.classList.add("danger");
            actionsCell.appendChild(delBtn);

            body.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        body.innerHTML = `<tr><td colspan="8" class="empty-state">Gagal memuat dokumen</td></tr>`;
        toast("Gagal memuat daftar dokumen", "error");
    }
}

function makeActionBtn(label, onClick) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    return btn;
}

async function runIngest(category, filename) {
    try {
        const data = await apiJson(`${ADMIN_BASE}/ingest`, "POST", { category, filename }, ADMIN_ROLE_HEADER);
        toast(data.message || "Ingest dimulai", "success");
        setTimeout(loadDocuments, 1500);
    } catch (e) {
        toast(e.message, "error");
    }
}

async function runUnIngest(category, filename) {
    try {
        const data = await apiJson(`${ADMIN_BASE}/un-ingest`, "POST", { category, filename }, ADMIN_ROLE_HEADER);
        toast(data.message || "Un-ingest berhasil", "success");
        loadDocuments();
    } catch (e) {
        toast(e.message, "error");
    }
}

async function deleteDocument(category, filename) {
    try {
        const res = await fetch(`${ADMIN_BASE}/documents/delete`, {
            method: "DELETE",
            headers: { "Content-Type": "application/json", ...ADMIN_ROLE_HEADER },
            body: JSON.stringify({ category, filename })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Gagal menghapus dokumen");
        toast(data.message || "Dokumen dihapus", "success");
        loadDocuments();
    } catch (e) {
        toast(e.message, "error");
    }
}

async function downloadDocument(category, filename) {
    try {
        const url = `${ADMIN_BASE}/documents/download?category=${encodeURIComponent(category)}&filename=${encodeURIComponent(filename)}`;
        const res = await fetch(url, { headers: ADMIN_ROLE_HEADER });
        if (!res.ok) throw new Error("Gagal mengunduh dokumen");
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    } catch (e) {
        toast(e.message, "error");
    }
}

async function syncAll() {
    try {
        const data = await apiJson(`${ADMIN_BASE}/sync`, "POST", {}, ADMIN_ROLE_HEADER);
        toast(data.message || "Sync dimulai", "success");
        setTimeout(loadDocuments, 2000);
    } catch (e) {
        toast(e.message, "error");
    }
}

document.getElementById("doc-category-filter").addEventListener("change", loadDocuments);
document.getElementById("sync-all-btn").addEventListener("click", syncAll);

// ---------- Upload modal ----------

const uploadModal = document.getElementById("upload-modal");
const uploadForm = document.getElementById("upload-form");
const uploadStatus = document.getElementById("upload-status");

function openUploadModal() {
    uploadForm.reset();
    uploadStatus.textContent = "";
    uploadStatus.className = "";
    uploadModal.classList.add("open");
}
function closeUploadModal() {
    uploadModal.classList.remove("open");
}

document.getElementById("upload-open-btn").addEventListener("click", openUploadModal);
document.getElementById("upload-close-btn").addEventListener("click", closeUploadModal);
document.getElementById("upload-cancel-btn").addEventListener("click", closeUploadModal);
uploadModal.addEventListener("click", (e) => { if (e.target === uploadModal) closeUploadModal(); });

uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const category = document.getElementById("upload-category").value;
    const fileInput = document.getElementById("upload-file");
    const replace = document.getElementById("upload-replace").checked;
    const submitBtn = document.getElementById("upload-submit-btn");

    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("category", category);
    formData.append("replace", replace ? "true" : "false");

    submitBtn.disabled = true;
    uploadStatus.textContent = "Mengunggah...";
    uploadStatus.className = "";

    try {
        const res = await fetch(`${ADMIN_BASE}/documents/upload`, {
            method: "POST",
            headers: ADMIN_ROLE_HEADER,
            body: formData
        });
        const data = await res.json();

        if (res.status === 409 && data.exists) {
            uploadStatus.textContent = data.message + " Centang \"Ganti jika sudah ada\" untuk menimpa.";
            uploadStatus.className = "error";
            return;
        }

        if (!res.ok) {
            uploadStatus.textContent = data.error || "Upload gagal";
            uploadStatus.className = "error";
            return;
        }

        if (data.warning) {
            uploadStatus.textContent = data.message || data.warning;
            uploadStatus.className = "error";
            toast("Dokumen diunggah tetapi ditandai untuk review", "error");
        } else {
            uploadStatus.textContent = "Berhasil diunggah";
            uploadStatus.className = "success";
            toast(data.message || "Dokumen berhasil diunggah", "success");
        }

        setTimeout(() => {
            closeUploadModal();
            loadDocuments();
        }, 900);

    } catch (e) {
        uploadStatus.textContent = "Gagal terhubung ke server";
        uploadStatus.className = "error";
    } finally {
        submitBtn.disabled = false;
    }
});

// ---------- Confirm modal ----------

const confirmModal = document.getElementById("confirm-modal");
let confirmCallback = null;

function confirmAction(title, message, onConfirm) {
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-message").textContent = message;
    confirmCallback = onConfirm;
    confirmModal.classList.add("open");
}

document.getElementById("confirm-cancel-btn").addEventListener("click", () => {
    confirmModal.classList.remove("open");
    confirmCallback = null;
});
document.getElementById("confirm-ok-btn").addEventListener("click", () => {
    confirmModal.classList.remove("open");
    if (confirmCallback) confirmCallback();
    confirmCallback = null;
});
confirmModal.addEventListener("click", (e) => {
    if (e.target === confirmModal) {
        confirmModal.classList.remove("open");
        confirmCallback = null;
    }
});

// ---------- Top FAQ ----------

async function loadFaq() {
    const days = document.getElementById("faq-days").value;
    const limit = document.getElementById("faq-limit").value;
    const body = document.getElementById("faq-body");
    body.innerHTML = `<tr><td colspan="4" class="empty-state">Memuat...</td></tr>`;

    try {
        const data = await apiGet(`${API_BASE}/logs/top-faq?days=${days}&limit=${limit}`, ADMIN_ROLE_HEADER);
        body.innerHTML = "";

        if (!data.length) {
            body.innerHTML = `<tr><td colspan="4" class="empty-state">Belum ada data</td></tr>`;
            return;
        }

        data.forEach((row, i) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${i + 1}</td>
                <td>${row.query}</td>
                <td>${fmtNumber(row.total_queries)}</td>
                <td>${fmtDateTime(row.last_asked)}</td>
            `;
            body.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        body.innerHTML = `<tr><td colspan="4" class="empty-state">Gagal memuat data</td></tr>`;
    }
}

document.getElementById("faq-days").addEventListener("change", loadFaq);
document.getElementById("faq-limit").addEventListener("change", loadFaq);

// ---------- Problematic Answers ----------

async function loadProblematicAnswers() {
    const days = document.getElementById("fb-days").value;
    const minDownvotes = document.getElementById("fb-min-downvotes").value;
    const list = document.getElementById("feedback-list");
    list.innerHTML = `<div class="empty-state">Memuat...</div>`;

    try {
        const data = await apiGet(
            `${API_BASE}/analytics/problematic-answers?days=${days}&min_downvotes=${minDownvotes}&limit=20`,
            ADMIN_ROLE_HEADER
        );
        list.innerHTML = "";

        if (!data.length) {
            list.innerHTML = `<div class="empty-state">Tidak ada jawaban bermasalah</div>`;
            return;
        }

        data.forEach(item => {
            const card = document.createElement("div");
            card.className = "qa-card";
            const reasons = (item.reasons || []).filter(Boolean);
            card.innerHTML = `
                <div class="qa-question">${item.question}</div>
                <div class="qa-answer">${item.answer || "-"}</div>
                <div class="qa-meta">
                    <span>👍 ${item.upvotes}</span>
                    <span>👎 ${item.downvotes}</span>
                    <span>${fmtDateTime(item.last_feedback_at)}</span>
                </div>
                ${reasons.length ? `<div class="qa-reasons">${reasons.map(r => `<div class="qa-reason">${r}</div>`).join("")}</div>` : ""}
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
        list.innerHTML = `<div class="empty-state">Gagal memuat data</div>`;
    }
}

document.getElementById("fb-days").addEventListener("change", loadProblematicAnswers);
document.getElementById("fb-min-downvotes").addEventListener("change", loadProblematicAnswers);

// ---------- Flagged Documents ----------

async function loadFlaggedDocuments() {
    const days = document.getElementById("flags-days").value;
    const body = document.getElementById("flags-body");
    body.innerHTML = `<tr><td colspan="5" class="empty-state">Memuat...</td></tr>`;

    try {
        const data = await apiGet(`${API_BASE}/analytics/flagged-documents?days=${days}&limit=20`, ADMIN_ROLE_HEADER);
        body.innerHTML = "";

        if (!data.length) {
            body.innerHTML = `<tr><td colspan="5" class="empty-state">Tidak ada dokumen ditandai</td></tr>`;
            return;
        }

        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.source}</td>
                <td>${row.chunk_index}</td>
                <td>${fmtNumber(row.flagged_count)}</td>
                <td>${fmtNumber(row.total_referenced_count)}</td>
                <td>${row.flag_ratio}</td>
            `;
            body.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        body.innerHTML = `<tr><td colspan="5" class="empty-state">Gagal memuat data</td></tr>`;
    }
}

document.getElementById("flags-days").addEventListener("change", loadFlaggedDocuments);

// ---------- Export logs (topbar action, shown on overview) ----------

function renderExportButton() {
    const actions = document.getElementById("topbar-actions");
    actions.innerHTML = "";
    const btn = document.createElement("button");
    btn.className = "btn-secondary";
    btn.textContent = "Ekspor Log CSV";
    btn.addEventListener("click", exportLogs);
    actions.appendChild(btn);
}

async function exportLogs() {
    try {
        const res = await fetch(`${API_BASE}/logs/export`, { headers: ADMIN_ROLE_HEADER });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || "Gagal mengekspor log");
        }
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "interaction_logs.csv";
        a.click();
        URL.revokeObjectURL(a.href);
    } catch (e) {
        toast(e.message, "error");
    }
}

// ---------- Init ----------

renderExportButton();
loadOverview();