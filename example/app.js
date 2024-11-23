const video = document.getElementById("video");
const status = document.getElementById("status");
const passportInput = document.getElementById("passportInput");
const uploadButton = document.getElementById("uploadButton");
const uploadStatus = document.getElementById("uploadStatus");

const websocketUrl = "ws://127.0.0.1:8000/stream";
const uploadUrl = "http://127.0.0.1:8000/upload-passport";


// 1. Passeport image upload
async function uploadPassport() {
    const file = passportInput.files[0];
    if (!file) {
        uploadStatus.textContent = "Upload Status: Please select a file first.";
        return;
    }

    const formData = new FormData();
    formData.append("image", file);

    try {
        const response = await fetch(uploadUrl, {
            method: "POST",
            body: formData,
            headers:{
                "allow-origin": "*"
            }
        });

        const result = await response.json();
        if (result.success) {
            uploadStatus.textContent = `Upload Status: ${result.message}`;
            console.log("Passport uploaded successfully.");

            // Initialize web socket (On another page)
            initialize_ws();

        } else {
            uploadStatus.textContent = `Upload Status: ${result.message}`;
            console.error("Passport upload failed:", result.message);
        }
    } catch (err) {
        uploadStatus.textContent = "Upload Status: An error occurred while uploading.";
        console.error("Error uploading passport:", err);
    }
}

// Attach upload event listener
uploadButton.addEventListener("click", uploadPassport);


// Initialize WS
async function initialize_ws() {
    const stream = await startCamera();
    startWebSocket(stream);
}


// 2. Video streaming with Web socket

// Access the user's camera
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        return stream;
    } catch (err) {
        console.log("Error accessing the camera:", err);
        status.textContent = "Status: Camera access failed.";
        throw err;
    }
}

// Convert video frames to Base64
function getFrameData(videoElement, canvas) {
    const context = canvas.getContext("2d");
    context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg"); // Encode frame to Base64
}


// WebSocket communication

async function startWebSocket(stream) {
    const websocket = new WebSocket(websocketUrl);

    websocket.onopen = () => {
        status.textContent = "Status: Connected to server.";
        console.log("WebSocket connection established.");
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Server response:", data);

        if (data.error) {
            status.textContent = `Error: ${data.error}`;
        } else if (data.face_detected) {
            status.textContent = `Face Detected: Match ${data.match ? "found" : "not found"} (Score: ${data.match_score.toFixed(2)})`;
        } else {
            status.textContent = `Face Not Detected: ${data.feedback_message}`;
        }
    };

    websocket.onclose = () => {
        status.textContent = "Status: Disconnected from server.";
        console.log("WebSocket connection closed.");
    };

    websocket.onerror = (err) => {
        console.error("WebSocket error:", err);
        status.textContent = "Status: WebSocket error.";
    };

    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;

    // Send video frames periodically
    const intervalId = setInterval(() => {
        if (websocket.readyState === WebSocket.OPEN) {
            const frameData = getFrameData(video, canvas);
            websocket.send(JSON.stringify({ frame: frameData }));
        }
    }, 100); // Send every 100ms (just an example)

    // Stop sending frames if WebSocket closes
    websocket.onclose = () => {
        clearInterval(intervalId);
    };
}



