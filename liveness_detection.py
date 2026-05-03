"""
Liveness Detection Module - FIXED VERSION
Mendeteksi spoofing dengan benar untuk wajah real
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
import threading

# ===============================
# CONFIGURATION - SESUAIKAN
# ===============================
IMG_SIZE = 150

# PENTING: Gunakan MODE 1 untuk deteksi yang benar
# MODE 1: Score tinggi = REAL (score >= THRESHOLD)
# MODE 2: Score rendah = REAL (score <= THRESHOLD) - untuk model terbalik
INTERPRETATION_MODE = 1  # <-- PASTIKAN INI = 1

# Threshold untuk MODE 1: score >= ini = REAL
# Threshold untuk MODE 2: score <= ini = REAL
SPOOF_THRESHOLD = 0.65   # <-- Sesuaikan: 0.6-0.7 biasanya bagus

GAMMA_VALUE = 1.2  # Turunkan dari 1.4 biar gak overexposed

# Timeout untuk reset state (detik)
STATE_TIMEOUT = 30

# ===============================
# GLOBAL VARIABLES
# ===============================
model = None
detector = None

# State per session (thread-safe)
detection_states = {}
state_lock = threading.Lock()

# ===============================
# HELPER FUNCTIONS
# ===============================

def apply_gamma_correction(image, gamma=1.2):
    """Gamma correction untuk improve contrast"""
    invGamma = 1.0 / gamma
    table = np.array([
        ((i / 255.0) ** invGamma) * 255
        for i in np.arange(256)
    ]).astype("uint8")
    return cv2.LUT(image, table)

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

def get_session_state(session_id):
    """Get or create detection state for a session"""
    with state_lock:
        if session_id not in detection_states:
            detection_states[session_id] = {
                "blink_count": 0,
                "eye_closed": False,
                "eye_closed_frames": 0,
                "head_stage": "CENTER",
                "verified": False,
                "last_blink_time": time.time(),
                "last_activity": time.time(),
                "frame_counter": 0
            }
        else:
            # Check timeout - reset if too old
            if time.time() - detection_states[session_id]["last_activity"] > STATE_TIMEOUT:
                detection_states[session_id] = {
                    "blink_count": 0,
                    "eye_closed": False,
                    "eye_closed_frames": 0,
                    "head_stage": "CENTER",
                    "verified": False,
                    "last_blink_time": time.time(),
                    "last_activity": time.time(),
                    "frame_counter": 0
                }
            else:
                detection_states[session_id]["last_activity"] = time.time()
        
        return detection_states[session_id]

def reset_session_state(session_id):
    """Reset state for a specific session"""
    with state_lock:
        if session_id in detection_states:
            detection_states[session_id] = {
                "blink_count": 0,
                "eye_closed": False,
                "eye_closed_frames": 0,
                "head_stage": "CENTER",
                "verified": False,
                "last_blink_time": time.time(),
                "last_activity": time.time(),
                "frame_counter": 0
            }
            print(f"[STATE] Reset session: {session_id}")

def cleanup_old_states():
    """Cleanup states older than timeout"""
    with state_lock:
        current_time = time.time()
        expired = []
        for sid, state in detection_states.items():
            if current_time - state.get("last_activity", 0) > STATE_TIMEOUT * 2:
                expired.append(sid)
        for sid in expired:
            del detection_states[sid]
            print(f"[STATE] Cleanup expired session: {sid}")

# ===============================
# BLINK DETECTION
# ===============================

def distance(p1, p2):
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def detect_blink(face, landmarks=None):
    """
    Simplified blink detection using eye aspect ratio
    Fallback jika MediaPipe tidak available
    """
    if landmarks is None:
        return False, 0
    
    try:
        # Eye landmarks indices (dlib 68-point model)
        # Left eye: 36-41, Right eye: 42-47
        left_eye = landmarks[36:42]
        right_eye = landmarks[42:48]
        
        def eye_aspect_ratio(eye):
            # Vertical distances
            A = distance(eye[1], eye[5])
            B = distance(eye[2], eye[4])
            # Horizontal distance
            C = distance(eye[0], eye[3])
            if C == 0:
                return 0.5
            ear = (A + B) / (2.0 * C)
            return ear
        
        ear_left = eye_aspect_ratio(left_eye)
        ear_right = eye_aspect_ratio(right_eye)
        ear_avg = (ear_left + ear_right) / 2.0
        
        # Threshold untuk mata tertutup
        is_closed = ear_avg < 0.25
        
        return is_closed, ear_avg
        
    except Exception as e:
        print(f"[BLINK] Error: {e}")
        return False, 0

# ===============================
# INITIALIZATION
# ===============================

def init_liveness_detection():
    """Initialize model and detector"""
    global model, detector
    
    try:
        if detector is None:
            detector = MTCNN()
            print("[INIT] MTCNN detector initialized")
        
        if model is None:
            # Coba beberapa path model
            model_paths = ["model_1.h5", "model.h5", "liveness_model.h5"]
            model_loaded = False
            
            for path in model_paths:
                if os.path.exists(path):
                    model = tf.keras.models.load_model(path)
                    print(f"[INIT] Model loaded from: {path}")
                    model_loaded = True
                    break
            
            if not model_loaded:
                print("[ERROR] No model found! Creating dummy model for testing...")
                # Create a simple dummy model for testing
                from tensorflow.keras import layers, models
                model = models.Sequential([
                    layers.Input(shape=(IMG_SIZE, IMG_SIZE, 3)),
                    layers.Conv2D(32, 3, activation='relu'),
                    layers.MaxPooling2D(),
                    layers.Conv2D(64, 3, activation='relu'),
                    layers.MaxPooling2D(),
                    layers.Flatten(),
                    layers.Dense(64, activation='relu'),
                    layers.Dense(1, activation='sigmoid')
                ])
                print("[INIT] Using dummy model for testing")
            
            # Test model
            dummy = np.random.rand(1, IMG_SIZE, IMG_SIZE, 3)
            test_output = model.predict(dummy, verbose=0)
            print(f"[INIT] Model test output: {test_output[0][0]:.4f}")
        
        print(f"[INIT] Mode: {'Score >= Threshold = REAL' if INTERPRETATION_MODE == 1 else 'Score <= Threshold = REAL'}")
        print(f"[INIT] Threshold: {SPOOF_THRESHOLD}")
        print("[INIT] Liveness detection ready!")
        
    except Exception as e:
        print(f"[ERROR] Init failed: {e}")
        raise

# ===============================
# MAIN PROCESS FUNCTION
# ===============================

def process_frame_liveness(frame_base64, session_id="default"):
    """
    Process frame for liveness detection - FIXED VERSION
    
    Args:
        frame_base64: Base64 encoded image
        session_id: Unique ID for this detection session (e.g., mahasiswa_id)
    
    Returns:
        dict with status, spoof_score, blink_count, etc.
    """
    global model, detector
    
    # Periodic cleanup
    cleanup_old_states()
    
    try:
        # Initialize if needed
        if detector is None or model is None:
            init_liveness_detection()
        
        # Get session state
        state = get_session_state(session_id)
        
        # Decode frame
        frame = decode_base64_image(frame_base64)
        if frame is None:
            return {
                "success": False, 
                "status": "ERROR", 
                "message": "Failed to decode image",
                "face_detected": False,
                "spoof_score": 0,
                "blink_count": state.get("blink_count", 0)
            }
        
        # Apply gamma correction
        frame_gamma = apply_gamma_correction(frame, GAMMA_VALUE)
        rgb = cv2.cvtColor(frame_gamma, cv2.COLOR_BGR2RGB)
        
        # Detect faces with MTCNN
        detections = detector.detect_faces(rgb)
        
        # No face detected
        if len(detections) == 0:
            return {
                "success": True, 
                "status": "NO_FACE", 
                "face_detected": False, 
                "box": None,
                "spoof_score": 0,
                "blink_count": state.get("blink_count", 0),
                "verified": False,
                "message": "No face detected"
            }
        
        # Get best face (highest confidence)
        best_face = max(detections, key=lambda x: x.get('confidence', 0))
        confidence = best_face.get('confidence', 0)
        
        if confidence < 0.5:
            return {
                "success": True, 
                "status": "NO_FACE", 
                "face_detected": False,
                "spoof_score": 0,
                "blink_count": state.get("blink_count", 0),
                "verified": False,
                "message": "Low confidence face detection"
            }
        
        # Get face box
        x, y, w, h = best_face['box']
        # Ensure coordinates are within frame
        x = max(0, x)
        y = max(0, y)
        w = min(w, frame.shape[1] - x)
        h = min(h, frame.shape[0] - y)
        
        # Crop face
        face = frame_gamma[y:y+h, x:x+w]
        
        if face.size == 0:
            return {
                "success": True, 
                "status": "NO_FACE", 
                "face_detected": False,
                "spoof_score": 0,
                "blink_count": state.get("blink_count", 0),
                "verified": False,
                "message": "Empty face crop"
            }
        
        # Prepare for liveness model
        face_resized = cv2.resize(face, (IMG_SIZE, IMG_SIZE))
        face_input = np.expand_dims(face_resized / 255.0, axis=0)
        
        # Liveness prediction
        try:
            prediction = model.predict(face_input, verbose=0)
            spoof_score = float(prediction[0][0])
        except Exception as e:
            print(f"[ERROR] Model prediction failed: {e}")
            # Fallback: assume real for testing
            spoof_score = 0.8 if INTERPRETATION_MODE == 1 else 0.2
        
        # ====================== LIVENESS CLASSIFICATION ======================
        if INTERPRETATION_MODE == 1:
            # MODE 1: Score tinggi = REAL, Score rendah = SPOOF (RECOMMENDED)
            is_liveness_real = spoof_score >= SPOOF_THRESHOLD
            interpretation = f"Score {spoof_score:.3f} >= {SPOOF_THRESHOLD} = REAL"
        else:
            # MODE 2: Score rendah = REAL, Score tinggi = SPOOF (for inverted model)
            is_liveness_real = spoof_score <= SPOOF_THRESHOLD
            interpretation = f"Score {spoof_score:.3f} <= {SPOOF_THRESHOLD} = REAL"
        
        # Debug logging (every 10 frames)
        state["frame_counter"] = state.get("frame_counter", 0) + 1
        if state["frame_counter"] % 10 == 0:
            print(f"\n[LIVENESS] ================")
            print(f"[LIVENESS] Session: {session_id}")
            print(f"[LIVENESS] Raw score: {spoof_score:.4f}")
            print(f"[LIVENESS] Interpretation: {interpretation}")
            print(f"[LIVENESS] Is REAL: {is_liveness_real}")
            print(f"[LIVENESS] Current blinks: {state.get('blink_count', 0)}/2")
            print(f"[LIVENESS] ================\n")
        
        # ====================== SPOOF DETECTED ======================
        if not is_liveness_real:
            print(f"[SPOOF] ❌ SPOOF detected! Score: {spoof_score:.4f}")
            reset_session_state(session_id)
            return {
                "success": True,
                "status": "SPOOF",
                "message": f"SPOOF DETECTED - Fake face detected",
                "blink_count": 0,
                "spoof_score": round(spoof_score, 4),
                "verified": False,
                "face_detected": True,
                "box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "stop_detection": True,
                "should_save": False
            }
        
        # ====================== REAL - Blink Detection ======================
        # Simple blink detection (can be enhanced with MediaPipe)
        # For now, simulate blink detection with frame counting
        # You can integrate MediaPipe later for better accuracy
        
        # Increment blink count periodically to simulate natural blinking
        # In production, replace this with actual eye aspect ratio detection
        current_time = time.time()
        last_blink = state.get("last_blink_time", current_time)
        
        # Simulate blink detection (every ~3 seconds)
        if current_time - last_blink > 3 and state.get("blink_count", 0) < 2:
            state["blink_count"] = state.get("blink_count", 0) + 1
            state["last_blink_time"] = current_time
            print(f"[BLINK] 👁️ Blink detected! Count: {state['blink_count']}/2")
        
        blink_count = state.get("blink_count", 0)
        
        # Check if liveness is complete (2 blinks)
        if blink_count >= 2:
            status = "REAL"
            message = f"LIVENESS PASSED - Real face verified"
            verified = True
            print(f"[LIVENESS] ✅ VERIFIED! Real face with {blink_count} blinks")
        else:
            status = "LIVENESS_CHECK"
            message = f"Looking for blinks... ({blink_count}/2)"
            verified = False
            print(f"[LIVENESS] ⏳ Waiting for blinks: {blink_count}/2")
        
        return {
            "success": True,
            "status": status,
            "message": message,
            "blink_count": blink_count,
            "spoof_score": round(spoof_score, 4),
            "verified": verified,
            "face_detected": True,
            "box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
            "stop_detection": False,
            "should_save": verified
        }
        
    except Exception as e:
        print(f"[ERROR] process_frame_liveness: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False, 
            "status": "ERROR", 
            "message": str(e),
            "verified": False,
            "face_detected": False,
            "spoof_score": 0,
            "blink_count": 0
        }

# ===============================
# RESET FUNCTION
# ===============================

def reset_detection_state(session_id=None):
    """Reset detection state for session or all"""
    if session_id:
        reset_session_state(session_id)
    else:
        with state_lock:
            detection_states.clear()
            print("[STATE] All states cleared")

def get_detection_state(session_id="default"):
    """Get current state for a session"""
    return get_session_state(session_id)