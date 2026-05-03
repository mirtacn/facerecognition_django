import os
import cv2
import numpy as np
import base64
import pickle
from deepface import DeepFace
from django.conf import settings
from .models import FotoWajah, Mahasiswa

MODEL_NAME = "ArcFace"
THRESHOLD = 0.45  # STANDAR: 0.45 (jika terlalu ketat, naikkan ke 0.55 atau 0.60)
DETECTOR = "mtcnn"  # PAKAI MTCNN, LEBIH AKURAT DARI OPENCV

def get_face_embedding(foto_wajah, force_refresh=False):
    """
    Get embedding for a FotoWajah instance, using a local pickle cache.
    """
    cache_dir = os.path.join(settings.MEDIA_ROOT, 'embeddings_cache')
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    cache_path = os.path.join(cache_dir, f"emb_{foto_wajah.id}.pkl")
    
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"[RECOGNITION] Cache read error: {e}")
    
    try:
        img_path = foto_wajah.file_path.path
        
        if not os.path.exists(img_path):
            print(f"[RECOGNITION] File not found: {img_path}")
            return None
        
        objs = DeepFace.represent(
            img_path=img_path,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR,
            enforce_detection=False,
            align=True
        )
        
        if objs and len(objs) > 0:
            embedding = objs[0]["embedding"]
            with open(cache_path, 'wb') as f:
                pickle.dump(embedding, f)
            return embedding
        else:
            print(f"[RECOGNITION] No face detected in photo {foto_wajah.id}")
            
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
    
    # Normalize vectors
    a = a / (np.linalg.norm(a) + 1e-8)
    b = b / (np.linalg.norm(b) + 1e-8)
    
    similarity = np.dot(a, b)
    distance = 1 - similarity
    
    return distance

def verify_face_with_insightface(frame_base64, mahasiswa_id, face_box=None):
    """
    Verifikasi wajah menggunakan model ArcFace
    """
    print(f"\n[RECOGNITION] ========== START ==========")
    print(f"[RECOGNITION] Mahasiswa ID: {mahasiswa_id}")
    print(f"[RECOGNITION] Threshold: {THRESHOLD}")
    
    try:
        # 1. Get student from DB
        mahasiswa = Mahasiswa.objects.get(id=mahasiswa_id)
        print(f"[RECOGNITION] Mahasiswa: {mahasiswa.user.nama_lengkap}")
        
        # 2. Get ALL reference photos
        reference_photos = FotoWajah.objects.filter(mahasiswa=mahasiswa).order_by('-created_at')
        
        if not reference_photos.exists():
            return {"verified": False, "message": "No reference photos found"}
        
        print(f"[RECOGNITION] Reference photos: {reference_photos.count()}")
        
        # 3. Decode frame
        if ',' in frame_base64:
            frame_base64 = frame_base64.split(',')[1]
        
        img_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"verified": False, "message": "Failed to decode frame"}
        
        # 4. Crop face if box provided
        recognition_frame = frame
        
        if face_box and all(k in face_box for k in ('x', 'y', 'w', 'h')):
            try:
                x, y, w, h = face_box['x'], face_box['y'], face_box['w'], face_box['h']
                
                # Margin 20%
                margin_w = int(w * 0.2)
                margin_h = int(h * 0.2)
                
                x1 = max(0, x - margin_w)
                y1 = max(0, y - margin_h)
                x2 = min(frame.shape[1], x + w + margin_w)
                y2 = min(frame.shape[0], y + h + margin_h)
                
                recognition_frame = frame[y1:y2, x1:x2]
                
                if recognition_frame.size == 0:
                    recognition_frame = frame
                    
            except Exception as e:
                print(f"[RECOGNITION] Crop error: {e}")
                recognition_frame = frame
        
        # 5. Extract embedding from frame
        try:
            # Try with MTCNN first (more accurate)
            frame_objs = DeepFace.represent(
                img_path=recognition_frame,
                model_name=MODEL_NAME,
                detector_backend='mtcnn',
                enforce_detection=False,
                align=True
            )
            
            # If MTCNN fails, try opencv
            if not frame_objs or len(frame_objs) == 0:
                print(f"[RECOGNITION] MTCNN no face, trying opencv...")
                frame_objs = DeepFace.represent(
                    img_path=recognition_frame,
                    model_name=MODEL_NAME,
                    detector_backend='opencv',
                    enforce_detection=False,
                    align=True
                )
            
            # If still fails, try with original frame (no crop)
            if not frame_objs or len(frame_objs) == 0:
                print(f"[RECOGNITION] Still no face, trying original frame...")
                frame_objs = DeepFace.represent(
                    img_path=frame,
                    model_name=MODEL_NAME,
                    detector_backend='mtcnn',
                    enforce_detection=False,
                    align=True
                )
            
            if not frame_objs or len(frame_objs) == 0:
                return {"verified": False, "message": "No face detected in frame"}
            
            frame_embedding = frame_objs[0]["embedding"]
            print(f"[RECOGNITION] Frame embedding extracted (dim: {len(frame_embedding)})")
            
        except Exception as e:
            print(f"[RECOGNITION] Frame extraction error: {e}")
            return {"verified": False, "message": f"Face extraction failed"}
        
        # 6. Compare with reference photos
        best_distance = 2.0
        best_ref_id = None
        
        for ref in reference_photos:
            ref_embedding = get_face_embedding(ref)
            
            if ref_embedding is None:
                continue
            
            distance = calculate_cosine_distance(frame_embedding, ref_embedding)
            similarity = 1 - distance
            
            print(f"[RECOGNITION] Ref {ref.id}: distance={distance:.4f}, similarity={similarity:.4f}")
            
            if distance < best_distance:
                best_distance = distance
                best_ref_id = ref.id
            
            if distance < THRESHOLD:
                print(f"[RECOGNITION] ✅ MATCH! distance={distance:.4f} < {THRESHOLD}")
                return {
                    "verified": True,
                    "distance": float(distance),
                    "similarity": float(1 - distance),
                    "message": f"Face verified ({(1-distance)*100:.1f}%)"
                }
        
        print(f"[RECOGNITION] Best distance: {best_distance:.4f}")
        
        if best_distance < THRESHOLD:
            return {
                "verified": True,
                "distance": float(best_distance),
                "similarity": float(1 - best_distance),
                "message": f"Face verified ({(1-best_distance)*100:.1f}%)"
            }
        else:
            return {
                "verified": False,
                "distance": float(best_distance),
                "similarity": float(1 - best_distance),
                "message": f"Identity not matched (best: {(1-best_distance)*100:.1f}%)"
            }
        
    except Mahasiswa.DoesNotExist:
        return {"verified": False, "message": "Student not found"}
    except Exception as e:
        print(f"[RECOGNITION] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"verified": False, "message": f"Error: {str(e)}"}