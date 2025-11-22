# forms.py

from django import forms
from .models import Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Kegiatan_PA 
# Pastikan semua model yang relevan sudah di-import dari models.py Anda

# --- STEP 1: Akun & Identitas (TIDAK BERUBAH) ---
class Step1Form(forms.Form):
    """
    Form untuk pendaftaran/akun baru.
    """
    nama_lengkap = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan nama lengkap'})
    )
    nim = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: 2021001234'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'nama@universitas.ac.id'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimal 8 karakter'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ulangi password'})
    )
    kelas = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: A, B, atau C'})
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Password tidak cocok.")
            
        return cleaned_data
    
# -------------------------------------------------------------------
# --- STEP 2: Akademik dan Kegiatan PA (REVISI BESAR DI SINI) ---
# -------------------------------------------------------------------

class Step2Form(forms.Form):
    """
    Form untuk data akademik (Jenjang, Semester, Dosen, Kegiatan PA).
    Revisi: Menggunakan 3 field Dosen Pembimbing terpisah.
    """
    
    # 1. Jenjang (Jenjang_Pendidikan)
    jenjang = forms.ModelChoiceField(
        queryset=Jenjang_Pendidikan.objects.all(),
        empty_label="Pilih Jenjang Pendidikan",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Jenjang Pendidikan"
    )

    # 2. Semester (Tahun_Ajaran)
    semester = forms.ModelChoiceField(
        queryset=Tahun_Ajaran.objects.filter(status_aktif='aktif').order_by('-tanggal_mulai'),
        empty_label="Pilih Semester Aktif",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Tahun Ajaran/Semester"
    )

    # --- INPUT DOSEN PEMBIMBING (3 Field) ---
    
    # 3. Dosen Pembimbing 1 (Wajib)
    dosen_pembimbing1 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        empty_label="Pilih Pembimbing 1 (Wajib)",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Dosen Pembimbing 1"
    )
    
    # 4. Dosen Pembimbing 2 (Wajib)
    dosen_pembimbing2 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        empty_label="Pilih Pembimbing 2 (Wajib)",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Dosen Pembimbing 2"
    )
    
    # 5. Dosen Pembimbing 3 (Opsional)
    dosen_pembimbing3 = forms.ModelChoiceField(
        queryset=Dosen.objects.all(),
        empty_label="Pilih Pembimbing 3 (Opsional)",
        required=False, # Dibuat opsional
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Dosen Pembimbing 3"
    )

    # 6. Kegiatan PA (Menggantikan MataKuliah)
    kegiatan_pa_diambil = forms.ModelMultipleChoiceField(
        queryset=Kegiatan_PA.objects.all(), 
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}), 
        label="Kegiatan PA yang Akan Diikuti"
    )
    
    def clean(self):
        """Validasi untuk memastikan Dosen Pembimbing tidak sama."""
        cleaned_data = super().clean()
        d1 = cleaned_data.get('dosen_pembimbing1')
        d2 = cleaned_data.get('dosen_pembimbing2')
        d3 = cleaned_data.get('dosen_pembimbing3')
        
        dosen_list = [d for d in [d1, d2, d3] if d is not None]
        
        # Validasi: Dosen harus berbeda
        if len(dosen_list) != len(set(dosen_list)):
             # Gunakan non_field_errors agar pesan muncul di bagian atas form
             raise forms.ValidationError(
                "Dosen Pembimbing yang dipilih harus berbeda satu sama lain."
            )
        
        return cleaned_data

# --- STEP 3: Upload Foto (TIDAK BERUBAH) ---
class Step3Form(forms.Form):
    """
    Form untuk upload foto wajah.
    """
    file_path = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        label="Upload Foto Wajah (Ambil minimal 5 foto wajah untuk dataset)"
    )