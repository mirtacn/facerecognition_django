# accounts/translation.py
from modeltranslation.translator import translator, TranslationOptions
from .models import (
    Jenjang_Pendidikan, Tahun_Ajaran, Semester, 
    Akun, Mahasiswa, Dosen, Mahasiswa_Dosen,
    Kegiatan_PA, Status_Pemenuhan_SKS,
    Presensi, Durasi, FotoWajah,
    Pengajuan_Pendaftaran
)

# --- 1. Master Data Translation ---
class JenjangPendidikanTranslationOptions(TranslationOptions):
    fields = ()

class TahunAjaranTranslationOptions(TranslationOptions):
    fields = ()

class SemesterTranslationOptions(TranslationOptions):
    fields = ()

# --- 2. Akun dan Pengguna Translation ---
class AkunTranslationOptions(TranslationOptions):
    fields = ()

class MahasiswaTranslationOptions(TranslationOptions):
    fields = ()

class DosenTranslationOptions(TranslationOptions):
    fields = ()

class MahasiswaDosenTranslationOptions(TranslationOptions):
    fields = ()

# --- 3. Kegiatan dan Pemenuhan SKS Translation ---
class KegiatanPATranslationOptions(TranslationOptions):
    fields = ()

class StatusPemenuhanSKSTranslationOptions(TranslationOptions):
    fields = ()

# --- 4. Presensi dan Wajah Translation ---
class PresensiTranslationOptions(TranslationOptions):
    fields = ()

class DurasiTranslationOptions(TranslationOptions):
    fields = ()

class FotoWajahTranslationOptions(TranslationOptions):
    fields = ()

# --- 5. Pengajuan Pendaftaran Translation ---
class PengajuanPendaftaranTranslationOptions(TranslationOptions):
    fields = ()

# --- Register semua model untuk translation ---
translator.register(Jenjang_Pendidikan, JenjangPendidikanTranslationOptions)
translator.register(Tahun_Ajaran, TahunAjaranTranslationOptions)
translator.register(Semester, SemesterTranslationOptions)
translator.register(Akun, AkunTranslationOptions)
translator.register(Mahasiswa, MahasiswaTranslationOptions)
translator.register(Dosen, DosenTranslationOptions)
translator.register(Mahasiswa_Dosen, MahasiswaDosenTranslationOptions)
translator.register(Kegiatan_PA, KegiatanPATranslationOptions)
translator.register(Status_Pemenuhan_SKS, StatusPemenuhanSKSTranslationOptions)
translator.register(Presensi, PresensiTranslationOptions)
translator.register(Durasi, DurasiTranslationOptions)
translator.register(FotoWajah, FotoWajahTranslationOptions)
translator.register(Pengajuan_Pendaftaran, PengajuanPendaftaranTranslationOptions)