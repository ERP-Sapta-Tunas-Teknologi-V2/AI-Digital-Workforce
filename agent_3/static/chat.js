const form = document.getElementById("chat-form");
const input = document.getElementById("question");
const button = form.querySelector("button");
const messages = document.getElementById("messages");

let isLoading = false;

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
            body: JSON.stringify({question})
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
            bot.className = "message bot";
            bot.textContent = data.answer;
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
                    sources = data.sources || [];
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

                // if (data.type === "done") {
                //     if (sources.length) {
                //         const sourceEl = document.createElement("div");
                //         sourceEl.className = "sources";

                //         const title = document.createElement("b");
                //         title.textContent = "Sumber:";
                //         sourceEl.appendChild(title);

                //         sources.slice(0, 3).forEach(source => {
                //             const item = document.createElement("div");
                //             item.textContent = source.source || "Dokumen";
                //             sourceEl.appendChild(item);
                //         });

                //         bot.appendChild(sourceEl);
                //     }
                // }
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