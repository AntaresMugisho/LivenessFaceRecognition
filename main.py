import logging
import base64
from typing import Annotated

from fastapi import FastAPI, WebSocket, File
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import face_recognition

logging.basicConfig(
    filename="app.log",
    encoding="utf-8",
    filemode="a",
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%d-%m-%Y %H:%M",
)


app = FastAPI()

origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Placeholder for the passport image encoding
passport_encoding = None


def detect_face_position(image):
    """
    Check if the face is detected, centered, and correctly positioned.
    Returns a tuple: (status, feedback_message, face_coordinates).
    """
    face_locations = face_recognition.face_locations(image)

    if not face_locations:
        return False, "No face detected. Please ensure your face is visible in the camera.", None

    # Assume the first detected face is the one we need
    top, right, bottom, left = face_locations[0]
    height, width, _ = image.shape
    face_center_x = (left + right) // 2
    face_center_y = (top + bottom) // 2
    frame_center_x = width // 2
    frame_center_y = height // 2

    # Check if the face is centered
    if abs(face_center_x - frame_center_x) > width * 0.1:
        if face_center_x < frame_center_x:
            return False, "Move your face slightly to the right.", (top, right, bottom, left)
        else:
            return False, "Move your face slightly to the left.", (top, right, bottom, left)

    if abs(face_center_y - frame_center_y) > height * 0.1:
        if face_center_y < frame_center_y:
            return False, "Move your face slightly lower.", (top, right, bottom, left)
        else:
            return False, "Move your face slightly higher.", (top, right, bottom, left)

    # Check if the face is too close or too far
    face_width = right - left
    face_height = bottom - top
    if face_width < width * 0.2 or face_height < height * 0.2:
        return False, "Move closer to the camera.", (top, right, bottom, left)
    if face_width > width * 0.6 or face_height > height * 0.6:
        return False, "Move farther away from the camera.", (top, right, bottom, left)

    return True, "Face position is correct. Hold still.", (top, right, bottom, left)


def match_face(frame, passport_encoding):
    """
    Match the live video frame's face with the passport photo's encoding.
    """
    frame_encodings = face_recognition.face_encodings(frame)
    if frame_encodings:
        matches = face_recognition.compare_faces([passport_encoding], frame_encodings[0])
        match_score = face_recognition.face_distance([passport_encoding], frame_encodings[0])
        return matches[0], 1 - match_score[0]  # Match result and confidence score
    return False, 0.0  # No match


@app.get("/")
def index():
    return {"status": "API is alive"}


@app.post("/upload-passport")
async def upload_passport(image: Annotated[bytes, File()]):
    """
    Endpoint to upload a passport photo and extract its face encoding.
    """
    global passport_encoding
    
    # Decode the image bytes
    nparr = np.frombuffer(image, np.uint8)
    passport_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Get face encoding
    encodings = face_recognition.face_encodings(passport_image)
    if not encodings:
        return {"success": False, "message": "No face detected in the passport photo."}

    passport_encoding = encodings[0]
    return {"success": True, "message": "Passport photo uploaded successfully."}


@app.websocket("/stream")
async def stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video streaming and face matching.
    """
    global passport_encoding
    await websocket.accept()

    if passport_encoding is None:
        await websocket.send_json({"error": "Passport photo not uploaded. Please upload it first."})
        await websocket.close()
        return

    while True:
        try:
            data = await websocket.receive_json()
            frame_data = data.get("frame")  # Base64 string
            nparr = np.frombuffer(base64.b64decode(frame_data.split(",")[1]), np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Check face position
            face_detected, feedback_message, face_coordinates = detect_face_position(frame)

            if not face_detected:
                response = {
                    "face_detected": False,
                    "feedback_message": feedback_message,
                    "match": False,
                    "match_score": 0.0,
                }
            else:
                # Perform face matching
                match, match_score = match_face(frame, passport_encoding)
                response = {
                    "face_detected": True,
                    "feedback_message": feedback_message,
                    "face_coordinates": face_coordinates,
                    "match": match,
                    "match_score": match_score,
                }

            await websocket.send_json(response)

        except Exception as e:
            await websocket.close()
            logging.error(str(e))
            break
