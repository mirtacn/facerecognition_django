"""
Liveness Detection Module - Port langsung dari antispoof_utils.py
Logic 100% sama - digunakan untuk web backend
"""
import cv2
import numpy as np
import tensorflow as tf
from mtcnn import MTCNN
import base64
import io
import time
import os
import sys
from PIL import Image

# Force reload module jika ada
if 'mediapipe_utils' in sys.modules:
    del sys.modules['mediapipe_utils']

from mediapipe_utils import process_liveness

# ===============================
# CONFIG
# ===============================
IMG_SIZE = 128
SPOOF_THRESHOLD = 0.7
GAMMA_VALUE = 1.4   

# ===============================
# GAMMA CORRECTION FUNCTION
# ===============================
def apply_gamma_correction(image, gamma=1.4):
    invGamma = 1.0 / gamma
    table = np.array([
        ((i / 255.0) ** invGamma) * 255
        for i in np.arange(256)
    ]).astype("uint8")
    return cv2.LUT(image, table)

# ===============================
# LOAD MODEL & DETECTOR (GLOBAL)
# ===============================
model = None
detector = None

# ===============================
# STATE (GLOBAL)
# ===============================
state = {
    "blink_count": 0,
    "eye_closed": False,
    "eye_closed_count": 0,
    "head_stage": "CENTER",
    "verified": False,
    "last_blink_time": time.time(),
}

previous_face_box = None

# ===============================
# INIT FUNCTION
# ===============================
def init_liveness_detection():
    """Inisialisasi model dan detector"""
    global model, detector
    
    try:
        if detector is None:
            detector = MTCNN()
            print("[LIVENESS] MTCNN detector initialized")
        
        if model is None:
            model_path = "model_antispoof_128x128_final.h5"
            if os.path.exists(model_path):
                model = tf.keras.models.load_model(model_path)
                print("[LIVENESS] Model loaded successfully")
            else:
                print(f"[ERROR] Model not found at {model_path}")
                raise FileNotFoundError(f"Model tidak ditemukan: {model_path}")
        
        print("[LIVENESS] Init complete")
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        raise

# ===============================
# DECODE BASE64
# ===============================
def decode_base64_image(image_base64):
    """Convert base64 ke OpenCV frame"""
    try:
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        return frame
    except Exception as e:
        print(f"[ERROR] Failed to decode: {e}")
        return None

# ===============================
# MAIN PROCESS FUNCTION
# ===============================
def process_frame_liveness(frame_base64):
    """
    Process single frame untuk liveness detection
    Return: dict dengan hasil detection
    
    Logic sama 100% dengan antispoof_utils.py:
    1. Decode base64 frame
    2. Apply gamma correction ke full frame
    3. Detect faces dengan MTCNN
    4. Check spoof score dengan CNN model
    5. Process blink detection dengan mediapipe
    6. Tentukan status: NO_FACE / SPOOF / VERIFYING / REAL
    7. Return response dengan box coordinates
    """
    global state, detector, model, previous_face_box
    
    try:
        # Initialize jika belum
        if detector is None or model is None:
            init_liveness_detection()
        
        # Decode frame
        frame = decode_base64_image(frame_base64)
        if frame is None:
            return {
                "success": False,
                "error": "Failed to decode image",
                "status": "ERROR",
                "face_detected": False
            }
        
        # ===============================
        # APPLY GAMMA TO FULL FRAME
        # ===============================
        frame_gamma = apply_gamma_correction(frame, GAMMA_VALUE)
        
        rgb = cv2.cvtColor(frame_gamma, cv2.COLOR_BGR2RGB)
        detections = detector.detect_faces(rgb)
        
        # ===============================
        # NO FACE DETECTED
        # ===============================
        if len(detections) == 0:
            state["blink_count"] = 0
            state["verified"] = False
            previous_face_box = None
            
            return {
                "success": True,
                "status": "NO_FACE",
                "blink_count": 0,
                "spoof_score": 0.5,
                "verified": False,
                "message": "NO FACE DETECTED",
                "face_detected": False,
                "box": None,
                "frame_width": frame_gamma.shape[1],
                "frame_height": frame_gamma.shape[0]
            }
        
        # ===============================
        # PROCESS FACE
        # ===============================
        for det in detections:
            if det["confidence"] < 0.9:
                continue
            
            x, y, w, h = det["box"]
            x, y = max(0, x), max(0, y)
            
            # ===============================
            # RESET JIKA ORANG BERGANTI
            # ===============================
            current_face_box = (x, y, w, h)
            if previous_face_box is not None:
                px, py, pw, ph = previous_face_box
                distance = np.sqrt((x - px)**2 + (y - py)**2)
                if distance > 80:
                    state["blink_count"] = 0
                    state["verified"] = False
            previous_face_box = current_face_box
            
            # ===============================
            # CNN ANTISPOOF (WITH GAMMA)
            # ===============================
            face = frame_gamma[y:y+h, x:x+w]
            if face.size == 0:
                continue
            
            face_resized = cv2.resize(face, (IMG_SIZE, IMG_SIZE))
            face_input = face_resized / 255.0
            face_input = np.expand_dims(face_input, axis=0)
            
            spoof_score = float(model.predict(face_input, verbose=0)[0][0])
            print(f"[DEBUG] Spoof Score = {spoof_score:.4f}, Threshold = {SPOOF_THRESHOLD}")
            
            # ===============================
            # LIVENESS (BLINK)
            # ===============================
            state = process_liveness(frame_gamma, frame_gamma.shape, state)
            
            # ===============================
            # UI STATUS LOGIC
            # ===============================
            color = (0, 255, 255)  # Kuning
            status = "LIVENESS_CHECK"
            message = f"Liveness Check... (Blinks: {state['blink_count']}/2)"
            verified = False
            
            if spoof_score < SPOOF_THRESHOLD:
                color = (0, 0, 255)  # Merah
                status = "SPOOF"
                message = "Spoof detected! Fake Face Pattern"
                verified = False
                state["verified"] = False
            
            elif state["blink_count"] >= 2:
                color = (0, 255, 0)  # Hijau
                status = "REAL"
                message = "Proses Face Recognition"
                verified = True
                state["verified"] = True
            
            # ===============================
            # RETURN RESPONSE
            # ===============================
            return {
                "success": True,
                "status": status,
                "message": message,
                "blink_count": state["blink_count"],
                "spoof_score": spoof_score,
                "verified": verified,
                "face_detected": True,
                "box": {
                    "x": int(x),
                    "y": int(y),
                    "w": int(w),
                    "h": int(h)
                },
                "frame_width": frame_gamma.shape[1],
                "frame_height": frame_gamma.shape[0],
                "color": color  # (B, G, R)
            }
        
        # Fallback if no valid detection
        return {
            "success": True,
            "status": "NO_FACE",
            "blink_count": 0,
            "spoof_score": 0.5,
            "verified": False,
            "message": "No valid face detected",
            "face_detected": False,
            "box": None,
            "frame_width": frame_gamma.shape[1],
            "frame_height": frame_gamma.shape[0]
        }
        
    except Exception as e:
        print(f"[ERROR] process_frame_liveness: {e}")
        return {
            "success": False,
            "error": str(e),
            "status": "ERROR",
            "face_detected": False
        }

# ===============================
# STATE MANAGEMENT
# ===============================
def reset_detection_state():
    """Reset state untuk detection baru"""
    global state, previous_face_box
    
    state = {
        "blink_count": 0,
        "eye_closed": False,
        "eye_closed_count": 0,
        "head_stage": "CENTER",
        "verified": False,
        "last_blink_time": time.time(),
    }
    previous_face_box = None
    print("[LIVENESS] State reset")

def get_detection_state():
    """Get current state"""
    global state
    return state.copy()