const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file");
const categoryInput = document.getElementById("category");
const uploadButton = document.getElementById("upload-button");
const uploadMessage = document.getElementById("upload-message");

const documentsEl = document.getElementById("documents");
const emptyEl = document.getElementById("empty");
const countEl = document.getElementById("document-count");

const filterCategory = document.getElementById("filter-category");
const refreshButton = document.getElementById("refresh-button");

const categoryMap = {
    sop: "SOP",
    datasheet: "Datasheet",
    pricelist: "Pricelist",
    guide: "Technical Guide",
    meeting: "Meeting Notes",
    training: "Training Material"
};

let documents = [];

async function api(url, options = {}) {
    const response = await fetch(url, options);

    let data = {};
    try {
        data = await response.json();
    } catch {}

    if (!response.ok) {
        const error = new Error(data.error || "Terjadi kesalahan.");
        error.status = response.status;
        error.data = data;
        throw error;
    }

    return data;
}

function formatSize(bytes) {
    if (!bytes) return "-";

    const units = ["B", "KB", "MB", "GB"];
    let size = bytes;
    let unit = 0;

    while (size >= 1024 && unit < units.length - 1) {
        size /= 1024;
        unit++;
    }

    return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function statusLabel(status) {
    const labels = {
        not_ingested: "Belum ingest",
        processing: "Processing",
        success: "Sudah ingest",
        failed: "Gagal"
    };

    return labels[status] || status;
}

function statusClass(status) {
    return `status status-${status}`;
}

function renderDocuments() {
    const category = filterCategory.value;

    const filtered = [...(
        category
            ? documents.filter(doc => doc.category === category)
            : documents
    )].sort((a, b) =>
        new Date(b.uploaded_at) - new Date(a.uploaded_at)
    );

    documentsEl.innerHTML = "";

    countEl.textContent = `${filtered.length} dokumen`;
    emptyEl.style.display = filtered.length ? "none" : "block";

    filtered.forEach(doc => {
        const tr = document.createElement("tr");

        const ingestDisabled =
            doc.ingest_status === "processing";

        tr.innerHTML = `
            <td>
                <div class="filename">${escapeHtml(doc.filename)}</div>
                <div class="path">${escapeHtml(doc.path)}</div>
                <div class="flags">${flagBadges(doc.flags)}</div>
            </td>

            <td>${escapeHtml(categoryMap[doc.category] ?? doc.category)}</td>

            <td>${formatSize(doc.size)}</td>

            <td>
                <div>${doc.uploaded_at_wib || "-"}</div>
            </td>

            <td>
                <span class="${statusClass(doc.ingest_status)}">
                    ${statusLabel(doc.ingest_status)}
                </span>
            </td>

            <td>
                ${doc.last_ingested_at_wib || "-"}
            </td>

            <td>
                <button
                    class="download-button"
                    data-action="download"
                    data-category="${escapeAttr(doc.category)}"
                    data-filename="${escapeAttr(doc.filename)}">
                    Download
                </button>

                <button
                    class="ingest-button"
                    data-action="ingest"
                    data-category="${escapeAttr(doc.category)}"
                    data-filename="${escapeAttr(doc.filename)}"
                    ${doc.ingest_status === "processing" ? "disabled" : ""}
                >
                    ${doc.ingest_status === "processing" ? "Processing..." : "Ingest"}
                </button>

                ${
                    doc.ingest_status !== "not_ingested"
                    ? `
                    <button
                        class="un-ingest-button"
                        data-action="un-ingest"
                        data-category="${escapeAttr(doc.category)}"
                        data-filename="${escapeAttr(doc.filename)}"
                    >
                        Un-ingest
                    </button>
                    `
                    : ""
                }

                <button
                    class="delete-button"
                    data-action="delete"
                    data-category="${escapeAttr(doc.category)}"
                    data-filename="${escapeAttr(doc.filename)}"
                >
                    Hapus
                </button>
            </td>
        `;

        documentsEl.appendChild(tr);
    });
}

async function loadDocuments() {
    try {
        refreshButton.disabled = true;

        const category = filterCategory.value;
        const url = category
            ? `/api/admin/documents?category=${encodeURIComponent(category)}`
            : "/api/admin/documents";

        documents = await api(url);
        renderDocuments();
    } catch (error) {
        alert(error.message);
    } finally {
        refreshButton.disabled = false;
    }
}

uploadForm.addEventListener("submit", async event => {
    event.preventDefault();

    const file = fileInput.files[0];
    const category = categoryInput.value;

    if (!file || !category) {
        return;
    }

    await uploadFile(file, category, false);
});

async function uploadFile(file, category, replace) {
    const formData = new FormData();

    formData.append("file", file);
    formData.append("category", category);
    formData.append("replace", replace);

    try {
        uploadButton.disabled = true;
        uploadButton.textContent = "Uploading...";
        uploadMessage.textContent = "";

        const data = await api("/api/admin/documents/upload", {
            method: "POST",
            body: formData
        });

        uploadMessage.className = "success";
        uploadMessage.textContent = data.message;

        uploadForm.reset();
        await loadDocuments();

    } catch (error) {
        if (error.status === 409 && error.data?.exists) {
            const replace = confirm(
                `${error.data.message}\n\nKlik OK untuk replace file.`
            );

            if (replace) {
                await uploadFile(file, category, true);
            }

            return;
        }

        uploadMessage.className = "error";
        uploadMessage.textContent = error.message;

    } finally {
        uploadButton.disabled = false;
        uploadButton.textContent = "Upload";
    }
}

documentsEl.addEventListener("click", async event => {
    const button = event.target.closest("button");
    if (!button) return;

    const action = button.dataset.action;
    const category = button.dataset.category;
    const filename = button.dataset.filename;

    if (action === "download") {
        downloadDocument(category, filename);
        return;
    }

    if (action === "ingest") {
        await ingestDocument(category, filename);
    }

    if (action === "un-ingest") {
        await unIngestDocument(category, filename);
    }

    if (action === "delete") {
        await deleteDocument(category, filename);
    }
});

function downloadDocument(category, filename) {
    const params = new URLSearchParams({
        category,
        filename
    });

    window.location.href = `/api/admin/documents/download?${params}`;
}

async function ingestDocument(category, filename) {
    if (!confirm(`Ingest "${filename}" ke vector database?`)) {
        return;
    }

    try {
        await api("/api/admin/ingest", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                category,
                filename
            })
        });

        await loadDocuments();
    } catch (error) {
        alert(error.message);
    }
}

async function unIngestDocument(category, filename) {
    if (!confirm(
        `Un-ingest "${filename}"?\n\n` +
        `File tetap ada di MinIO, tetapi data vector akan dihapus.`
    )) {
        return;
    }

    try {
        await api("/api/admin/un-ingest", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                category,
                filename
            })
        });

        await loadDocuments();
    } catch (error) {
        alert(error.message);
    }
}

async function deleteDocument(category, filename) {
    if (!confirm(
        `Hapus "${filename}"?\n\n` +
        `File MinIO dan data vector Supabase akan dihapus.`
    )) {
        return;
    }

    try {
        await api("/api/admin/documents/delete", {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                category,
                filename
            })
        });

        await loadDocuments();
    } catch (error) {
        alert(error.message);
    }
}

filterCategory.addEventListener("change", loadDocuments);
refreshButton.addEventListener("click", loadDocuments);

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
    return escapeHtml(value);
}

function flagBadges(flags) {
    if (!flags || !flags.length) return "";

    const labels = {
        duplicate: "Duplikat",
        confidential: "Rahasia",
        stale: "Usang"
    };

    return flags.map(f => {
        const title = f.type === "duplicate" && f.duplicate_of
            ? `Duplikat dari: ${f.duplicate_of}`
            : (f.detail || "");
        return `<span class="flag-badge flag-${f.type}" title="${escapeAttr(title)}">${labels[f.type] || f.type}</span>`;
    }).join(" ");
}

function isBlocked(flags) {
    return (flags || []).some(f => f.type === "duplicate" || f.type === "confidential");
}

loadDocuments();

setInterval(loadDocuments, 60000);