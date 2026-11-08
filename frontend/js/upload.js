const fileInput = document.querySelector("#image");
const form = document.querySelector("#upload-form");
const preview = document.querySelector("#preview");
const statusBox = document.querySelector("#status");
const submitButton = form?.querySelector("button[type='submit']");

fileInput?.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) {
        preview.src = URL.createObjectURL(file);
        preview.hidden = false;
        statusBox.textContent = `${file.name} selected.`;
    }
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
    statusBox.textContent = "Uploading image and initializing OCR (CPU processing may take up to 2 minutes)...";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5 * 60 * 1000);
    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            body: data,
            signal: controller.signal
        });
        statusBox.textContent = "Extracting label text and checking ingredients...";
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw Error(apiError(response, result));
        }
        statusBox.textContent = "Preparing results...";
        sessionStorage.setItem("nutriguard-analysis", JSON.stringify(result));
        location.href = "/analysis.html";
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
