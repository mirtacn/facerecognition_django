import cv2
import numpy as np
import math
import time
import os

def _distance(p1, p2):
    """Calculate Euclidean distance between two points"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def detect_eyes_simple(frame, face_box):
    """
    Deteksi mata sederhana menggunakan Haar Cascade
    Mengembalikan True jika mata terdeteksi (terbuka), False jika tidak (tertutup)
    """
    try:
        x, y, w, h = face_box
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Load eye cascade
        eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        )
        
        if eye_cascade.empty():
            print("Eye cascade not loaded!")
            return True
        
        # Crop region mata (bagian atas wajah)
        roi_gray = gray[y:y+int(h*0.5), x:x+w]
        if roi_gray.size == 0:
            return True
        
        # Deteksi mata
        eyes = eye_cascade.detectMultiScale(
            roi_gray,
            scaleFactor=1.1,
            minNeighbors=3,
            minSize=(20, 20)
        )
        
        # Jika terdeteksi 2 mata, dianggap terbuka
        # Jika terdeteksi 1 atau 0 mata, dianggap tertutup
        num_eyes = len(eyes)
        print(f"      Detected {num_eyes} eye(s)")
        
        return num_eyes >= 2
        
    except Exception as e:
        print(f"Error in eye detection: {e}")
        return True

def detect_eyes_brightness(frame, face_box):
    """
    Deteksi mata menggunakan cascade dengan fallback brightness
    Metode yang lebih reliable
    """
    try:
        x, y, w, h = face_box
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Coba berbagai path untuk haarcascade_eye
        cascade_paths = [
            'haarcascade_eye.xml',
            './haarcascade_eye.xml',
            'C:\laragon\www\facerecognition_django\haarcascade_eye.xml',
            'C:\\laragon\\www\\facerecognition_django\\haarcascade_eye.xml',
            os.path.join(os.path.dirname(__file__), 'haarcascade_eye.xml'),
            cv2.data.haarcascades + 'haarcascade_eye.xml'
        ]
        
        eye_cascade = None
        for cascade_path in cascade_paths:
            if os.path.exists(cascade_path) or 'haarcascade' in cascade_path:
                eye_cascade = cv2.CascadeClassifier(cascade_path)
                if not eye_cascade.empty():
                    print(f"      ✓ Loaded cascade from: {cascade_path}")
                    break
        
        if eye_cascade is None or eye_cascade.empty():
            print("      ✗ Cascade file not found, using brightness method only")
            eye_cascade = None
        
        if eye_cascade is not None:
            # Crop region mata (bagian atas wajah)
            roi_gray = gray[max(0, y):max(0, y)+int(h*0.5), max(0, x):max(0, x)+w]
            
            if roi_gray.size > 0:
                # Deteksi mata
                eyes = eye_cascade.detectMultiScale(
                    roi_gray,
                    scaleFactor=1.05,
                    minNeighbors=5,
                    minSize=(20, 20)
                )
                
                # Mata terbuka jika deteksi >= 1 mata
                is_open = len(eyes) >= 1
                print(f"      Eyes detected: {len(eyes)} | Eyes open: {is_open}")
                return is_open
        
        # Fallback ke brightness jika cascade gagal
        eye_region_y_start = max(0, y + int(h * 0.25))
        eye_region_y_end = max(0, y + int(h * 0.45))
        eye_region_x_start = max(0, x)
        eye_region_x_end = max(0, x + w)
        
        eye_region = frame[eye_region_y_start:eye_region_y_end, 
                          eye_region_x_start:eye_region_x_end]
        
        if eye_region.size == 0:
            return True
        
        # Convert to grayscale
        gray_eye = cv2.cvtColor(eye_region, cv2.COLOR_BGR2GRAY)
        
        # Hitung variasi brightness
        std_brightness = np.std(gray_eye)
        
        # Threshold lebih rendah untuk deteksi yang lebih sensitif
        threshold = 20.0
        is_open = std_brightness > threshold
        
        print(f"      Brightness variance: {std_brightness:.1f} | Eyes open: {is_open}")
        
        return is_open
        
    except Exception as e:
        print(f"Error in brightness detection: {e}")
        return True

def process_liveness(frame, frame_shape, state, blink_threshold=0.22, timeout_seconds=3.0):
    """
    Process face liveness detection using improved eye detection
    """
    
    try:
        # Initialize timestamp if not exists
        if 'last_blink_time' not in state:
            state['last_blink_time'] = time.time()
        if 'is_timeout' not in state:
            state['is_timeout'] = False
        if 'eye_closed_count' not in state:
            state['eye_closed_count'] = 0
        
        # Deteksi wajah dengan Haar Cascade untuk mendapatkan posisi mata
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100)
        )
        
        if len(faces) > 0:
            # Ambil wajah pertama
            x, y, w, h = faces[0]
            
            # Gunakan metode cascade + brightness untuk deteksi mata
            eyes_open = detect_eyes_brightness(frame, (x, y, w, h))
            
            current_time = time.time()
            
            # Improved blink detection logic
            if not eyes_open:  # Eyes closing/closed
                state["eye_closed_count"] += 1
                if state["eye_closed_count"] == 1:  # First frame of closure
                    state["eye_closed"] = True
                    print(f"  ↓ Eyes closing... (count: {state['eye_closed_count']})")
            else:  # Eyes opening/open
                if state["eye_closed"] and state["eye_closed_count"] > 2:  # Blink confirmed (sustained closure)
                    state["blink_count"] += 1
                    state['last_blink_time'] = current_time
                    state["eye_closed"] = False
                    state["eye_closed_count"] = 0
                    print(f"  ✓ Blink detected! Total: {state['blink_count']}")
                elif state["eye_closed_count"] > 0 and not state["eye_closed"]:
                    # Reset if it was just a glitch
                    state["eye_closed_count"] = 0
        
        else:
            # No face detected
            print("      No face detected")
            eyes_open = True  # Default to open
        
        # Verification: require at least 2 blinks (NO TIMEOUT)
        if state["blink_count"] >= 2:
            state["verified"] = True
            state['is_timeout'] = False
        else:
            state["verified"] = False
            
        return state
        
    except Exception as e:
        print(f"Error in process_liveness: {type(e).__name__}: {e}")

# ===== MEDIAPIPE BLINK DETECTION =====

def detect_blink_mediapipe(frame, face_landmarks, threshold=0.15):
    """
    Mendeteksi kedipan mata menggunakan MediaPipe Face Mesh
    Menghitung Eye Aspect Ratio (EAR) untuk mendeteksi kedipan
    
    Args:
        frame: input frame
        face_landmarks: MediaPipe face landmarks
        threshold: threshold EAR untuk deteksi mata tertutup
    
    Returns:
        is_blink: boolean, True jika sedang berkedip
        ear_left: Eye Aspect Ratio mata kiri
        ear_right: Eye Aspect Ratio mata kanan
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
        left_eye_coords = np.array([[lm.x, lm.y] for lm in [face_landmarks.landmark[i] for i in LEFT_EYE]])
        right_eye_coords = np.array([[lm.x, lm.y] for lm in [face_landmarks.landmark[i] for i in RIGHT_EYE]])
        
        # Hitung Eye Aspect Ratio
        def eye_aspect_ratio(eye_coords):
            # Vertical distances
            vertical_1 = _distance(eye_coords[1], eye_coords[5])
            vertical_2 = _distance(eye_coords[2], eye_coords[4])
            
            # Horizontal distance
            horizontal = _distance(eye_coords[0], eye_coords[3])
            
            # Calculate EAR
            ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
            return ear
        
        ear_left = eye_aspect_ratio(left_eye_coords)
        ear_right = eye_aspect_ratio(right_eye_coords)
        
        # Average EAR
        ear_avg = (ear_left + ear_right) / 2.0
        
        # Deteksi kedipan jika EAR rendah
        is_blink = ear_avg < threshold
        
        return is_blink, ear_left, ear_right
        
    except Exception as e:
        print(f"Error in blink detection: {e}")
        return False, 0.0, 0.0

def process_liveness_mediapipe(frame, state, min_blinks_required=2):
    """
    Process liveness detection using MediaPipe Face Mesh
    Mendeteksi mata berkedip minimal 2x untuk verifikasi liveness
    
    Args:
        frame: input frame
        state: state dictionary
        min_blinks_required: jumlah kedipan minimal yang dibutuhkan
    
    Returns:
        state: updated state dictionary
    """
    
    try:
        # Import MediaPipe di dalam fungsi
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh
        
        # Initialize detector jika belum ada
        if 'face_detector' not in state:
            state['face_detector'] = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            )
        
        if 'blink_count' not in state:
            state['blink_count'] = 0
        
        if 'eye_closed' not in state:
            state['eye_closed'] = False
        
        if 'eye_closed_frames' not in state:
            state['eye_closed_frames'] = 0
        
        if 'verified' not in state:
            state['verified'] = False
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Deteksi face mesh
        results = state['face_detector'].process(rgb_frame)
        
        if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
            face_landmarks = results.multi_face_landmarks[0]
            
            # Deteksi blink menggunakan EAR
            is_eyes_closed, ear_left, ear_right = detect_blink_mediapipe(frame, face_landmarks, threshold=0.15)
            
            # Update state berdasarkan deteksi mata
            if is_eyes_closed:
                state['eye_closed_frames'] += 1
                if not state['eye_closed']:
                    state['eye_closed'] = True
            else:
                # Mata membuka setelah ditutup
                if state['eye_closed'] and state['eye_closed_frames'] >= 3:
                    # Dianggap sebagai satu kedipan jika mata tertutup >= 3 frames
                    state['blink_count'] += 1
                    print(f"✓ Blink detected! Total: {state['blink_count']}/{min_blinks_required}")
                
                state['eye_closed'] = False
                state['eye_closed_frames'] = 0
            
            # Cek apakah sudah cukup kedipan
            if state['blink_count'] >= min_blinks_required:
                state['verified'] = True
        
        return state
        
    except Exception as e:
        print(f"Error in process_liveness_mediapipe: {type(e).__name__}: {e}")
        return state

def get_mediapipe_landmarks(frame, state):
    """
    Get MediaPipe face landmarks untuk visualisasi
    """
    
    try:
        # Import MediaPipe di dalam fungsi
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh
        
        if 'face_detector' not in state:
            state['face_detector'] = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            )
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = state['face_detector'].process(rgb_frame)
        
        return results
        
    except Exception as e:
        print(f"Error in get_mediapipe_landmarks: {e}")
        return None
        return state