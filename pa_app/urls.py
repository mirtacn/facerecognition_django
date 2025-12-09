# pa_app/urls.py

"""
URL configuration for pa_app project.
# ... (komentar)
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect 
from accounts.views import (login_view, checkin_presensi, get_presensi_today, checkout_presensi, register_wizard, edit_mahasiswa, hapus_mahasiswa, kamera_presensi_mhs, admin_dashboard, pengaturan_sistem, status_pemenuhan, rekap_presensi, monitoring_presensi, data_sks, management_data, approval_pendaftaran, master_data_wajah, data_mahasiswa, monitor_durasi, profil_mahasiswa, data_wajah, riwayat_presensi, progress_sks, edit_profil, get_kegiatan_pa_by_jenjang, registrasi_complete, edit_dosen_pembimbing, upload_foto_wajah, hapus_foto_wajah, hapus_semua_foto)
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import logout_view

urlpatterns = [
    # --- URL UNTUK ADMIN APLIKASI (Harus DITEMPATKAN SEBELUM admin.site.urls) ---
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/kamera_presensi_mhs/', kamera_presensi_mhs, name='kamera_presensi_mhs'),
    path('admin/monitor-durasi/', monitor_durasi, name='monitor_durasi'),
    path('admin/management-data/', management_data, name='management_data'),
    path('admin/approval-pendaftaran/', approval_pendaftaran, name='approval_pendaftaran'),
    path('admin/data-mahasiswa/', data_mahasiswa, name='data_mahasiswa'),
    path('admin/edit-mahasiswa/<int:mahasiswa_id>/', edit_mahasiswa, name='edit_mahasiswa'),
    path('admin/hapus-mahasiswa/<int:mahasiswa_id>/', hapus_mahasiswa, name='hapus_mahasiswa'),
    path('admin/master-data-wajah/', master_data_wajah, name='master_data_wajah'),
    path('admin/data-sks/', data_sks, name='data_sks'),
    path('admin/monitoring-presensi/', monitoring_presensi, name='monitoring_presensi'),
    path('api/checkin/', checkin_presensi, name='checkin_presensi'),
    path('api/checkout/', checkout_presensi, name='checkout_presensi'),
    path('api/presensi-today/', get_presensi_today, name='get_presensi_today'),
    path('admin/rekap-presensi/', rekap_presensi, name='rekap_presensi'),
    path('admin/status-pemenuhan/', status_pemenuhan, name='status_pemenuhan'),
    path('admin/pengaturan-sistem/', pengaturan_sistem, name='pengaturan_sistem'),
    
    # --- DJANGO ADMIN (Harus DITEMPATKAN DIBAWAH URL ADMIN APLIKASI) ---
    path('admin/', admin.site.urls),
    
    # --- URL UNTUK MAHASISWA DAN UMUM ---
    path('login/', login_view, name='login'),
    path('register/step/<int:step>/', register_wizard, name='register_step'), 
    path('register/', lambda request: redirect('register_step', step=1), name='register'), 
    path('registrasi-complete/', registrasi_complete, name='registrasi_complete'),
    path("api/kegiatan-pa-by-jenjang/<int:jenjang_id>/", get_kegiatan_pa_by_jenjang, name="kegiatan_pa_api"),
    path('profil_mahasiswa/', profil_mahasiswa, name='profil_mahasiswa'),
    path('edit_profil/<str:nim>/', edit_profil, name='edit_profil'),
    path('edit-dosen-pembimbing/', edit_dosen_pembimbing, name='edit_dosen_pembimbing'),
    path('data_wajah/', data_wajah, name='data_wajah'),
    path('upload-foto-wajah/', upload_foto_wajah, name='upload_foto_wajah'),
    path('api/hapus-foto-wajah/<int:foto_id>/', hapus_foto_wajah, name='hapus_foto_wajah'),
    path('hapus-semua-foto/', hapus_semua_foto, name='hapus_semua_foto'),
    path('riwayat_presensi/', riwayat_presensi, name='riwayat_presensi'),
    path('progress_sks/', progress_sks, name='progress_sks'),
    path('logout/', logout_view, name='logout'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)