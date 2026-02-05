import cv2
import numpy as np
import tensorflow as tf
from mtcnn import MTCNN
import time
import sys

# Force reload module
if 'mediapipe_utils' in sys.modules:
    del sys.modules['mediapipe_utils']

from mediapipe_utils import process_liveness

IMG_SIZE = 128
SPOOF_THRESHOLD = 0.7  
model = tf.keras.models.load_model("model_antispoof_128x128_final.h5")
detector = MTCNN()

state = {
    "blink_count": 0,
    "eye_closed": False,
    "eye_closed_count": 0,
    "head_stage": "CENTER",
    "verified": False,
    "last_blink_time": time.time(),
}

previous_face_box = None
cap = cv2.VideoCapture(0)

print("--- LIVENESS SYSTEM START ---")
print("Instruksi: Silakan berkedip 2 kali untuk verifikasi.")

while True:
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.flip(frame, 1)  # 1 = flip horizontal (mirror)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    detections = detector.detect_faces(rgb)
    
    if len(detections) == 0:
        # Reset state jika wajah hilang
        state["blink_count"] = 0
        state["verified"] = False
        previous_face_box = None
        cv2.putText(frame, "NO FACE DETECTED", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    else:
        for det in detections:
            if det["confidence"] < 0.9: continue

            x, y, w, h = det["box"]
            x, y = max(0, x), max(0, y)
            
            # Reset jika orang berganti
            current_face_box = (x, y, w, h)
            if previous_face_box is not None:
                px, py, pw, ph = previous_face_box
                distance = np.sqrt((x - px)**2 + (y - py)**2)
                if distance > 80:
                    state["blink_count"] = 0
                    state["verified"] = False
            previous_face_box = current_face_box

            # 1. CEK SPOOF DARI MODEL CNN
            face = frame[y:y+h, x:x+w]
            if face.size == 0: continue
            face_input = cv2.resize(face, (IMG_SIZE, IMG_SIZE)) / 255.0
            face_input = np.expand_dims(face_input, axis=0)
            spoof_score = model.predict(face_input, verbose=0)[0][0]
            print(f"Debug: Spoof Score = {spoof_score:.2f}")
            # 2. PROSES KEDIPAN (LIVENESS)
            state = process_liveness(frame, frame.shape, state)

            # --- LOGIKA STATUS ---
            # Default Warna & Pesan
            color = (0, 255, 255) # Kuning (Verifying)
            status_text = "VERIFYING..."
            sub_text = f"Blinks: {state['blink_count']}/2"

            # Syarat 1: Jika Score CNN sangat rendah, langsung anggap SPOOF
            if spoof_score < SPOOF_THRESHOLD:
                color = (0, 0, 255) # Merah
                status_text = "SPOOF DETECTED"
                sub_text = "Fake Face Pattern"
            
            # Syarat 2: Jika sudah berkedip 2x dan score CNN aman
            elif state['blink_count'] >= 2:
                color = (0, 255, 0) # Hijau
                status_text = "REAL / LIVE"
                sub_text = "Liveness Verified"
                state["verified"] = True

            # Gambar UI ke Frame
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 3)
            cv2.putText(frame, status_text, (x, y-15), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
            cv2.putText(frame, sub_text, (x, y+h+30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.imshow("LIVENESS SYSTEM", frame)
    if cv2.waitKey(1) & 0xFF == 27: break

cap.release()
cv2.destroyAllWindows()