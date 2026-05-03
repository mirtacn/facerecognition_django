# forms.py - VERSION LENGKAP

from django import forms
from django.core.validators import MinLengthValidator, RegexValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from .models import Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Kegiatan_PA, Semester, Prodi, Kelas


# --- STEP 1: Akun & Identitas ---
class Step1Form(forms.Form):
    # Data pribadi
    nama_lengkap = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Lengkap'})
    )
    nim = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIM / NRP'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    
    # Password dengan validasi realtime (akan dihandle di JS, tapi tetap validasi di backend)
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'id': 'id_password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ulangi Password',
            'id': 'id_confirm_password'
        })
    )
    
    # Jenjang (dropdown, filter prodi)
    jenjang = forms.ModelChoiceField(
        queryset=Jenjang_Pendidikan.objects.filter(
            nama_jenjang__in=['D3 - Diploma 3', 'D4 - Diploma 4', 'S2 - Magister']
        ),
        empty_label="Pilih Jenjang",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_jenjang'})
    )
    
    # Prodi (akan diisi dinamis via JS, hanya menampilkan nama prodi tanpa kode)
    prodi = forms.ModelChoiceField(
        queryset=Prodi.objects.none(),
        empty_label="Pilih Program Studi",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_prodi'})
    )
    
    kelas = forms.ModelChoiceField(
        queryset=Kelas.objects.filter(is_active=True).order_by('nama_kelas'),
        empty_label="Pilih Kelas",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_kelas'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # KELAS TIDAK PERLU DISET ULANG (sudah di-set di field)
        # Hanya prodi yang perlu difilter
        jenjang_id = None
        if self.is_bound:
            jenjang_id = self.data.get('jenjang')
        elif self.initial.get('jenjang'):
            jenjang = self.initial.get('jenjang')
            jenjang_id = jenjang.id if isinstance(jenjang, Jenjang_Pendidikan) else jenjang
        
        if jenjang_id:
            self.fields['prodi'].queryset = Prodi.objects.filter(
                jenjang_id=jenjang_id,
                is_active=True
            ).order_by('nama_prodi')

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # Validasi password match
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Password tidak cocok.")
        
        # Validasi password complexity (huruf dan angka)
        if password:
            if not any(c.isalpha() for c in password):
                self.add_error('password', "Password harus mengandung huruf.")
            if not any(c.isdigit() for c in password):
                self.add_error('password', "Password harus mengandung angka.")
        
        # Validasi NIM sudah terdaftar (akan di cek di view juga)
        return cleaned_data

# --- STEP 2: Akademik ---
# --- STEP 2: Akademik ---
# --- STEP 2: Akademik ---
class Step2Form(forms.Form):
    # Semester (filter by jenjang)
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.none(),
        empty_label="Pilih Semester",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_semester'})
    )
    
    # Dosen pembimbing - PAKAI CLASS YANG SAMA PERSIS dengan Step1Form
    dosen_pembimbing1 = forms.ModelChoiceField(
        queryset=Dosen.objects.all().order_by('nama_dosen'),
        empty_label="Pilih Pembimbing 1",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_dosen1'})
    )
    
    dosen_pembimbing2 = forms.ModelChoiceField(
        queryset=Dosen.objects.all().order_by('nama_dosen'),
        empty_label="Pilih Pembimbing 2",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_dosen2'})
    )
    
    dosen_pembimbing3 = forms.ModelChoiceField(
        queryset=Dosen.objects.all().order_by('nama_dosen'),
        required=False,
        empty_label="Pilih Pembimbing 3 (Opsional)",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_dosen3'})
    )
    
    # Kegiatan PA yang diambil
    kegiatan_pa_diambil = forms.ModelMultipleChoiceField(
        queryset=Kegiatan_PA.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        label="Kegiatan PA",
        required=True
    )

    def __init__(self, *args, **kwargs):
        jenjang_obj = kwargs.pop('jenjang_obj', None)
        super().__init__(*args, **kwargs)
        
        if jenjang_obj:
            self.fields["kegiatan_pa_diambil"].queryset = Kegiatan_PA.objects.filter(
                jenjang_pendidikan_id=jenjang_obj.id
            )
            
            jenjang_nama = jenjang_obj.nama_jenjang
            if "D3" in jenjang_nama:
                jenjang_kode = 'D3'
            elif "D4" in jenjang_nama:
                jenjang_kode = 'D4'
            elif "S2" in jenjang_nama:
                jenjang_kode = 'S2'
            else:
                jenjang_kode = None
            
            if jenjang_kode:
                semesters = Semester.objects.filter(jenjang=jenjang_kode).order_by('nomor_semester')
                self.fields["semester"].queryset = semesters
                self.fields["semester"].label_from_instance = lambda obj: obj.nama_semester

    def clean(self):
        cleaned_data = super().clean()
        
        d1 = cleaned_data.get("dosen_pembimbing1")
        d2 = cleaned_data.get("dosen_pembimbing2")
        d3 = cleaned_data.get("dosen_pembimbing3")
        
        dosen_list = [d for d in [d1, d2, d3] if d]
        if len(dosen_list) != len(set(dosen_list)):
            raise forms.ValidationError("Dosen Pembimbing tidak boleh sama.")
        
        return cleaned_data
    
# --- STEP 3: Foto ---
from django.forms.widgets import ClearableFileInput

class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True

class Step3Form(forms.Form):
    # Foto wajah (multiple)
    foto_wajah = forms.FileField(
        label="Foto Wajah",
        required=True,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'id_foto_wajah'
        })
    )
    
    # Upload kartu identitas (single file)
    foto_kartu_identitas = forms.FileField(
        label="Foto Kartu Identitas (KTP/KTM)",
        required=True,
        widget=ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'id_foto_kartu'
        })
    )


# --- FILTER REKAP PRESENSI ---
class FilterRekapPresensiForm(forms.Form):
    tanggal_mulai = forms.DateField(
        label='Tanggal Mulai',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'id': 'tanggal_mulai_filter'
        })
    )
    tanggal_selesai = forms.DateField(
        label='Tanggal Selesai',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'id': 'tanggal_selesai_filter'
        })
    )
    tingkatan = forms.ModelChoiceField(
        queryset=Jenjang_Pendidikan.objects.all(),
        label='Tingkatan',
        required=False,
        empty_label="Semua Tingkatan",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'tingkatan_filter'
        })
    )
    kegiatan = forms.ModelChoiceField(
        queryset=Kegiatan_PA.objects.all().order_by('nama_kegiatan'),
        label='Kegiatan',
        required=False,
        empty_label="Semua Kegiatan",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'kegiatan_filter'
        })
    )