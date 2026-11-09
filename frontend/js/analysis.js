const output = document.querySelector("#analysis-output");

function ingredientCard(item) {
    return `<li><strong>${escapeHtml(item.ingredient)}</strong>${item.description
        ? ` — ${escapeHtml(item.description)}` : ""}${item.allergen && item.allergen.toLowerCase() !== "none"
        ? `<br><span class="badge">Allergen: ${escapeHtml(item.allergen)}</span>` : ""}${item.purpose
        ? `<br><span class="muted">Purpose: ${escapeHtml(item.purpose)}</span>` : ""}</li>`;
}

function additiveCard(item) {
    return `<li><strong>${escapeHtml(item.ingredient || "Unidentified additive")}</strong> (${escapeHtml(item.code)})${item.description
        ? ` — ${escapeHtml(item.description)}` : ""}${item.category
        ? `<br><span class="muted">${escapeHtml(item.category)}</span>` : ""}${item.purpose
        ? `<br><span class="muted">Purpose: ${escapeHtml(item.purpose)}</span>` : ""}</li>`;
}

function nutritionMarkup(nutrition) {
    const entries = Object.entries(nutrition || {})
        .filter(([, item]) => item && item.value && item.unit);
    return entries.length
        ? `<ul class="list">${entries.map(([name, item]) =>
            `<li><strong>${escapeHtml(name.replaceAll("_", " "))}:</strong> ${escapeHtml(item.value)} ${escapeHtml(item.unit)}${item.basis ? ` <span class="muted">(${escapeHtml(item.basis)})</span>` : ""}</li>`
        ).join("")}</ul>`
        : '<p class="muted">No structured nutrition values were detected.</p>';
}

function chatMarkup(messages) {
    return `<section class="card chat-card result-section"><div class="chat-header"><span class="chat-avatar" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.5 8.5 0 0 1-3.5-.8L4 20l1.5-3.5A7.4 7.4 0 0 1 4.5 12 7.5 7.5 0 0 1 12 4.5a7.5 7.5 0 0 1 8 7Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></svg></span><div><h2>Ask NutriGuard</h2><p class="muted">A clear answer about the product on your screen.</p></div></div>
        <div id="chat-messages">${messages.map((message) =>
        `<div class="${message.role === "user" ? "chat-user" : "chat-assistant"}"><strong>${message.role === "user" ? "You" : "NutriGuard"}</strong><p>${escapeHtml(message.content).replace(/\n/g, "<br>")}</p>${message.sources?.length ? `<small>Sources: ${message.sources.map((source) => source.url ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">${escapeHtml(source.document)}, page ${escapeHtml(source.page)}</a>` : `${escapeHtml(source.document)}, page ${escapeHtml(source.page)}`).join("; ")}</small>` : ""}</div>`
    ).join("")}</div>
        <form id="dashboard-chat-form" class="chat-composer"><textarea id="dashboard-question" placeholder="Ask a follow-up question..." aria-label="Ask about this product"></textarea><button type="submit">Send <span aria-hidden="true">→</span></button><span id="chat-status" class="muted" role="status"></span></form>
    </section>`;
}

async function loadDashboard() {
    const response = await fetch("/api/product");
    const data = await response.json();
    if (!data.product) {
        output.innerHTML = '<div class="status error">No product is loaded. <a href="/upload.html">Scan a label</a>.</div>';
        return;
    }

    const product = data.product;
    const analysis = product.ingredient_analysis;
    const allergy = product.allergy_analysis;
    const sections = product.ocr.sections;
    const alerts = allergy.user_allergies?.length
        ? allergy.results.map((item) => `<div class="${item.status === "MATCH_FOUND" ? "danger" : item.status === "POSSIBLE_CROSS_CONTAMINATION" ? "warning" : "status"}"><strong>${escapeHtml(item.allergen)}</strong>: ${escapeHtml(item.status.replaceAll("_", " "))}<br><span class="muted">${escapeHtml(item.evidence.join("; ") || "No matching declaration detected")}</span></div>`).join("")
        : '<p class="muted">No allergies selected for this scan.</p>';

    output.innerHTML = `
        <div class="dashboard-toolbar"><div><span class="eyebrow">Current product</span><p class="muted">Your analysis stays here until you clear it.</p></div><div class="actions"><button type="button" id="clear-product" class="button danger">Clear product</button><a class="button" href="/upload.html">Scan another label</a></div></div>
        <section class="card result-section product-header">${product.preview_url ? `<img src="${escapeHtml(product.preview_url)}" alt="Scanned label" class="product-preview">` : ""}<div><h2>${escapeHtml(product.filename)}</h2><p class="muted">Analysis completed in ${escapeHtml(product.duration_ms)} ms.</p></div></section>
        <div class="grid result-section"><section class="card"><h2>Ingredients</h2>${analysis.ingredient_matches?.length ? `<ul class="list">${analysis.ingredient_matches.map(ingredientCard).join("")}</ul>` : '<p class="muted">No known ingredients were recognized.</p>'}<h3>Additives</h3>${analysis.additive_codes?.length ? `<ul class="list">${analysis.additive_codes.map(additiveCard).join("")}</ul>` : '<p class="muted">No supported INS/E-numbers identified.</p>'}</section>
        <section class="card"><h2>Allergy warnings</h2>${alerts}<p class="hint">${escapeHtml(allergy.safety_note)}</p></section></div>
        <section class="card result-section"><h2>Label information</h2><div class="grid"><div><h3>Contains</h3><p>${escapeHtml(sections.contains || "Not detected")}</p></div><div><h3>May contain</h3><p>${escapeHtml(sections.may_contain || "Not detected")}</p></div><div><h3>Nutrition</h3>${nutritionMarkup(analysis.nutrition)}<p class="hint">${escapeHtml(analysis.consumption_guidance?.summary || "")}</p>${analysis.consumption_guidance?.sources?.length ? `<small>Guidance: ${analysis.consumption_guidance.sources.map((source) => `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">${escapeHtml(source.name)}</a>`).join("; ")}</small>` : ""}<details><summary>OCR nutrition text</summary><p>${escapeHtml(sections.nutrition || "Not detected")}</p></details></div></div></section>
        <details class="card result-section"><summary>Review technical details</summary><p>${escapeHtml(analysis.unmatched_words_for_review?.join(", ") || "No unmatched words")}</p>${product.ocr.warnings?.map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("") || ""}<div class="raw">${escapeHtml(product.ocr.raw_text)}</div></details>
        ${chatMarkup(data.messages || [])}`;

    document.querySelector("#clear-product").addEventListener("click", async () => {
        if (!window.confirm("Clear this product and its assistant conversation?")) return;
        await fetch("/api/product/current", {method: "DELETE"});
        location.reload();
    });
    document.querySelector("#dashboard-chat-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = document.querySelector("#dashboard-question").value.trim();
        const status = document.querySelector("#chat-status");
        if (!question) return;
        status.textContent = "Thinking...";
        document.querySelector("#dashboard-chat-form button").disabled = true;
        try {
            const response = await fetch("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({question})});
            const result = await response.json();
            if (!response.ok || !result.success) throw Error(apiError(response, result));
            document.querySelector("#dashboard-question").value = "";
            await loadDashboard();
        } catch (error) {
            status.textContent = error.message || "The assistant is unavailable.";
        } finally {
            document.querySelector("#dashboard-chat-form button").disabled = false;
        }
    });
}

loadDashboard().catch(() => {
    output.innerHTML = '<div class="status error">The dashboard could not be loaded. Please try again.</div>';
});
