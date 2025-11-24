# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required

from .forms import Step1Form, Step2Form, Step3Form
from .models import (
    Mahasiswa, FotoWajah, Kegiatan_PA, Jenjang_Pendidikan,
    Tahun_Ajaran, Dosen, Mahasiswa_Dosen, Pengajuan_Pendaftaran,
    Status_Pemenuhan_SKS
)
from django.contrib.auth import logout
from django.shortcuts import redirect

def register_wizard(request, step=1):
    # Gunakan Custom User Model
    User = get_user_model()
    
    step1_data = request.session.get('step1_data', {})
    step2_data = request.session.get('step2_data', {})
    form = None

    # ==================== STEP 1: AKUN ====================
    if step == 1:
        form = Step1Form(request.POST or None, initial=step1_data)
        if request.method == 'POST' and form.is_valid():
            request.session['step1_data'] = form.cleaned_data
            request.session.pop('step2_data', None)
            return redirect('register_step', step=2)

    # ==================== STEP 2: AKADEMIK ====================
    elif step == 2:
        if not step1_data:
            return redirect('register_step', step=1)

        initial_data = step2_data.copy()
        if request.method != 'POST':
            if initial_data.get('jenjang'):
                initial_data['jenjang'] = Jenjang_Pendidikan.objects.filter(id=initial_data['jenjang']).first()
            if initial_data.get('semester'):
                initial_data['semester'] = Tahun_Ajaran.objects.filter(id=initial_data['semester']).first()

        form = Step2Form(request.POST or None, initial=initial_data)

        if request.method == 'POST' and form.is_valid():
            data = form.cleaned_data
            save_data = {
                'jenjang': data['jenjang'].id,
                'semester': data['semester'].id,
                'dosen_pembimbing1': data['dosen_pembimbing1'].id,
                'dosen_pembimbing2': data['dosen_pembimbing2'].id,
                'dosen_pembimbing3': data['dosen_pembimbing3'].id if data['dosen_pembimbing3'] else None,
                'kegiatan_pa_diambil': [k.id for k in data['kegiatan_pa_diambil']]
            }
            request.session['step2_data'] = save_data
            return redirect('register_step', step=3)

    # ==================== STEP 3: FOTO & FINALISASI ====================
    elif step == 3:
        if not step1_data or not step2_data:
            messages.warning(request, "Sesi kadaluarsa. Ulangi dari awal.")
            return redirect('register_step', step=1)

        form = Step3Form(request.POST or None, request.FILES or None)

        if request.method == 'POST':
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # 1. BUAT USER (AKUN)
                        nim = step1_data['nim']
                        if User.objects.filter(username=nim).exists():
                            raise Exception(f"NIM {nim} sudah terdaftar!")

                        user = User.objects.create_user(
                            username=nim,
                            email=step1_data['email'],
                            password=step1_data['password'],
                            # Custom fields:
                            nama_lengkap=step1_data['nama_lengkap'],
                            nrp=nim,
                            role='mahasiswa',
                            status_akun='aktif'
                        )

                        # 2. AMBIL DATA FK
                        jenjang = Jenjang_Pendidikan.objects.get(id=step2_data['jenjang'])
                        semester = Tahun_Ajaran.objects.get(id=step2_data['semester'])

                        # 3. BUAT MAHASISWA
                        mhs = Mahasiswa.objects.create(
                            user=user,
                            jenjang_pendidikan=jenjang,
                            semester=semester.nama_semester,
                            kelas=step1_data['kelas'],
                            sks_total_tempuh=0
                        )

                        # 4. SIMPAN DOSEN
                        dosen_ids = [
                            (step2_data['dosen_pembimbing1'], 'pembimbing1'),
                            (step2_data['dosen_pembimbing2'], 'pembimbing2'),
                            (step2_data['dosen_pembimbing3'], 'pembimbing3')
                        ]
                        for d_id, tipe in dosen_ids:
                            if d_id:
                                d_obj = Dosen.objects.get(id=d_id)
                                Mahasiswa_Dosen.objects.create(
                                    mahasiswa=mhs, dosen=d_obj, tipe_pembimbing=tipe
                                )

                        # 5. SIMPAN KEGIATAN PA
                        kp_ids = step2_data.get('kegiatan_pa_diambil', [])
                        if kp_ids:
                            kegiatan_objects = Kegiatan_PA.objects.filter(id__in=kp_ids)
                            mhs.kegiatan_pa.set(kegiatan_objects)
                            for kp in kegiatan_objects:
                                Status_Pemenuhan_SKS.objects.create(
                                    mahasiswa=mhs,
                                    kegiatan_pa=kp,
                                    jam_target=kp.target_jam
                                )

                        # 6. PENGAJUAN & FOTO
                        Pengajuan_Pendaftaran.objects.create(mahasiswa=mhs, status_pengajuan='pending')
                        file_gambar = form.cleaned_data['file_path']
                        FotoWajah.objects.create(mahasiswa=mhs, file_path=file_gambar)

                        # 7. SELESAI
                        request.session.flush()
                        messages.success(request, "Registrasi Berhasil! Silakan Login.")
                        return redirect('login')

                except Exception as e:
                    print(f"ERROR SAVE: {e}")
                    messages.error(request, f"Gagal menyimpan: {str(e)}")
                    return redirect('register_step', step=3)
            else:
                messages.error(request, "Form tidak valid.")

    template_name = f"register_step{step}.html"
    progress = {1: 33, 2: 67, 3: 100}.get(step, 0)
    return render(request, template_name, {'form': form, 'step': step, 'progress': progress})

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get("username")
        p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            # Redirect berdasarkan role
            if getattr(user, 'role', '') == 'mahasiswa': 
                # !!! PERBAIKAN UTAMA DI SINI !!!
                return redirect('profil_mahasiswa')
            elif getattr(user, 'role', '') == 'admin' or user.is_superuser: 
                return redirect('admin_dashboard')
            else: 
                return redirect('login')
        else:
            messages.error(request, 'Login Gagal.')
    return render(request, 'login.html')

def edit_profil(request, nim):
    return render(request, 'mahasiswa/edit_profil.html')

def data_wajah(request):
    return render(request, 'mahasiswa/data_wajah.html')

def riwayat_presensi(request):
    return render(request, 'mahasiswa/riwayat_presensi.html')

def progress_sks(request):
    return render(request, 'mahasiswa/progress_sks.html')

def logout_view(request):
    logout(request) 
    return redirect('login') 

# --- DASHBOARD VIEWS ---
@login_required
def admin_dashboard(request):
    # Asumsi admin_dashboard.html ada di templates/admin/
    return render(request, 'admin/admin_dashboard.html')

@login_required
def profil_mahasiswa(request):
    user = request.user
    try:
        mahasiswa = Mahasiswa.objects.select_related('jenjang_pendidikan', 'user').get(user=user)
        # Inisial dari nama lengkap
        nama_lengkap = user.nama_lengkap or user.get_full_name() or user.username
        inisial = ''.join([x[0] for x in nama_lengkap.split() if x]).upper()[:3]
        nrp = user.nrp or user.username
        email = user.email
        angkatan = mahasiswa.angkatan
        jurusan = mahasiswa.jurusan if mahasiswa.jurusan else ''
        jenjang = mahasiswa.jenjang_pendidikan.nama_jenjang if mahasiswa.jenjang_pendidikan else ''
        semester = mahasiswa.semester
        kelas = mahasiswa.kelas
        # Status PA: ambil dari pengajuan atau status lain jika ada
        try:
            pengajuan = Pengajuan_Pendaftaran.objects.get(mahasiswa=mahasiswa)
            status_pa = pengajuan.get_status_pengajuan_display()
        except Pengajuan_Pendaftaran.DoesNotExist:
            status_pa = 'Belum mengajukan'
        # Mata Kuliah PA: ambil dari kegiatan_pa pertama
        mk_pa = mahasiswa.kegiatan_pa.first().nama_kegiatan if mahasiswa.kegiatan_pa.exists() else '-'
        # Dosen pembimbing urut
        dosen_pembimbing_qs = Mahasiswa_Dosen.objects.filter(mahasiswa=mahasiswa).select_related('dosen').order_by('tipe_pembimbing')
        dosen_pembimbing = []
        for idx, md in enumerate(dosen_pembimbing_qs, 1):
            dosen_pembimbing.append({
                'nomor': idx,
                'nama': md.dosen.nama_dosen,
                'gelar': md.dosen.prodi,
            })
        context = {
            'mahasiswa': {
                'inisial': inisial,
                'nama': nama_lengkap,
                'nrp': nrp,
                'email': email,
                'angkatan': angkatan,
                'jurusan': jurusan,
                'jenjang': jenjang,
                'semester': semester,
                'status_pa': status_pa,
                'mk_pa': mk_pa,
                'user': user,
                'kelas': kelas,
            },
            'dosen_pembimbing': dosen_pembimbing,
        }
    except Mahasiswa.DoesNotExist:
        context = {
            'mahasiswa': None,
            'dosen_pembimbing': [],
        }
    return render(request, 'mahasiswa/profil_mahasiswa.html', context)