# forms.py

from django import forms
from .models import Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Kegiatan_PA

# --- STEP 1: Akun & Identitas ---
class Step1Form(forms.Form):
    nama_lengkap = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Lengkap'}))
    nim = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIM / NRP'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ulangi Password'}))
    kelas = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kelas (Misal: 3 D4 IT A)'}))

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', "Password tidak cocok.")
        return cleaned_data

# --- STEP 2: Akademik ---
class Step2Form(forms.Form):
    jenjang = forms.ModelChoiceField(
        queryset=Jenjang_Pendidikan.objects.all(),
        empty_label="Pilih Jenjang",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    semester = forms.ModelChoiceField(
        queryset=Tahun_Ajaran.objects.filter(status_aktif='aktif'),
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
        queryset=Kegiatan_PA.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}),
        label="Kegiatan PA"
    )

    def clean(self):
        cleaned_data = super().clean()
        d1 = cleaned_data.get('dosen_pembimbing1')
        d2 = cleaned_data.get('dosen_pembimbing2')
        d3 = cleaned_data.get('dosen_pembimbing3')
        
        # Pastikan dosen unik
        dosen_list = [d for d in [d1, d2, d3] if d]
        if len(dosen_list) != len(set(dosen_list)):
             raise forms.ValidationError("Dosen Pembimbing tidak boleh sama.")
        return cleaned_data

# --- STEP 3: Foto (Gunakan Form Biasa) ---
class Step3Form(forms.Form):
    # Kita gunakan Form biasa agar validasi lebih mudah dikontrol di views
    file_path = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        label="Upload Foto Wajah"
    )