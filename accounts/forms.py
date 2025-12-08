# forms.py

from django import forms
from .models import Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Kegiatan_PA, Semester, FotoWajah

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