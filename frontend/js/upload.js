const fileInput = document.querySelector("#image");
const form = document.querySelector("#upload-form");
const preview = document.querySelector("#preview");
const statusBox = document.querySelector("#status");
const submitButton = form?.querySelector("button[type='submit']");
const dropZone = document.querySelector("#drop-zone");
const selectedFile = document.querySelector("#selected-file");

function showFile(file) {
    if (!file) return;
    if (selectedFile) {
        selectedFile.hidden = false;
        selectedFile.textContent = `${file.name} ready to analyze`;
    }
    if (file.type === "application/pdf") {
        preview.removeAttribute("src");
        preview.alt = `${file.name} PDF selected`;
        preview.hidden = true;
        return;
    }
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
}

fileInput?.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
        showFile(file);
        statusBox.textContent = "Label selected. Add allergies if you’d like, then analyze.";
    }
});

dropZone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
});
dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone?.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    showFile(file);
    statusBox.textContent = "Label selected. Add allergies if you’d like, then analyze.";
});

form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        statusBox.textContent = "Choose a label image first.";
        statusBox.className = "status error";
        return;
    }

    const data = new FormData(form);
    if (!data.get("allergies")) {
        const saved = JSON.parse(localStorage.getItem("nutriguard-allergies") || "[]");
        if (saved.length) data.set("allergies", saved.join(","));
    }

    submitButton.disabled = true;
    statusBox.className = "status";
    statusBox.innerHTML = '<span class="progress-wrap"><span class="progress-dot"></span> Uploading label and starting analysis...</span>';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5 * 60 * 1000);
    try {
        data.set("background", "1");
        const response = await fetch("/api/analyze", {
            method: "POST",
            body: data,
            signal: controller.signal
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw Error(apiError(response, result));
        }
        if (result.status !== "queued") {
            location.href = "/analysis.html";
            return;
        }
        let finished = false;
        while (!finished) {
            await new Promise((resolve) => setTimeout(resolve, 1200));
            const statusResponse = await fetch(`/api/analyze/status/${encodeURIComponent(result.job_id)}`);
            const status = await statusResponse.json();
            if (!statusResponse.ok || !status.success) {
                throw Error(apiError(statusResponse, status));
            }
            if (status.status === "processing") {
                statusBox.innerHTML = '<span class="progress-wrap"><span class="progress-dot"></span> Reading your label... this can take a moment.</span>';
            } else if (status.status === "completed") {
                finished = true;
                statusBox.textContent = "Analysis complete. Opening dashboard...";
                location.href = "/analysis.html";
            } else if (status.status === "failed") {
                throw Error(status.error || "OCR analysis failed.");
            }
        }
    } catch (error) {
        statusBox.textContent = error.name === "AbortError"
            ? "Analysis timed out. Use a clearer, closer label image and try again."
            : error.message || "Analysis failed. Please try again.";
        statusBox.className = "status error";
    } finally {
        clearTimeout(timeout);
        submitButton.disabled = false;
    }
});
