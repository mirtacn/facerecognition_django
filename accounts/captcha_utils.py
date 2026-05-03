# accounts/captcha_utils.py
import random
import string
import io
import base64
from datetime import datetime
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL (Pillow) not installed. Install with: pip install Pillow")

def generate_captcha_text(length=6):
    """Generate random alphanumeric CAPTCHA text"""
    characters = string.ascii_uppercase + string.digits
    # Hapus karakter yang mudah membingungkan (0, O, I, 1, etc)
    characters = characters.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    captcha_text = ''.join(random.choices(characters, k=length))
    return captcha_text

def create_captcha_image(captcha_text):
    """Generate CAPTCHA image as base64"""
    if not PIL_AVAILABLE:
        # Fallback: return text as image (simplified)
        return None
    
    # Ukuran gambar
    width = 200
    height = 70
    
    # Buat gambar dengan background putih
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Load font (gunakan font default PIL)
    try:
        # Coba gunakan font yang lebih bagus jika ada
        import sys
        if sys.platform == 'win32':
            font_path = "C:/Windows/Fonts/Arial.ttf"
        else:
            font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        font = ImageFont.truetype(font_path, 36)
    except:
        # Fallback ke font default
        font = ImageFont.load_default()
    
    # Hitung posisi teks (center)
    try:
        bbox = draw.textbbox((0, 0), captcha_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # For older PIL versions
        text_width, text_height = draw.textsize(captcha_text, font=font)
    
    x = (width - text_width) / 2
    y = (height - text_height) / 2
    
    # Gambar teks dengan warna random
    colors = ['#1a1a1a', '#2d2d2d', '#3d3d3d', '#4a4a4a']
    draw.text((x, y), captcha_text, font=font, fill=random.choice(colors))
    
    # Tambahkan noise (titik-titik random)
    for _ in range(500):
        x_noise = random.randint(0, width)
        y_noise = random.randint(0, height)
        draw.point((x_noise, y_noise), fill=random.choice(colors))
    
    # Tambahkan garis-garis random
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=random.choice(colors), width=2)
    
    # Konversi ke base64
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/png;base64,{image_base64}"

def get_or_create_captcha(session_key, force_refresh=False):
    """Get or create CAPTCHA for current session"""
    if not session_key:
        return {'text': 'ABCD12', 'image': None}
    
    cache_key = f'captcha_{session_key}'
    
    # If force_refresh is True, delete existing cache
    if force_refresh:
        cache.delete(cache_key)
    
    captcha_data = cache.get(cache_key)
    
    if not captcha_data:
        captcha_text = generate_captcha_text()
        captcha_image = create_captcha_image(captcha_text)
        captcha_data = {
            'text': captcha_text,
            'image': captcha_image,
            'created_at': datetime.now()
        }
        # Simpan di cache selama 5 menit
        cache.set(cache_key, captcha_data, 300)
    
    return captcha_data

def verify_captcha(session_key, user_input):
    """Verify CAPTCHA input - TIDAK menghapus cache"""
    if not session_key:
        return False
    
    cache_key = f'captcha_{session_key}'
    captcha_data = cache.get(cache_key)
    
    if not captcha_data:
        return False
    
    # Bandingkan (case insensitive)
    is_valid = captcha_data['text'].lower() == user_input.lower()
    
    # JANGAN HAPUS CACHE DI SINI!
    # Cache akan dihapus hanya saat login berhasil di login_view
    return is_valid

@csrf_exempt
@require_http_methods(["GET"])
def refresh_captcha(request):
    """Refresh CAPTCHA (AJAX endpoint)"""
    if not request.session.session_key:
        request.session.create()
    
    session_key = request.session.session_key
    
    try:
        cache_key = f'captcha_{session_key}'
        # Hapus cache lama
        cache.delete(cache_key)
        
        # Buat CAPTCHA baru dengan force_refresh=True
        captcha_data = get_or_create_captcha(session_key, force_refresh=True)
        
        return JsonResponse({
            'success': True,
            'captcha_image': captcha_data['image']
        })
    except Exception as e:
        print(f"Error refreshing CAPTCHA: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })