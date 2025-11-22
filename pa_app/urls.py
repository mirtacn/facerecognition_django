# pa_app/urls.py

"""
URL configuration for pa_app project.
# ... (komentar)
"""
from django.contrib import admin
from django.urls import path
# --- Tambahkan import redirect di sini ---
from django.shortcuts import redirect 
from accounts.views import (login_view, register_wizard, admin_dashboard, mahasiswa_dashboard)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    # Menggunakan <int:step> untuk menangani 1, 2, 3
    path('register/step/<int:step>/', register_wizard, name='register_step'), 
    
    # Redirect register biasa ke step 1
    # Fungsi redirect sekarang dikenali
    path('register/', lambda request: redirect('register_step', step=1), name='register'), 

    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('mahasiswa-dashboard/', mahasiswa_dashboard, name='mahasiswa_dashboard'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)