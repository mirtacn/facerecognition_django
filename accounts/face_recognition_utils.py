
import os
import cv2
import numpy as np
import base64
import pickle
from deepface import DeepFace
from django.conf import settings
from .models import FotoWajah, Mahasiswa


MODEL_NAME = "ArcFace"
THRESHOLD = 0.6 
DETECTOR = "opencv"

def get_face_embedding(foto_wajah):
    """
    Get embedding for a FotoWajah instance, using a local pickle cache.
    """
    cache_dir = os.path.join(settings.MEDIA_ROOT, 'embeddings_cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    cache_path = os.path.join(cache_dir, f"emb_{foto_wajah.id}.pkl")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[RECOGNITION] Cache read error: {e}")
            
    try:
        img_path = foto_wajah.file_path.path
        objs = DeepFace.represent(
            img_path = img_path,
            model_name = MODEL_NAME,
            detector_backend = DETECTOR,
            enforce_detection = False,
            align = True
        )
        
        if objs:
            embedding = objs[0]["embedding"]
            with open(cache_path, 'wb') as f:
                pickle.dump(embedding, f)
            return embedding
            
    except Exception as e:
        print(f"[RECOGNITION] Embedding extraction failed for photo {foto_wajah.id}: {e}")
        
    return None

def calculate_cosine_distance(source_representation, test_representation):
    """
    Calculate cosine distance between two representations.
    Cosine Distance = 1 - Cosine Similarity
    """
    a = np.array(source_representation)
    b = np.array(test_representation)
    
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return 1 - similarity

def verify_face_with_insightface(frame_base64, mahasiswa_id, face_box=None):
    """
    Verifikasi wajah menggunakan model ArcFace dengan optimasi:
    1. Cropping wajah berdasarkan box dari liveness (Skip detection).
    2. Extract embedding frame HANYA SEKALI.
    3. Gunakan cache untuk embedding foto referensi.
    """
    try:
        # 1. Get the student from DB
        mahasiswa = Mahasiswa.objects.get(id=mahasiswa_id)
        
        # 2. Get registered face photos (take 5)
        reference_photos = FotoWajah.objects.filter(mahasiswa=mahasiswa).order_by('-created_at')[:5]
        
        if not reference_photos.exists():
            return {
                "verified": False,
                "message": "No reference photos found."
            }
            
        # 3. Decode frame base64
        if ',' in frame_base64:
            frame_base64 = frame_base64.split(',')[1]
        
        img_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"verified": False, "message": "Failed to decode frame"}

        # --- OPTIMASI: CROP WAJAH ---
        # Jika ada box dari liveness, crop dulu supaya DeepFace tidak perlu deteksi lagi
        recognition_frame = frame
        if face_box and all(k in face_box for k in ('x', 'y', 'w', 'h')):
            try:
                x, y, w, h = face_box['x'], face_box['y'], face_box['w'], face_box['h']
                # Tambahkan margin sedikit (10%)
                margin_w = int(w * 0.1)
                margin_h = int(h * 0.1)
                
                x1 = max(0, x - margin_w)
                y1 = max(0, y - margin_h)
                x2 = min(frame.shape[1], x + w + margin_w)
                y2 = min(frame.shape[0], y + h + margin_h)
                
                recognition_frame = frame[y1:y2, x1:x2]
                if recognition_frame.size == 0:
                    recognition_frame = frame # Fallback
            except:
                recognition_frame = frame
        # ----------------------------

        # 4. Extract embedding from current frame (ONCE)
        try:
            # Jika sudah di-crop, kita bisa skip detection dg enforce_detection=False
            # 'opencv' detector di sini hanya formalitas jika enforce_detection=False
            frame_objs = DeepFace.represent(
                img_path = recognition_frame,
                model_name = MODEL_NAME,
                detector_backend = 'opencv',
                enforce_detection = False, 
                align = True
            )
            
            if not frame_objs:
                return {"verified": False, "message": "No face found in frame"}
                
            frame_embedding = frame_objs[0]["embedding"]
            
        except Exception as e:
            print(f"[RECOGNITION ERR] Frame extraction: {e}")
            return {"verified": False, "message": "Face extraction failed"}

        # 5. Compare against reference embeddings
        best_distance = 1.0
        is_verified = False
        
        for ref in reference_photos:
            ref_embedding = get_face_embedding(ref)
            
            if ref_embedding is None:
                continue
                
            distance = calculate_cosine_distance(frame_embedding, ref_embedding)
            
            if distance < best_distance:
                best_distance = distance
            
            if distance < THRESHOLD:
                is_verified = True
                break
                    
        if is_verified:
            return {
                "verified": True,
                "distance": float(best_distance),
                "message": f"Face verified (Score: {1-best_distance:.2f})"
            }
        else:
            return {
                "verified": False,
                "distance": float(best_distance),
                "message": "Identity not matched."
            }

    except Mahasiswa.DoesNotExist:
        return {"verified": False, "message": "Student not found"}
    except Exception as e:
        print(f"[RECOGNITION ERROR] {e}")
        return {"verified": False, "message": f"Error: {str(e)}"}
