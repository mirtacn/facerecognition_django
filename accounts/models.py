# models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

# --- 1. Master Data (Jenjang, Tahun Ajaran) ---

class Jenjang_Pendidikan(models.Model):
    """
    Entitas Jenjang_Pendidikan (Lookup Table)
    """
    # id_jenjang_pendidikan (PK) otomatis oleh Django
    nama_jenjang = models.CharField(max_length=50, unique=True) # Contoh: D3, S1, Lintas Jalur

    def __str__(self):
        return self.nama_jenjang
    
    class Meta:
        verbose_name = "Jenjang Pendidikan"
        verbose_name_plural = "Jenjang Pendidikan"


class Tahun_Ajaran(models.Model):
    """
    Entitas Tahun_Ajaran
    """
    # id_tahun_ajaran (PK) otomatis oleh Django
    nama_semester = models.CharField(max_length=50) # Contoh: Ganjil 2024/2025
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField()
    
    STATUS_CHOICES = [('aktif', 'Aktif'), ('nonaktif', 'Nonaktif')]
    status_aktif = models.CharField(max_length=10, choices=STATUS_CHOICES, default='nonaktif')

    def __str__(self):
        return self.nama_semester
    
    class Meta:
        verbose_name = "Tahun Ajaran"
        verbose_name_plural = "Tahun Ajaran"


# --- 2. Akun dan Pengguna (Mahasiswa, Dosen) ---

class Mahasiswa(models.Model):
    """
    Entitas Mahasiswa (Relasi One-to-One ke Akun/User)
    """
    # id_mahasiswa (PK) otomatis oleh Django
    
    # id_akun (FK)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mahasiswa_profile')
    
    # nrp (nullable, untuk mahasiswa) - Diwakili oleh 'nim' atau 'nrp'
    nrp = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    # Relasi ke Jenjang_Pendidikan
    jenjang_pendidikan = models.ForeignKey(Jenjang_Pendidikan, on_delete=models.SET_NULL, null=True)
    
    nama = models.CharField(max_length=100) # Nama Mahasiswa
    semester = models.CharField(max_length=20)
    kelas = models.CharField(max_length=50)
    sks_total_tempuh = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    def __str__(self):
        return self.nama
    
    class Meta:
        verbose_name = "Mahasiswa"
        verbose_name_plural = "Mahasiswa"


class Dosen(models.Model):
    """
    Entitas Dosen (Relasi One-to-One ke Akun/User)
    """
    # id_dosen (PK) otomatis oleh Django
    
    # id_akun (FK)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dosen_profile')
    
    nama_dosen = models.CharField(max_length=100)
    # Anda bisa menambahkan field NIP/NIDN di sini jika diperlukan
    
    def __str__(self):
        return self.nama_dosen
    
    class Meta:
        verbose_name = "Dosen"
        verbose_name_plural = "Dosen"

class Semester(models.Model):
    """
    Tabel lookup sederhana untuk nama-nama semester (misal: Ganjil, Genap, Pendek).
    """
    # id (PK) otomatis oleh Django
    nama = models.CharField(max_length=50, unique=True) # Contoh: Ganjil, Genap

    def __str__(self):
        return self.nama
    
    class Meta:
        verbose_name = "Nama Semester (Lookup)"
        verbose_name_plural = "Nama Semester (Lookup)"
        
class Mahasiswa_Dosen(models.Model):
    """
    Entitas Mahasiswa_Dosen (Relasi Many-to-Many antara Mahasiswa dan Dosen)
    Ini mencatat Dosen Pembimbing untuk setiap Mahasiswa.
    """
    # id_mahasiswa_dosen (PK) otomatis oleh Django
    
    # id_mahasiswa (FK)
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    
    # id_dosen (FK)
    dosen = models.ForeignKey(Dosen, on_delete=models.CASCADE)
    
    TIPE_CHOICES = [
        ('pembimbing1', 'Pembimbing 1'), 
        ('pembimbing2', 'Pembimbing 2'), 
        ('pembimbing3', 'Pembimbing 3')
    ]
    # tipe_pembimbing ENUM('pembimbing1', 'pembimbing2', 'pembimbing3')
    tipe_pembimbing = models.CharField(max_length=20, choices=TIPE_CHOICES)
    
    class Meta:
        verbose_name = "Mahasiswa Dosen Pembimbing"
        verbose_name_plural = "Mahasiswa Dosen Pembimbing"
        # Memastikan satu mahasiswa hanya memiliki satu tipe pembimbing dari dosen tertentu
        unique_together = ('mahasiswa', 'tipe_pembimbing') 

    def __str__(self):
        return f"{self.mahasiswa.nama} dibimbing oleh {self.dosen.nama_dosen} ({self.get_tipe_pembimbing_display()})"


# --- 3. Kegiatan dan Pemenuhan SKS ---

class Kegiatan_PA(models.Model):
    """
    Entitas Kegiatan_PA (Kegiatan yang menghasilkan SKS)
    """
    # id_kegiatan_pa (PK) otomatis oleh Django
    
    # id_jenjang_pendidikan (FK)
    jenjang_pendidikan = models.ForeignKey(Jenjang_Pendidikan, on_delete=models.CASCADE)
    
    # id_tahun_ajaran (FK)
    tahun_ajaran = models.ForeignKey(Tahun_Ajaran, on_delete=models.CASCADE)
    
    nama_kegiatan = models.CharField(max_length=200)
    jumlah_sks = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    total_jam_target = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    def __str__(self):
        return self.nama_kegiatan
    
    class Meta:
        verbose_name = "Kegiatan PA"
        verbose_name_plural = "Kegiatan PA"


class Status_Pemenuhan_SKS(models.Model):
    """
    Entitas Status_Pemenuhan_SKS
    Mencatat capaian SKS per kegiatan oleh mahasiswa
    """
    # id_status_pemenuhan_sks (PK) otomatis oleh Django
    
    # id_mahasiswa (FK)
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    
    # id_kegiatan_pa (FK)
    kegiatan_pa = models.ForeignKey(Kegiatan_PA, on_delete=models.CASCADE)
    
    jumlah_sks = models.IntegerField(default=0, validators=[MinValueValidator(0)]) # Jumlah SKS yang diperoleh dari kegiatan ini
    jam_target = models.IntegerField(default=0, validators=[MinValueValidator(0)]) # Target jam kegiatan
    jam_tercapai = models.IntegerField(default=0, validators=[MinValueValidator(0)]) # Jam yang sudah dicapai

    # status_pemenuhan ENUM('belum memenuhi', 'memenuhi')
    STATUS_CHOICES = [('belum memenuhi', 'Belum Memenuhi'), ('memenuhi', 'Memenuhi')]
    status_pemenuhan = models.CharField(max_length=20, choices=STATUS_CHOICES, default='belum memenuhi')
    
    class Meta:
        verbose_name = "Status Pemenuhan SKS"
        verbose_name_plural = "Status Pemenuhan SKS"
        unique_together = ('mahasiswa', 'kegiatan_pa') # Satu mahasiswa hanya punya satu status per kegiatan

    def __str__(self):
        return f"SKS {self.kegiatan_pa.nama_kegiatan} oleh {self.mahasiswa.nama}: {self.get_status_pemenuhan_display()}"


# --- 4. Presensi dan Wajah ---

class Presensi(models.Model):
    """
    Entitas Presensi (Untuk mencatat kehadiran)
    """
    # id_presensi (PK) otomatis oleh Django
    
    # id_mahasiswa (FK)
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    
    # id_kegiatan_pa (FK) - Relasi ke Kegiatan_PA
    kegiatan_pa = models.ForeignKey(Kegiatan_PA, on_delete=models.CASCADE)
    
    tanggal_presensi = models.DateField()
    jam_checkin = models.TimeField(null=True, blank=True)
    jam_checkout = models.TimeField(null=True, blank=True)
    
    # foto_checkin, foto_checkout
    foto_checkin = models.ImageField(upload_to='presensi/checkin/', null=True, blank=True)
    foto_checkout = models.ImageField(upload_to='presensi/checkout/', null=True, blank=True)
    
    def __str__(self):
        return f"Presensi {self.mahasiswa.nama} - {self.tanggal_presensi} ({self.kegiatan_pa.nama_kegiatan})"
    
    class Meta:
        verbose_name = "Presensi"
        verbose_name_plural = "Presensi"


class Durasi(models.Model):
    """
    Entitas Durasi
    Mencatat durasi yang dihasilkan dari Presensi
    """
    # id_durasi (PK) otomatis oleh Django
    
    # id_presensi (FK) - Relasi One-to-One ke Presensi
    presensi = models.OneToOneField(Presensi, on_delete=models.CASCADE)
    
    waktu_durasi = models.DurationField() # Digunakan untuk menyimpan selisih waktu (jam_checkout - jam_checkin)

    def __str__(self):
        return f"Durasi Presensi {self.presensi.id}: {self.waktu_durasi}"
    
    class Meta:
        verbose_name = "Durasi Presensi"
        verbose_name_plural = "Durasi Presensi"


class FotoWajah(models.Model):
    """
    Entitas Foto_Wajah
    """
    # id_foto (PK) otomatis oleh Django
    
    # id_mahasiswa (FK)
    mahasiswa = models.ForeignKey(Mahasiswa, related_name='foto_wajah', on_delete=models.CASCADE)
    
    # file_path (Diwakili oleh ImageField)
    file_path = models.ImageField(upload_to='dataset_wajah/')
    
    def __str__(self):
        return f"Foto Wajah {self.id} milik {self.mahasiswa.nama}"
    
    class Meta:
        verbose_name = "Foto Wajah"
        verbose_name_plural = "Foto Wajah"

# --- 5. Pengajuan Pendaftaran ---

class Pengajuan_Pendaftaran(models.Model):
    """
    Entitas Pengajuan_Pendaftaran
    """
    # id_pengajuan_pendaftaran (PK) otomatis oleh Django
    
    # id_mahasiswa (FK) - Relasi One-to-One
    mahasiswa = models.OneToOneField(Mahasiswa, on_delete=models.CASCADE)
    
    # status_pengajuan ENUM('pending', 'disetujui', 'ditolak')
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak')
    ]
    status_pengajuan = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    alasan_penolakan = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Pengajuan {self.mahasiswa.nama}: {self.get_status_pengajuan_display()}"
    
    class Meta:
        verbose_name = "Pengajuan Pendaftaran"
        verbose_name_plural = "Pengajuan Pendaftaran"