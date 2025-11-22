from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import Step1Form, Step2Form, Step3Form
from .models import Mahasiswa, FotoWajah, Kegiatan_PA, Jenjang_Pendidikan, Tahun_Ajaran, Dosen, Mahasiswa_Dosen, Pengajuan_Pendaftaran
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.db import transaction # Penting untuk operasi database yang terikat

def register_wizard(request, step=1):
    # Ambil data session yang sudah ada (jika user back)
    step1_data = request.session.get('step1_data', {})
    # Catatan: step2_data sekarang menyimpan ID objek FK, bukan string, dan list ID Kegiatan_PA
    step2_data = request.session.get('step2_data', {})

    if step == 1:
        # Step 1: Akun dan Data Dasar Mahasiswa
        form = Step1Form(request.POST or None, initial=step1_data)
        if request.method == 'POST' and form.is_valid():
            # Simpan data form ke session
            request.session['step1_data'] = form.cleaned_data
            return redirect('register_step', step=2)
            
    elif step == 2:
        # Step 2: Akademik (Jenjang, Semester, Dosen, Kegiatan PA)
        
        # --- PERBAIKAN: Penanganan ModelChoiceField di Session ---
        initial_data = request.session.get('step2_data', {})
        
        # Saat inisialisasi form (GET), kita harus konversi ID menjadi objek untuk ModelChoiceField
        if not request.POST:
            if initial_data.get('jenjang'):
                initial_data['jenjang'] = Jenjang_Pendidikan.objects.filter(id=initial_data['jenjang']).first()
            if initial_data.get('semester'):
                initial_data['semester'] = Tahun_Ajaran.objects.filter(id=initial_data['semester']).first()
            if initial_data.get('dosen_pembimbing'):
                initial_data['dosen_pembimbing'] = Dosen.objects.filter(id=initial_data['dosen_pembimbing']).first()
            
            # Konversi list ID Kegiatan_PA menjadi QuerySet
            kp_ids = initial_data.get('kegiatan_pa_diambil', [])
            if kp_ids:
                initial_data['kegiatan_pa_diambil'] = Kegiatan_PA.objects.filter(id__in=kp_ids)

        form = Step2Form(request.POST or None, initial=initial_data)
        
        if request.method == 'POST':
            if form.is_valid():
                data = form.cleaned_data
                
                # Setelah form divalidasi, konversi objek kembali menjadi ID untuk disimpan di session
                # Foreign Key fields (ModelChoiceField)
                data['jenjang'] = data['jenjang'].id
                data['semester'] = data['semester'].id
                data['dosen_pembimbing'] = data['dosen_pembimbing'].id
                
                # Many-to-Many fields (ModelMultipleChoiceField)
                data['kegiatan_pa_diambil'] = [kp.id for kp in data['kegiatan_pa_diambil']]
                
                request.session['step2_data'] = data
                return redirect('register_step', step=3)

    elif step == 3:
        # Step 3: Upload Foto dan Finalisasi Data
        
        # Pastikan data step 1 & 2 ada sebelum memproses finalisasi
        if not step1_data or not step2_data:
             messages.error(request, "Lengkapi Step 1 & 2 terlebih dahulu.")
             return redirect('register_step', step=1)
        
        # NOTE: Step3Form menggunakan forms.FileField yang hanya menerima satu file.
        # Jika Anda ingin 5 foto, Anda harus memodifikasi Step3Form dan kode ini.
        form = Step3Form(request.POST or None, request.FILES or None)
        
        if request.method == 'POST' and form.is_valid():
            
            # Gunakan transaction untuk memastikan semua operasi DB berhasil atau gagal semua
            try:
                with transaction.atomic():
                    # 1. Create User (Akun)
                    user = User.objects.create_user(
                        username=step1_data['nim'], # Menggunakan NIM/NRP sebagai username
                        email=step1_data['email'],
                        password=step1_data['password']
                    )
                    
                    # 2. Fetch Foreign Key Objects (berdasarkan ID yang disimpan di session)
                    jenjang_obj = Jenjang_Pendidikan.objects.get(id=step2_data['jenjang'])
                    dosen_obj = Dosen.objects.get(id=step2_data['dosen_pembimbing'])
                    
                    # 3. Create Mahasiswa
                    mhs = Mahasiswa.objects.create(
                        user=user,
                        nrp=step1_data['nim'],         # nrp
                        nama=step1_data['nama_lengkap'], # nama
                        jenjang_pendidikan=jenjang_obj, # FK ke Jenjang_Pendidikan
                        semester=step2_data['semester'], # semester (String, dari Tahun_Ajaran.nama_semester)
                        kelas=step1_data['kelas'],
                        sks_total_tempuh=0
                    )

                    # 4. Create Mahasiswa_Dosen (Pembimbing 1)
                    Mahasiswa_Dosen.objects.create(
                        mahasiswa=mhs,
                        dosen=dosen_obj,
                        tipe_pembimbing='pembimbing1'
                    )
                    
                    # 5. Create Pengajuan Pendaftaran (Opsional, jika proses ini dianggap pendaftaran)
                    Pengajuan_Pendaftaran.objects.create(
                        mahasiswa=mhs,
                        status_pengajuan='pending' # Default status
                    )

                    # 6. Simpan Foto ke tabel FotoWajah
                    file = request.FILES.get('file_path') # Nama field di Step3Form yang direvisi
                    if file:
                        # Membuat objek FotoWajah (image=file_path)
                        FotoWajah.objects.create(mahasiswa=mhs, file_path=file) 

                    # 7. Bersihkan session & Selesai
                    del request.session['step1_data']
                    del request.session['step2_data']
                    messages.success(request, "Registrasi Lengkap Berhasil! Silakan masuk.")
                    return redirect('login_view')

            except Dosen.DoesNotExist:
                messages.error(request, "Dosen Pembimbing tidak ditemukan.")
                return redirect('register_step', step=2)
            except Jenjang_Pendidikan.DoesNotExist:
                messages.error(request, "Jenjang Pendidikan tidak valid.")
                return redirect('register_step', step=2)
            except Exception as e:
                # Handle error umum, termasuk masalah DB atau relasi
                messages.error(request, f"Terjadi kesalahan saat menyimpan data: {e}")
                return redirect('register_step', step=1)

    # Render template sesuai step
    template_name = f"register_step{step}.html"
    
    # Data context untuk Progress Bar
    progress = {1: 33, 2: 67, 3: 100}.get(step)
    
    return render(request, template_name, {'form': form, 'step': step, 'progress': progress})


# --- Revisi Login View ---

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # --- PERBAIKAN: Cek Role Berdasarkan Relasi Model ---
            
            # Cek apakah user adalah Dosen (jika memiliki profile Dosen)
            if hasattr(user, 'dosen_profile'): 
                return redirect('dosen_dashboard')
            
            # Cek apakah user adalah Mahasiswa (jika memiliki profile Mahasiswa)
            elif hasattr(user, 'mahasiswa_profile'): 
                return redirect('mahasiswa_dashboard')
            
            # Cek apakah user adalah Superuser/Admin (default Django admin)
            elif user.is_superuser:
                 return redirect('admin_dashboard')
            
            # Jika tidak ada profile yang cocok, log out dan tampilkan error
            else:
                messages.error(request, "Akun tidak memiliki profil yang terdaftar (Mahasiswa/Dosen).")
                return redirect('login_view')

        else:
            messages.error(request, 'Username/Password salah atau akun belum diverifikasi.')
            return render(request, 'login.html')

    return render(request, 'login.html')


# --- Dashboard Views ---
# (Pastikan Anda telah mendefinisikan URL untuk 'dosen_dashboard')

@login_required
def admin_dashboard(request):
    # Logika dashboard admin
    return render(request, 'admin_dashboard.html')

@login_required
def dosen_dashboard(request):
    # Logika dashboard dosen
    return render(request, 'dosen_dashboard.html')

@login_required
def mahasiswa_dashboard(request):
    # Logika dashboard mahasiswa
    return render(request, 'mahasiswa_dashboard.html')