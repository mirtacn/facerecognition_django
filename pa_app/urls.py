from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect 
from accounts.views import (
    login_view, tambah_kegiatan_sks, get_detail_tahun_ajaran, 
    hapus_tahun_ajaran, edit_tahun_ajaran, tambah_tahun_ajaran, 
    aktifkan_tahun_ajaran, edit_kegiatan_sks, get_detail_kegiatan, 
    hapus_kegiatan_sks, checkin_presensi, get_presensi_today, 
    get_foto_wajah_detail, download_all_fotos, checkout_presensi, 
    register_wizard, edit_mahasiswa, hapus_mahasiswa, kamera_presensi_mhs, 
    admin_dashboard, pengaturan_sistem, status_pemenuhan, rekap_presensi, 
    monitoring_presensi, data_sks, management_data, approval_pendaftaran, 
    master_data_wajah, data_mahasiswa, monitor_durasi, profil_mahasiswa, 
    data_wajah, riwayat_presensi, progress_sks, edit_profil, 
    get_kegiatan_pa_by_jenjang, registrasi_complete, edit_dosen_pembimbing, 
    upload_foto_wajah, hapus_foto_wajah, hapus_semua_foto, logout_view, status_pemenuhan_sks
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # --- URL UNTUK ADMIN APLIKASI ---
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/kamera_presensi_mhs/', kamera_presensi_mhs, name='kamera_presensi_mhs'),
    path('admin/monitor-durasi/', monitor_durasi, name='monitor_durasi'),
    path('admin/management-data/', management_data, name='management_data'),
    path('admin/approval-pendaftaran/', approval_pendaftaran, name='approval_pendaftaran'),
    path('admin/data-mahasiswa/', data_mahasiswa, name='data_mahasiswa'),
    path('admin/edit-mahasiswa/<int:mahasiswa_id>/', edit_mahasiswa, name='edit_mahasiswa'),
    path('admin/hapus-mahasiswa/<int:mahasiswa_id>/', hapus_mahasiswa, name='hapus_mahasiswa'),
    path('admin/master-data-wajah/', master_data_wajah, name='master_data_wajah'),
    path('admin/master-data-wajah/<int:mahasiswa_id>/detail/', get_foto_wajah_detail, name='get_foto_wajah_detail'),
    path('admin/master-data-wajah/<int:mahasiswa_id>/download/', download_all_fotos, name='download_all_fotos'),
    
    # URLs untuk Data SKS
    path('admin/data-sks/', data_sks, name='data_sks'),
    path('admin/data-sks/tambah/', tambah_kegiatan_sks, name='tambah_kegiatan_sks'),
    path('admin/data-sks/<int:kegiatan_id>/edit/', edit_kegiatan_sks, name='edit_kegiatan_sks'),
    path('admin/data-sks/<int:kegiatan_id>/hapus/', hapus_kegiatan_sks, name='hapus_kegiatan_sks'),
    path('admin/data-sks/<int:kegiatan_id>/detail/', get_detail_kegiatan, name='get_detail_kegiatan'),
    
    # URLs untuk Tahun Ajaran
    path('admin/data-sks/tahun-ajaran/tambah/', tambah_tahun_ajaran, name='tambah_tahun_ajaran'),
    path('admin/data-sks/tahun-ajaran/<int:tahun_id>/edit/', edit_tahun_ajaran, name='edit_tahun_ajaran'),
    path('admin/data-sks/tahun-ajaran/<int:tahun_id>/hapus/', hapus_tahun_ajaran, name='hapus_tahun_ajaran'),
    path('admin/data-sks/tahun-ajaran/<int:tahun_id>/detail/', get_detail_tahun_ajaran, name='get_detail_tahun_ajaran'),
    path('admin/data-sks/tahun-ajaran/aktifkan/', aktifkan_tahun_ajaran, name='aktifkan_tahun_ajaran'),

    path('admin/monitoring-presensi/', monitoring_presensi, name='monitoring_presensi'),
    path('admin/status_pemenuhan_sks/', status_pemenuhan_sks, name='status_pemenuhan_sks'),
    path('api/checkin/', checkin_presensi, name='checkin_presensi'),
    path('api/checkout/', checkout_presensi, name='checkout_presensi'),
    path('api/presensi-today/', get_presensi_today, name='get_presensi_today'),
    path('admin/rekap-presensi/', rekap_presensi, name='rekap_presensi'),
    path('admin/status-pemenuhan/', status_pemenuhan, name='status_pemenuhan'),
    path('admin/pengaturan-sistem/', pengaturan_sistem, name='pengaturan_sistem'),
    
    # --- DJANGO ADMIN ---
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