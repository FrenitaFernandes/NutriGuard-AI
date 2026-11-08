const chatForm = document.querySelector("#chat-form");
const chatOutput = document.querySelector("#chat-output");
const contextBox = document.querySelector("#product-context");
const productContext = JSON.parse(sessionStorage.getItem("nutriguard-chat-context") || "null");

if (productContext && contextBox) {
    contextBox.hidden = false;
    contextBox.textContent = `Product context loaded: ${productContext.filename}. You can ask about this label or ask a general food question.`;
}

chatForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = document.querySelector("#question").value.trim();
    if (!question) return;
    chatOutput.innerHTML = "<p>Searching the trusted knowledge base...</p>";
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({question, product_context: productContext})
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw Error(apiError(response, data));
        chatOutput.innerHTML = `<div class="card"><p>${escapeHtml(data.answer).replace(/\n/g, "<br>")}</p>
            <h3>Sources</h3>${list(data.sources?.map((source) => `${source.document}, page ${source.page}`), "No sources returned.")}</div>`;
    } catch (error) {
        chatOutput.innerHTML = `<div class="status error">${escapeHtml(error.message)}</div>`;
    }
});
