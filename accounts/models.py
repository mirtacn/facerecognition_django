# models.py

from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from datetime import date
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

def current_year():
    return date.today().year

class Jenjang_Pendidikan(models.Model):
    nama_jenjang = models.CharField(_("Education Level"), max_length=50, unique=True)
    
    def __str__(self):
        return self.nama_jenjang
    
    class Meta:
        verbose_name = _("Education Level")
        verbose_name_plural = _("Education Levels")

class Tahun_Ajaran(models.Model):
    nama_tahun_ajaran = models.CharField(_("Academic Year Name"), max_length=100, null=True, blank=True, default=None)
    tanggal_mulai = models.DateField(_("Start Date"))
    tanggal_selesai = models.DateField(_("End Date"))
    STATUS_CHOICES = [
        ('aktif', _('Active')),
        ('nonaktif', _('Inactive'))
    ]
    status_aktif = models.CharField(_("Active Status"), max_length=10, choices=STATUS_CHOICES, default='nonaktif')
    
    def __str__(self):
        return self.nama_tahun_ajaran
    
    class Meta:
        verbose_name = _("Academic Year")
        verbose_name_plural = _("Academic Years")

class Semester(models.Model):
    nama_semester = models.CharField(_("Semester Name"), max_length=20, unique=True)
    
    def __str__(self):
        return self.nama_semester
    
    class Meta:
        verbose_name = _("Semester")
        verbose_name_plural = _("Semesters")

# --- 2. Akun dan Pengguna (Mahasiswa, Dosen) ---

class Akun(AbstractUser):
    nrp = models.CharField(_("NRP"), max_length=20, unique=True, null=True, blank=True)
    
    ROLE_CHOICES = [
        ('admin', _('Admin')),
        ('mahasiswa', _('Student')),
    ]
    role = models.CharField(_("Role"), max_length=20, choices=ROLE_CHOICES, default='mahasiswa')
    
    STATUS_AKUN_CHOICES = [
        ('aktif', _('Active')),
        ('nonaktif', _('Inactive')),
    ]
    status_akun = models.CharField(_("Account Status"), max_length=10, choices=STATUS_AKUN_CHOICES, default='aktif')
    
    nama_lengkap = models.CharField(_("Full Name"), max_length=150, blank=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    class Meta:
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")

class Mahasiswa(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mahasiswa_profile')
    jenjang_pendidikan = models.ForeignKey(Jenjang_Pendidikan, on_delete=models.SET_NULL, null=True)
    nim = models.CharField(_("Student ID"), max_length=20, unique=True)
    semester = models.ForeignKey(Semester, on_delete=models.SET_NULL, null=True)
    kelas = models.CharField(_("Class"), max_length=50)
    sks_total_tempuh = models.IntegerField(_("Total Credits Taken"), default=0, validators=[MinValueValidator(0)])
    angkatan = models.PositiveSmallIntegerField(
        _("Batch Year"),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(current_year)
        ]
    )
    jurusan = models.CharField(_("Major"), max_length=255, null=True, blank=True)
    kegiatan_pa = models.ManyToManyField('Kegiatan_PA', blank=True)
    
    def __str__(self):
        return self.user.nama_lengkap if self.user.nama_lengkap else self.user.username
    
    class Meta:
        verbose_name = _("Student")
        verbose_name_plural = _("Students")

class Dosen(models.Model):
    nip = models.CharField(_("NIP"), max_length=30, unique=True)
    nama_dosen = models.CharField(_("Lecturer Name"), max_length=150)
    prodi = models.CharField(_("Study Program"), max_length=100)
    
    def __str__(self):
        return f"{self.nama_dosen} ({self.nip})"
    
    class Meta:
        verbose_name = _("Lecturer")
        verbose_name_plural = _("Lecturers")

class Mahasiswa_Dosen(models.Model):
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    dosen = models.ForeignKey(Dosen, on_delete=models.CASCADE)
    
    TIPE_CHOICES = [
        ('pembimbing1', _('Supervisor 1')),
        ('pembimbing2', _('Supervisor 2')),
        ('pembimbing3', _('Supervisor 3'))
    ]
    tipe_pembimbing = models.CharField(_("Supervisor Type"), max_length=20, choices=TIPE_CHOICES)
    
    class Meta:
        verbose_name = _("Student Lecturer")
        verbose_name_plural = _("Student Lecturers")
        unique_together = ('mahasiswa', 'tipe_pembimbing')
    
    def __str__(self):
        return f"{self.mahasiswa.user.nama_lengkap} supervised by {self.dosen.nama_dosen}"

# --- 3. Kegiatan dan Pemenuhan SKS ---

class Kegiatan_PA(models.Model):
    jenjang_pendidikan = models.ForeignKey(Jenjang_Pendidikan, on_delete=models.CASCADE)
    tahun_ajaran = models.ForeignKey(Tahun_Ajaran, on_delete=models.CASCADE)
    nama_kegiatan = models.CharField(_("Activity Name"), max_length=200)
    jumlah_sks = models.IntegerField(_("Credits"), default=0, validators=[MinValueValidator(0)])
    total_jam_minggu = models.IntegerField(_("Total Hours per Week"), default=0, validators=[MinValueValidator(0)])
    target_jam = models.IntegerField(_("Target Hours"), default=0, validators=[MinValueValidator(0)])
    
    def __str__(self):
        return self.nama_kegiatan
    
    class Meta:
        verbose_name = _("PA Activity")
        verbose_name_plural = _("PA Activities")

class Status_Pemenuhan_SKS(models.Model):
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    kegiatan_pa = models.ForeignKey(Kegiatan_PA, on_delete=models.CASCADE)
    jumlah_sks = models.IntegerField(_("Credits Earned"), default=0, validators=[MinValueValidator(0)])
    jam_target = models.IntegerField(_("Target Hours"), default=0, validators=[MinValueValidator(0)])
    jam_tercapai = models.IntegerField(_("Achieved Hours"), default=0, validators=[MinValueValidator(0)])
    
    STATUS_CHOICES = [
        ('belum memenuhi', _('Not Fulfilled')),
        ('memenuhi', _('Fulfilled'))
    ]
    status_pemenuhan = models.CharField(_("Fulfillment Status"), max_length=20, choices=STATUS_CHOICES, default='belum memenuhi')
    
    class Meta:
        verbose_name = _("Credit Fulfillment Status")
        verbose_name_plural = _("Credit Fulfillment Statuses")
        unique_together = ('mahasiswa', 'kegiatan_pa')
    
    def __str__(self):
        return f"SKS {self.kegiatan_pa.nama_kegiatan} by {self.mahasiswa.user.nama_lengkap}"

# --- 4. Presensi dan Wajah ---

class Presensi(models.Model):
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    kegiatan_pa = models.ForeignKey(Kegiatan_PA, on_delete=models.CASCADE)
    tanggal_presensi = models.DateField(_("Attendance Date"))
    jam_checkin = models.TimeField(_("Check-in Time"), null=True, blank=True)
    jam_checkout = models.TimeField(_("Check-out Time"), null=True, blank=True)
    foto_checkin = models.ImageField(_("Check-in Photo"), upload_to='presensi/checkin/', null=True, blank=True)
    foto_checkout = models.ImageField(_("Check-out Photo"), upload_to='presensi/checkout/', null=True, blank=True)
    
    def __str__(self):
        return f"Attendance {self.mahasiswa.user.nama_lengkap} - {self.tanggal_presensi}"
    
    class Meta:
        verbose_name = _("Attendance")
        verbose_name_plural = _("Attendances")

class Durasi(models.Model):
    presensi = models.OneToOneField(Presensi, on_delete=models.CASCADE)
    waktu_durasi = models.DurationField(_("Duration"))
    
    def __str__(self):
        return f"Duration for Attendance {self.presensi.id}"
    
    class Meta:
        verbose_name = _("Attendance Duration")
        verbose_name_plural = _("Attendance Durations")

class FotoWajah(models.Model):
    mahasiswa = models.ForeignKey(Mahasiswa, related_name='foto_wajah', on_delete=models.CASCADE)
    file_path = models.ImageField(_("File Path"), upload_to='dataset_wajah/')
    keterangan = models.CharField(_("Description"), max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    
    def __str__(self):
        return f"Face Photo {self.id} of {self.mahasiswa.user.nama_lengkap}"
    
    class Meta:
        verbose_name = _("Face Photo")
        verbose_name_plural = _("Face Photos")
        ordering = ['-created_at']

# --- 5. Pengajuan Pendaftaran ---

class Pengajuan_Pendaftaran(models.Model):
    mahasiswa = models.OneToOneField(Mahasiswa, on_delete=models.CASCADE)
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('disetujui', _('Approved')),
        ('ditolak', _('Rejected'))
    ]
    status_pengajuan = models.CharField(_("Submission Status"), max_length=10, choices=STATUS_CHOICES, default='pending')
    alasan_penolakan = models.TextField(_("Rejection Reason"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    
    def __str__(self):
        return f"Submission {self.mahasiswa.user.nama_lengkap}: {self.get_status_pengajuan_display()}"
    
    class Meta:
        verbose_name = _("Registration Submission")
        verbose_name_plural = _("Registration Submissions")