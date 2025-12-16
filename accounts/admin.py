# accounts/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline
from .models import (
    Jenjang_Pendidikan, Tahun_Ajaran, Semester,
    Akun, Mahasiswa, Dosen, Mahasiswa_Dosen,
    Kegiatan_PA, Status_Pemenuhan_SKS,
    Presensi, Durasi, FotoWajah,
    Pengajuan_Pendaftaran
)

# --- Admin dengan Translation ---
@admin.register(Jenjang_Pendidikan)
class JenjangPendidikanAdmin(TranslationAdmin):
    list_display = ('nama_jenjang',)
    search_fields = ('nama_jenjang',)

@admin.register(Tahun_Ajaran)
class TahunAjaranAdmin(TranslationAdmin):
    list_display = ('nama_tahun_ajaran', 'tanggal_mulai', 'tanggal_selesai', 'status_aktif')
    list_filter = ('status_aktif',)
    search_fields = ('nama_tahun_ajaran',)

@admin.register(Semester)
class SemesterAdmin(TranslationAdmin):
    list_display = ('nama_semester',)
    search_fields = ('nama_semester',)

@admin.register(Akun)
class AkunAdmin(TranslationAdmin):
    list_display = ('username', 'email', 'nama_lengkap', 'role', 'status_akun')
    list_filter = ('role', 'status_akun')
    search_fields = ('username', 'email', 'nama_lengkap')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'nama_lengkap', 'nrp')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Custom fields'), {'fields': ('role', 'status_akun')}),
    )

@admin.register(Mahasiswa)
class MahasiswaAdmin(TranslationAdmin):
    list_display = ('nim', 'get_nama', 'jenjang_pendidikan', 'semester', 'kelas', 'angkatan')
    list_filter = ('jenjang_pendidikan', 'semester', 'angkatan')
    search_fields = ('nim', 'user__username', 'user__nama_lengkap')
    raw_id_fields = ('user',)
    
    def get_nama(self, obj):
        return obj.user.nama_lengkap
    get_nama.short_description = _('Nama')
    get_nama.admin_order_field = 'user__nama_lengkap'

@admin.register(Dosen)
class DosenAdmin(TranslationAdmin):
    list_display = ('nip', 'nama_dosen', 'prodi')
    search_fields = ('nip', 'nama_dosen', 'prodi')

class MahasiswaDosenInline(admin.TabularInline):
    model = Mahasiswa_Dosen
    extra = 1
    raw_id_fields = ('dosen',)

@admin.register(Kegiatan_PA)
class KegiatanPAAdmin(TranslationAdmin):
    list_display = ('nama_kegiatan', 'jenjang_pendidikan', 'tahun_ajaran', 'jumlah_sks', 'total_jam_minggu', 'target_jam')
    list_filter = ('jenjang_pendidikan', 'tahun_ajaran')
    search_fields = ('nama_kegiatan',)

@admin.register(Status_Pemenuhan_SKS)
class StatusPemenuhanSKSAdmin(TranslationAdmin):
    list_display = ('mahasiswa', 'kegiatan_pa', 'jumlah_sks', 'jam_target', 'jam_tercapai', 'status_pemenuhan')
    list_filter = ('status_pemenuhan', 'kegiatan_pa')
    search_fields = ('mahasiswa__nim', 'mahasiswa__user__nama_lengkap')
    raw_id_fields = ('mahasiswa', 'kegiatan_pa')

@admin.register(Presensi)
class PresensiAdmin(TranslationAdmin):
    list_display = ('mahasiswa', 'kegiatan_pa', 'tanggal_presensi', 'jam_checkin', 'jam_checkout')
    list_filter = ('tanggal_presensi', 'kegiatan_pa')
    search_fields = ('mahasiswa__nim', 'mahasiswa__user__nama_lengkap')
    raw_id_fields = ('mahasiswa', 'kegiatan_pa')

@admin.register(Durasi)
class DurasiAdmin(TranslationAdmin):
    list_display = ('presensi', 'waktu_durasi')
    search_fields = ('presensi__mahasiswa__nim', 'presensi__mahasiswa__user__nama_lengkap')
    raw_id_fields = ('presensi',)

@admin.register(FotoWajah)
class FotoWajahAdmin(TranslationAdmin):
    list_display = ('mahasiswa', 'file_path', 'keterangan', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('mahasiswa__nim', 'mahasiswa__user__nama_lengkap', 'keterangan')
    raw_id_fields = ('mahasiswa',)
    readonly_fields = ('created_at',)

@admin.register(Pengajuan_Pendaftaran)
class PengajuanPendaftaranAdmin(TranslationAdmin):
    list_display = ('mahasiswa', 'status_pengajuan', 'created_at', 'updated_at')
    list_filter = ('status_pengajuan', 'created_at')
    search_fields = ('mahasiswa__nim', 'mahasiswa__user__nama_lengkap')
    raw_id_fields = ('mahasiswa',)
    readonly_fields = ('created_at', 'updated_at')