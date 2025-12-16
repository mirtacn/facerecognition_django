# forms.py

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime
from .models import Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Kegiatan_PA, Semester, FotoWajah, Semester

# --- STEP 1: Akun & Identitas ---
class Step1Form(forms.Form):
    nama_lengkap = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Lengkap'})
    )
    nim = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIM / NRP'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ulangi Password'})
    )
    
    # Field Jurusan dengan pilihan
    JURUSAN_CHOICES = [
        ('', 'Pilih Jurusan'),
        ('Teknik Informatika', 'Teknik Informatika'),
        ('Sains Data Terapan', 'Sains Data Terapan'),
    ]
    
    jurusan = forms.ChoiceField(
        choices=JURUSAN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    KELAS_CHOICES = [
        ('', 'Pilih Kelas'),
        ('1 D4 IT A', '1 D4 IT A'),
        ('1 D4 IT B', '1 D4 IT B'),
        ('2 D4 IT A', '2 D4 IT A'),
        ('2 D4 IT B', '2 D4 IT B'),
        ('3 D4 IT A', '3 D4 IT A'),
        ('3 D4 IT B', '3 D4 IT B'),
        ('4 D4 IT A', '4 D4 IT A'),
        ('4 D4 IT B', '4 D4 IT B'),
        ('1 D3 IT A', '1 D3 IT A'),
        ('1 D3 IT B', '1 D3 IT B'),
        ('2 D3 IT A', '2 D3 IT A'),
        ('2 D3 IT B', '2 D3 IT B'),
        ('3 D3 IT A', '3 D3 IT A'),
        ('3 D3 IT B', '3 D3 IT B'),
        ('1 D4 SD A', '1 D4 SD A'),
        ('1 D4 SD B', '1 D4 SD B'),
        ('2 D4 SD A', '2 D4 SD A'),
        ('2 D4 SD B', '2 D4 SD B'),
        ('3 D4 SD A', '3 D4 SD A'),
        ('3 D4 SD B', '3 D4 SD B'),
        ('4 D4 SD A', '4 D4 SD A'),
        ('4 D4 SD B', '4 D4 SD B'),
    ]
    
    kelas = forms.ChoiceField(
        choices=KELAS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Field Angkatan - menambahkan pilihan tahun dinamis
    def get_tahun_angkatan_choices():
        current_year = datetime.now().year
        # Buat pilihan dari 5 tahun sebelumnya hingga 1 tahun ke depan
        years = []
        for year in range(current_year - 5, current_year + 2):
            years.append((str(year), str(year)))
        return [('', 'Pilih Tahun Angkatan')] + years
    
    angkatan = forms.ChoiceField(
        choices=get_tahun_angkatan_choices(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Password tidak cocok.")
        
        # Validasi tambahan: cek jika NIM sesuai dengan angkatan
        nim = cleaned_data.get("nim")
        angkatan = cleaned_data.get("angkatan")
        
        return cleaned_data
    
# --- STEP 2: Akademik ---
# (hapus duplikasi definisi field di bawah, cukup satu definisi saja di atas)
class Step2Form(forms.Form):
    jenjang = forms.ModelChoiceField(
        queryset=Jenjang_Pendidikan.objects.all(),
        empty_label="Pilih Jenjang",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        empty_label="Pilih Semester",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    dosen_pembimbing1 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        empty_label="Pilih Pembimbing 1",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    dosen_pembimbing2 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        empty_label="Pilih Pembimbing 2",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    dosen_pembimbing3 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        required=False,
        empty_label="Pilih Pembimbing 3 (Opsional)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    kegiatan_pa_diambil = forms.ModelMultipleChoiceField(
        queryset=Kegiatan_PA.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        label="Kegiatan PA",
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        jenjang_id = None

        # Jika POST
        if self.is_bound:
            jenjang_id = self.data.get("jenjang")

        # Jika GET dan initial sudah diset
        elif self.initial.get("jenjang"):
            jenjang_initial = self.initial.get("jenjang")
            jenjang_id = (
                jenjang_initial.id if isinstance(jenjang_initial, Jenjang_Pendidikan)
                else jenjang_initial
            )

        # Filter queryset sesuai jenjang
        if jenjang_id:
            self.fields["kegiatan_pa_diambil"].queryset = Kegiatan_PA.objects.filter(
                jenjang_pendidikan_id=jenjang_id
            )
        else:
            self.fields["kegiatan_pa_diambil"].queryset = Kegiatan_PA.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        # --- Validasi Dosen Tidak Boleh Duplikat ---
        d1 = cleaned_data.get("dosen_pembimbing1")
        d2 = cleaned_data.get("dosen_pembimbing2")
        d3 = cleaned_data.get("dosen_pembimbing3")

        dosen_list = [d for d in [d1, d2, d3] if d]

        if len(dosen_list) != len(set(dosen_list)):
            raise forms.ValidationError("Dosen Pembimbing tidak boleh sama.")

        # --- Validasi kegiatan sesuai jenjang (pengamanan) ---
        jenjang = cleaned_data.get("jenjang")
        kegiatan_pa_diambil = cleaned_data.get("kegiatan_pa_diambil")

        if jenjang and kegiatan_pa_diambil:
            valid_queryset = Kegiatan_PA.objects.filter(jenjang_pendidikan_id=jenjang.id)
            for kegiatan in kegiatan_pa_diambil:
                if kegiatan not in valid_queryset:
                    self.add_error("kegiatan_pa_diambil",
                                   "Kegiatan PA tidak sesuai dengan jenjang yang dipilih.")
                    break

        return cleaned_data

# --- STEP 3: Foto (Gunakan Form Biasa) ---
# forms.py - Step3Form yang sangat sederhana
class Step3Form(forms.Form):
    # Hanya sebagai placeholder, validasi akan dilakukan di view
    file_path = forms.FileField(
        label="Foto Wajah",
        required=True
    )

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
    
    # UBAH INI: Gunakan ModelChoiceField
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
    
    # HAPUS __init__ method yang lama