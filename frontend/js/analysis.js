const output = document.querySelector("#analysis-output");
const result = JSON.parse(sessionStorage.getItem("nutriguard-analysis") || "null");

function ingredientCard(item) {
    const aliases = item.alternative_names?.length
        ? `<span class="muted">Also known as: ${escapeHtml(item.alternative_names.join(", "))}</span>`
        : "";
    return `<li><strong>${escapeHtml(item.ingredient)}</strong>${item.description
        ? ` — ${escapeHtml(item.description)}`
        : ""}${item.allergen && item.allergen.toLowerCase() !== "none"
        ? `<br><span class="badge">Supported allergen: ${escapeHtml(item.allergen)}</span>`
        : ""}<br>${aliases}</li>`;
}

function additiveCard(item) {
    return `<li><strong>${escapeHtml(item.ingredient || "Unknown additive")}</strong> (${escapeHtml(item.code)})
        ${item.description ? `— ${escapeHtml(item.description)}` : ""}
        ${item.category ? `<br><span class="muted">${escapeHtml(item.category)}</span>` : ""}</li>`;
}

if (output) {
    if (!result) {
        output.innerHTML = '<div class="status error">No analysis found. <a href="/upload.html">Scan a label</a>.</div>';
    } else {
        const analysis = result.ingredient_analysis;
        const allergy = result.allergy_analysis;
        const sections = result.ocr.sections;
        const hasProfile = allergy.user_allergies?.length > 0;
        const alertMarkup = hasProfile
            ? allergy.results.map((item) => `<div class="${item.status === "MATCH_FOUND" ? "danger" : item.status === "POSSIBLE_CROSS_CONTAMINATION" ? "warning" : "status"}">
                <strong>${escapeHtml(item.allergen)}</strong>: ${escapeHtml(item.status.replaceAll("_", " "))}
                <br><span class="muted">${escapeHtml(item.evidence.join("; ") || "No matching declaration detected")}</span>
            </div>`).join("")
            : '<p class="muted">No allergies selected. Personalized alerts are hidden.</p>';

        output.innerHTML = `
            <div class="status">Image: <strong>${escapeHtml(result.filename)}</strong> (${result.ocr.image_width} × ${result.ocr.image_height})</div>
            <div class="warning"><strong>Review notice:</strong> A negative match is not proof of safety. OCR may miss small or unclear text.</div>
            <div class="actions"><button type="button" id="explain-product">Explain this product</button><a class="button secondary" href="/upload.html">Scan another label</a></div>
            <div class="grid result-section">
                <section class="card">
                    <h2>Recognized ingredients</h2>
                    ${analysis.ingredient_matches?.length
                        ? `<ul class="list">${analysis.ingredient_matches.map(ingredientCard).join("")}</ul>`
                        : '<p class="muted">No known ingredients were recognized.</p>'}
                    <h3>INS / E-numbers and additives</h3>
                    ${analysis.additive_codes?.length
                        ? `<ul class="list">${analysis.additive_codes.map(additiveCard).join("")}</ul>`
                        : '<p class="muted">No supported INS/E-numbers identified.</p>'}
                    <h3>Needs a closer look</h3>${list(analysis.unmatched_words_for_review, "No unmatched words")}
                </section>
                <section class="card">
                    <h2>${hasProfile ? "Personalized allergy alerts" : "Allergy alerts"}</h2>
                    ${alertMarkup}
                    ${hasProfile ? `<p class="hint">${escapeHtml(allergy.safety_note)}</p>` : ""}
                </section>
            </div>
            <section class="card result-section">
                <h2>Label declarations</h2>
                <div class="grid">
                    <div><h3>Contains</h3>${list(analysis.contains_allergens, "No Contains declaration detected")}<p>${escapeHtml(sections.contains || "Not detected")}</p></div>
                    <div><h3>May Contain</h3>${list(analysis.may_contain_allergens, "No May Contain declaration detected")}<p>${escapeHtml(sections.may_contain || "Not detected")}</p></div>
                </div>
                <h3>Nutrition</h3><p>${escapeHtml(sections.nutrition || "Not detected")}</p>
            </section>
            <details class="card result-section">
                <summary>Technical OCR text</summary>
                <p class="muted">Use this to verify what the scanner read from the image.</p>
                <h3>Ingredient text</h3><div class="raw">${escapeHtml(analysis.original_ingredient_text || "Not detected")}</div>
                <h3>Full OCR output</h3><div class="raw">${escapeHtml(result.ocr.raw_text)}</div>
                ${result.ocr.warnings?.map((warning) => `<p class="warning">${escapeHtml(warning)}</p>`).join("") || ""}
            </details>`;

        document.querySelector("#explain-product")?.addEventListener("click", () => {
            const productContext = {
                filename: result.filename,
                ingredients: analysis.ingredient_matches,
                additives: analysis.additive_codes,
                contains: analysis.contains_allergens,
                may_contain: analysis.may_contain_allergens,
                selected_allergies: allergy.user_allergies || []
            };
            sessionStorage.setItem("nutriguard-chat-context", JSON.stringify(productContext));
            location.href = "/chat.html";
        });
    }
}
