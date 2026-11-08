const video = document.querySelector("#camera-video");
const cameraStatus = document.querySelector("#camera-status");
let cameraStream;

function stopCamera() {
    cameraStream?.getTracks().forEach((track) => track.stop());
    cameraStream = undefined;
}

document.querySelector("#start-camera")?.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
        cameraStatus.textContent = "Camera capture is not supported on this device.";
        cameraStatus.className = "status error";
        return;
    }
    try {
        stopCamera();
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false
        });
        video.srcObject = cameraStream;
        cameraStatus.textContent = "Camera ready. Capture the label in good light.";
        cameraStatus.className = "status";
    } catch (error) {
        cameraStatus.textContent = "Camera permission was denied. Use image upload instead.";
        cameraStatus.className = "status error";
    }
});

document.querySelector("#capture")?.addEventListener("click", () => {
    if (!cameraStream || !video.videoWidth) {
        cameraStatus.textContent = "Start the camera before capturing.";
        cameraStatus.className = "status error";
        return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
        if (!blob) return;
        const file = new File([blob], "camera-label.jpg", { type: "image/jpeg" });
        const transfer = new DataTransfer();
        transfer.items.add(file);
        document.querySelector("#image").files = transfer.files;
        document.querySelector("#preview").src = URL.createObjectURL(file);
        document.querySelector("#preview").hidden = false;
        cameraStatus.textContent = "Capture attached. Submit to analyze.";
        stopCamera();
    }, "image/jpeg", 0.95);
});

window.addEventListener("pagehide", stopCamera);
