# pa_app/urls.py

"""
URL configuration for pa_app project.
# ... (komentar)
"""
from django.contrib import admin
from django.urls import path
# --- Tambahkan import redirect di sini ---
from django.shortcuts import redirect 
from accounts.views import (login_view, register_wizard, admin_dashboard, profil_mahasiswa, data_wajah, riwayat_presensi, progress_sks, edit_profil)
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import logout_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', login_view, name='login'),
    # Menggunakan <int:step> untuk menangani 1, 2, 3
    path('register/step/<int:step>/', register_wizard, name='register_step'), 

    # Redirect register biasa ke step 1
    # Fungsi redirect sekarang dikenali
    path('register/', lambda request: redirect('register_step', step=1), name='register'), 

    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('profil_mahasiswa/', profil_mahasiswa, name='profil_mahasiswa'),
    path('edit_profil/<str:nim>/', edit_profil, name='edit_profil'),
    path('data_wajah/', data_wajah, name='data_wajah'),
    path('riwayat_presensi/', riwayat_presensi, name='riwayat_presensi'),
    path('progress_sks/', progress_sks, name='progress_sks'),
    path('logout/', logout_view, name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)