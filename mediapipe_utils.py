import cv2
import numpy as np
import math
import time

# GLOBAL STATE untuk blink detection
_blink_state = {
    "blink_count": 0,
    "eye_closed": False,
    "eye_closed_frames": 0,
    "last_blink_time": time.time(),
    "frame_counter": 0
}

def _distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def detect_blink_mediapipe(frame, face_landmarks, threshold=0.20):
    """
    Mendeteksi kedipan mata menggunakan MediaPipe Face Mesh
    """
    if face_landmarks is None:
        return False, 0.0, 0.0
    
    # Landmark indices untuk kedua mata
    # Left eye: 33, 160, 158, 133, 153, 144
    # Right eye: 362, 385, 387, 263, 373, 380
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    
    try:
        # Ekstrak koordinat landmark mata
        h, w = frame.shape[:2]
        
        left_eye_coords = []
        for i in LEFT_EYE:
            lm = face_landmarks.landmark[i]
            left_eye_coords.append([lm.x * w, lm.y * h])
        
        right_eye_coords = []
        for i in RIGHT_EYE:
            lm = face_landmarks.landmark[i]
            right_eye_coords.append([lm.x * w, lm.y * h])
        
        def eye_aspect_ratio(eye_coords):
            # Vertical distances (index 1-5, 2-4)
            vertical_1 = _distance(eye_coords[1], eye_coords[5])
            vertical_2 = _distance(eye_coords[2], eye_coords[4])
            # Horizontal distance (index 0-3)
            horizontal = _distance(eye_coords[0], eye_coords[3])
            
            if horizontal == 0:
                return 0.5
            ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
            return ear
        
        ear_left = eye_aspect_ratio(left_eye_coords)
        ear_right = eye_aspect_ratio(right_eye_coords)
        ear_avg = (ear_left + ear_right) / 2.0
        
        is_closed = ear_avg < threshold
        return is_closed, ear_left, ear_right
        
    except Exception as e:
        print(f"Error in blink detection: {e}")
        return False, 0.0, 0.0

def process_liveness(frame, frame_shape, state, min_blinks_required=2):
    """
    Process liveness detection using MediaPipe Face Mesh
    """
    global _blink_state
    
    try:
        # Gunakan state yang diberikan (dari liveness_detection.py)
        # atau global state sebagai fallback
        if state is None:
            state = _blink_state
        
        # Inisialisasi state jika belum ada
        if 'blink_count' not in state:
            state['blink_count'] = 0
        if 'eye_closed' not in state:
            state['eye_closed'] = False
        if 'eye_closed_frames' not in state:
            state['eye_closed_frames'] = 0
        if 'last_blink_time' not in state:
            state['last_blink_time'] = time.time()
        
        # Import MediaPipe
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh
        
        # Buat FaceMesh detector (cache di state)
        if 'face_detector' not in state:
            state['face_detector'] = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Deteksi face mesh
        results = state['face_detector'].process(rgb_frame)
        
        if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
            face_landmarks = results.multi_face_landmarks[0]
            
            # Deteksi apakah mata tertutup
            is_eyes_closed, ear_left, ear_right = detect_blink_mediapipe(
                frame, face_landmarks, threshold=0.20
            )
            
            # LOG untuk debugging
            state['frame_counter'] = state.get('frame_counter', 0) + 1
            if state['frame_counter'] % 10 == 0:  # Log setiap 10 frame
                print(f"[BLINK] EAR: L={ear_left:.3f}, R={ear_right:.3f} | "
                      f"Closed={is_eyes_closed} | Blink count={state['blink_count']}")
            
            # Deteksi kedipan
            if is_eyes_closed:
                # Mata tertutup
                state['eye_closed_frames'] += 1
                if not state['eye_closed']:
                    state['eye_closed'] = True
                    print(f"[BLINK] 👁️ Eyes closing... frames={state['eye_closed_frames']}")
            else:
                # Mata terbuka
                if state['eye_closed'] and state['eye_closed_frames'] >= 2:
                    # Kedipan terdeteksi (mata tertutup minimal 2 frame lalu terbuka)
                    state['blink_count'] += 1
                    state['last_blink_time'] = time.time()
                    print(f"[BLINK] ✅ BLINK DETECTED! Total: {state['blink_count']}/2")
                
                state['eye_closed'] = False
                state['eye_closed_frames'] = 0
        
        # Update verified status
        if state['blink_count'] >= min_blinks_required:
            state['verified'] = True
        
        return state
        
    except Exception as e:
        print(f"Error in process_liveness: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return state

def reset_blink_state():
    """Reset global blink state"""
    global _blink_state
    _blink_state = {
        "blink_count": 0,
        "eye_closed": False,
        "eye_closed_frames": 0,
        "last_blink_time": time.time(),
        "frame_counter": 0
    }
    print("[BLINK] State reset")