# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from datetime import datetime, date, timedelta 
from .forms import Step1Form, Step2Form, Step3Form
from .models import (
    Mahasiswa, FotoWajah, Kegiatan_PA, Jenjang_Pendidikan,
    Tahun_Ajaran, Dosen, Mahasiswa_Dosen, Pengajuan_Pendaftaran,
    Status_Pemenuhan_SKS, Semester, FotoWajah, Mahasiswa_Dosen, Presensi,Durasi
)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import zipfile
import io
import os
import base64
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import Q, Count
from django.contrib.auth import logout
from django.shortcuts import redirect
import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime

def register_wizard(request, step=1):
    # Gunakan Custom User Model
    User = get_user_model()
    
    step1_data = request.session.get('step1_data', {})
    step2_data = request.session.get('step2_data', {})
    form = None

    # ==================== STEP 1: AKUN ====================
    # ==================== STEP 1: AKUN ====================
    if step == 1:
        form = Step1Form(request.POST or None, initial=step1_data)
        if request.method == 'POST' and form.is_valid():
            # Validasi email dan NIM unik
            email = form.cleaned_data.get('email')
            nim = form.cleaned_data.get('nim')
            
            # Cek jika email sudah terdaftar
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'Email sudah terdaftar. Gunakan email lain.')
            # PERBAIKAN DI SINI: Cek jika NIM sudah terdaftar melalui User.nrp
            elif User.objects.filter(nrp=nim).exists():
                form.add_error('nim', 'NIM sudah terdaftar.')
            else:
                # Simpan data ke session
                request.session['step1_data'] = form.cleaned_data
                request.session.pop('step2_data', None)
                return redirect('register_step', step=2)
        
        progress = 33  # 33% untuk step 1
        return render(request, 'mahasiswa/register_step1.html', {
            'form': form, 
            'step': step, 
            'progress': progress
        })
    # ==================== STEP 2: AKADEMIK ====================
    elif step == 2:
        if not step1_data:
            messages.warning(request, 'Silakan lengkapi data identitas terlebih dahulu.')
            return redirect('register_step', step=1)

        # Perbaikan: Konversi ID ke objek untuk form initial
        initial_data = {}
        if step2_data:
            initial_data = {
                'jenjang': Jenjang_Pendidikan.objects.filter(id=step2_data.get('jenjang')).first(),
                'semester': Semester.objects.filter(id=step2_data.get('semester')).first(),
                'dosen_pembimbing1': Dosen.objects.filter(id=step2_data.get('dosen_pembimbing1')).first(),
                'dosen_pembimbing2': Dosen.objects.filter(id=step2_data.get('dosen_pembimbing2')).first(),
                'dosen_pembimbing3': Dosen.objects.filter(id=step2_data.get('dosen_pembimbing3')).first(),
            }
            # Untuk ManyToMany field
            if step2_data.get('kegiatan_pa_diambil'):
                kegiatan_ids = step2_data['kegiatan_pa_diambil']
                initial_data['kegiatan_pa_diambil'] = Kegiatan_PA.objects.filter(id__in=kegiatan_ids)

        form = Step2Form(request.POST or None, initial=initial_data)

        if request.method == 'POST' and form.is_valid():
            data = form.cleaned_data
            save_data = {
                'jenjang': data['jenjang'].id if data['jenjang'] else None,
                'semester': data['semester'].id if data['semester'] else None,
                'dosen_pembimbing1': data['dosen_pembimbing1'].id if data['dosen_pembimbing1'] else None,
                'dosen_pembimbing2': data['dosen_pembimbing2'].id if data['dosen_pembimbing2'] else None,
                'dosen_pembimbing3': data['dosen_pembimbing3'].id if data['dosen_pembimbing3'] else None,
                'kegiatan_pa_diambil': [k.id for k in data['kegiatan_pa_diambil']]
            }
            request.session['step2_data'] = save_data
            return redirect('register_step', step=3)
        
        progress = 67  # 67% untuk step 2
        return render(request, 'mahasiswa/register_step2.html', {
            'form': form, 
            'step': step, 
            'progress': progress
        })

    # ==================== STEP 3: FOTO & FINALISASI ====================
    elif step == 3:
        if not step1_data or not step2_data:
            messages.warning(request, "Sesi kadaluarsa. Ulangi dari awal.")
            return redirect('register_step', step=1)

        form = Step3Form(request.POST or None, request.FILES or None)

        if request.method == 'POST':
            # Debug: print data yang diterima
            print(f"DEBUG: POST data diterima")
            print(f"DEBUG: Files diterima: {request.FILES.getlist('file_path')}")
            
            uploaded_files = request.FILES.getlist('file_path')
            
            # Validasi minimal 10 file
            if len(uploaded_files) < 10:
                messages.error(request, f"Minimal 10 foto wajah diperlukan. Anda hanya mengupload {len(uploaded_files)} foto.")
            else:
                # Validasi setiap file
                valid_files = []
                invalid_files = []
                
                for file in uploaded_files:
                    # Validasi ukuran file (max 5MB) dan tipe file
                    if file.size > 5 * 1024 * 1024:
                        invalid_files.append(f"{file.name} - Ukuran terlalu besar (max 5MB)")
                    elif not file.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                        invalid_files.append(f"{file.name} - Format tidak didukung (harus .jpg, .jpeg, atau .png)")
                    else:
                        valid_files.append(file)

                print(f"DEBUG: Valid files: {len(valid_files)}, Invalid files: {len(invalid_files)}")
                
                if len(valid_files) < 10:
                    messages.error(request, f"Hanya {len(valid_files)} foto yang valid. Minimal 10 foto diperlukan.")
                    if invalid_files:
                        messages.warning(request, "File tidak valid: " + ", ".join(invalid_files[:3]))
                else:
                    try:
                        with transaction.atomic():
                            # 1. BUAT USER (AKUN)
                            nim = step1_data['nim']
                            
                            # Periksa lagi apakah user sudah ada (safety check)
                            User = get_user_model()
                            if User.objects.filter(username=nim).exists():
                                messages.error(request, f"NIM {nim} sudah terdaftar!")
                                return redirect('register_step', step=3)
                            
                            if User.objects.filter(email=step1_data['email']).exists():
                                messages.error(request, f"Email {step1_data['email']} sudah terdaftar!")
                                return redirect('register_step', step=3)
                            
                            user = User.objects.create_user(
                                username=nim,
                                email=step1_data['email'],
                                password=step1_data['password'],
                                nama_lengkap=step1_data['nama_lengkap'],
                                nrp=nim,
                                role='mahasiswa',
                                status_akun='pending',
                                is_active=False  # Nonaktif sampai admin approve
                            )
                            print(f"DEBUG: User created: {user.username}")

                            # 2. AMBIL DATA FK
                            jenjang = Jenjang_Pendidikan.objects.get(id=step2_data['jenjang'])
                            semester = Semester.objects.get(id=step2_data['semester'])

                            # 3. BUAT MAHASISWA
                            mhs = Mahasiswa.objects.create(
                                user=user,
                                nim=nim,
                                jenjang_pendidikan=jenjang,
                                semester=semester,
                                kelas=step1_data['kelas'],
                                angkatan=step1_data['angkatan'],
                                jurusan=step1_data.get('jurusan', ''),
                                sks_total_tempuh=0
                            )
                            print(f"DEBUG: Mahasiswa created: {mhs.nim}")

                            # 4. SIMPAN DOSEN PEMBIMBING
                            dosen_ids = [
                                (step2_data['dosen_pembimbing1'], 'pembimbing1'),
                                (step2_data['dosen_pembimbing2'], 'pembimbing2'),
                                (step2_data['dosen_pembimbing3'], 'pembimbing3') if step2_data.get('dosen_pembimbing3') else None
                            ]
                            
                            for d_data in dosen_ids:
                                if d_data and d_data[0]:  # Jika ada data dan id dosen tidak None
                                    d_id, tipe = d_data
                                    try:
                                        d_obj = Dosen.objects.get(id=d_id)
                                        Mahasiswa_Dosen.objects.create(
                                            mahasiswa=mhs, 
                                            dosen=d_obj, 
                                            tipe_pembimbing=tipe
                                        )
                                        print(f"DEBUG: Dosen {tipe} added: {d_obj.nama_dosen}")
                                    except Dosen.DoesNotExist:
                                        print(f"WARNING: Dosen dengan id {d_id} tidak ditemukan")

                            # 5. SIMPAN KEGIATAN PA
                            kp_ids = step2_data.get('kegiatan_pa_diambil', [])
                            if kp_ids:
                                try:
                                    kegiatan_objects = Kegiatan_PA.objects.filter(id__in=kp_ids)
                                    mhs.kegiatan_pa.set(kegiatan_objects)
                                    print(f"DEBUG: {kegiatan_objects.count()} kegiatan PA ditambahkan")
                                    
                                    for kp in kegiatan_objects:
                                        Status_Pemenuhan_SKS.objects.create(
                                            mahasiswa=mhs,
                                            kegiatan_pa=kp,
                                            jam_target=kp.target_jam,
                                            jumlah_sks=kp.jumlah_sks
                                        )
                                except Exception as e:
                                    print(f"ERROR creating kegiatan PA: {e}")

                            # 6. BUAT PENGAJUAN PENDAFTARAN
                            Pengajuan_Pendaftaran.objects.create(
                                mahasiswa=mhs, 
                                status_pengajuan='pending'
                            )
                            print(f"DEBUG: Pengajuan pendaftaran created")

                            # 7. SIMPAN SEMUA FOTO
                            foto_count = 0
                            for i, file_gambar in enumerate(valid_files):
                                FotoWajah.objects.create(
                                    mahasiswa=mhs,
                                    file_path=file_gambar,
                                    keterangan=f"Foto registrasi ke-{i+1}"
                                )
                                foto_count += 1
                            
                            print(f"DEBUG: {foto_count} foto berhasil disimpan")

                            # 8. SIMPAN EMAIL UNTUK HALAMAN PERSETUJUAN
                            request.session['registrasi_email'] = step1_data['email']
                            request.session['registrasi_nama'] = step1_data['nama_lengkap']
                            
                            # 9. HAPUS SESSION DATA REGISTRASI
                            request.session.pop('step1_data', None)
                            request.session.pop('step2_data', None)
                            
                            # 10. TAMPILKAN SUKSES DAN REDIRECT
                            messages.success(request, "Pendaftaran berhasil! Data Anda sedang menunggu persetujuan admin.")
                            return redirect('registrasi_complete')

                    except Exception as e:
                        print(f"ERROR SAVE: {e}")
                        import traceback
                        traceback.print_exc()  # Print traceback untuk debugging
                        messages.error(request, f"Gagal menyimpan: {str(e)}")

        progress = 100 
        
        return render(request, 'mahasiswa/register_step3.html', {
            'form': form, 
            'step': step, 
            'progress': progress, 
            'uploaded_files': []
        })

def login_view(request):
    if request.method == 'POST':
        u = request.POST.get("username")
        p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            # Cek jika status akun masih pending
            if getattr(user, 'status_akun', '') == 'pending':
                messages.warning(request, 'Akun Anda masih menunggu verifikasi admin.')
                return redirect('login')
            
            login(request, user)
            # Redirect berdasarkan role
            if getattr(user, 'role', '') == 'mahasiswa': 
                return redirect('profil_mahasiswa')
            elif getattr(user, 'role', '') == 'admin' or user.is_superuser: 
                # PERBAIKAN DI SINI: Redirect ke admin_dashboard bukan kamera_presensi_mhs
                return redirect('admin_dashboard')
            else: 
                return redirect('login')
        else:
            messages.error(request, 'Login Gagal. Cek kembali username dan password.')
    
    return render(request, 'login.html')
    if request.method == 'POST':        
        u = request.POST.get("username")    
        p = request.POST.get("password")    
        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            # Cek jika status akun masih pending
            if getattr(user, 'status_akun', '') == 'pending':
                messages.warning(request, 'Akun Anda masih menunggu verifikasi admin.')
                return redirect('login')
            
            login(request, user)
            # Redirect berdasarkan role
            if getattr(user, 'role', '') == 'mahasiswa': 
                return redirect('profil_mahasiswa')
            elif getattr(user, 'role', '') == 'admin' or user.is_superuser: 
                return redirect('kamera_presensi_mhs')
            else: 
                return redirect('login')
        else:
            messages.error(request, 'Login Gagal. Cek kembali username dan password.')
    
    return render(request, 'login.html')    

def registrasi_complete(request):
    """Halaman konfirmasi setelah registrasi selesai"""
    # Ambil email dari session
    email = request.session.get('registrasi_email', 'email.anda@domain.com')

    # Optional: Hapus session data setelah ditampilkan
    # request.session.pop('registrasi_email', None)

    return render(request, 'mahasiswa/persetujuandaftar.html', {'user_email': email})

# GANTI fungsi edit_profil di views.py dengan ini:
@login_required
def edit_profil(request, nim):
    if request.method == 'POST':
        try:
            # Validasi bahwa NIM sesuai dengan user yang login
            if str(request.user.nrp) != str(nim) and request.user.role != 'admin':
                return JsonResponse({'success': False, 'error': 'Unauthorized'})
            
            user = request.user
            mahasiswa = Mahasiswa.objects.get(user=user)
            
            # Update user data
            user.nama_lengkap = request.POST.get('nama')
            user.email = request.POST.get('email')
            
            # Update password jika diisi
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            
            if password and confirm_password:
                if password == confirm_password:
                    user.set_password(password)
                else:
                    return JsonResponse({'success': False, 'error': 'Password tidak sama'})
            
            user.save()
            
            # Update mahasiswa data
            mahasiswa.kelas = request.POST.get('kelas')
            mahasiswa.angkatan = request.POST.get('angkatan') 
            
            # PERBAIKAN 1: Update semester dengan benar (cari instance Semester)
            semester_id = request.POST.get('semester')
            if semester_id:
                try:
                    semester_obj = Semester.objects.get(id=semester_id)
                    mahasiswa.semester = semester_obj  # Assign instance, bukan string
                except Semester.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Semester tidak valid'})
            
            # Update jenjang jika diubah
            jenjang_id = request.POST.get('jenjang')
            if jenjang_id:
                try:
                    jenjang = Jenjang_Pendidikan.objects.get(id=jenjang_id)
                    mahasiswa.jenjang_pendidikan = jenjang
                except Jenjang_Pendidikan.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Jenjang tidak valid'})
            
            mahasiswa.save()
            
            # Update kegiatan PA (jika ada)
            kegiatan_pa_selected = request.POST.get('kegiatan_pa_selected')
            if kegiatan_pa_selected:
                try:
                    kegiatan_ids = json.loads(kegiatan_pa_selected)
                    kegiatan_objects = Kegiatan_PA.objects.filter(id__in=kegiatan_ids)
                    mahasiswa.kegiatan_pa.set(kegiatan_objects)
                    
                    # Update atau buat Status_Pemenuhan_SKS untuk setiap kegiatan
                    for kegiatan in kegiatan_objects:
                        Status_Pemenuhan_SKS.objects.update_or_create(
                            mahasiswa=mahasiswa,
                            kegiatan_pa=kegiatan,
                            defaults={
                                'jam_target': kegiatan.target_jam,
                                'jumlah_sks': kegiatan.jumlah_sks
                            }
                        )
                except json.JSONDecodeError:
                    pass
            
            return JsonResponse({'success': True, 'message': 'Profil berhasil diperbarui'})
            
        except Exception as e:
            print(f"Error saving profile: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    # Jika GET request, tetap render template
    return render(request, 'mahasiswa/edit_profil.html')

@login_required
def data_wajah(request):
    try:
        mahasiswa = Mahasiswa.objects.get(user=request.user)
        foto_wajah_list = FotoWajah.objects.filter(mahasiswa=mahasiswa)
        foto_count = foto_wajah_list.count()
        
        context = {
            'foto_wajah_list': foto_wajah_list,
            'foto_count': foto_count,
        }
        return render(request, 'mahasiswa/data_wajah.html', context)
    except Mahasiswa.DoesNotExist:
        messages.error(request, 'Data mahasiswa tidak ditemukan')
        return redirect('profil_mahasiswa')
    
@login_required
def hapus_foto_wajah(request, foto_id):
    if request.method == 'DELETE':
        try:
            user = request.user
            mahasiswa = Mahasiswa.objects.get(user=user)
            foto = FotoWajah.objects.get(id=foto_id, mahasiswa=mahasiswa)
            foto.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Foto berhasil dihapus'
            })
        except FotoWajah.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Foto tidak ditemukan'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def hapus_semua_foto(request):
    if request.method == 'POST':
        try:
            user = request.user
            mahasiswa = Mahasiswa.objects.get(user=user)
            foto_count = FotoWajah.objects.filter(mahasiswa=mahasiswa).count()
            FotoWajah.objects.filter(mahasiswa=mahasiswa).delete()
            
            return JsonResponse({
                'success': True,
                'message': f'{foto_count} foto berhasil dihapus'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def riwayat_presensi(request):
    return render(request, 'mahasiswa/riwayat_presensi.html')

def progress_sks(request):
    return render(request, 'mahasiswa/progress_sks.html')

def logout_view(request):
    logout(request) 
    return redirect('login') 

# --- DASHBOARD VIEWS ---
@login_required
def kamera_presensi_mhs(request):
    """View untuk kamera presensi mahasiswa - hanya tampilkan yang sudah di-approve"""
    today = date.today()
    
    # Filter hanya mahasiswa yang status pengajuannya DISETUJUI
    mahasiswa_list = Mahasiswa.objects.select_related(
        'user',
        'jenjang_pendidikan',
        'semester'
    ).filter(
        user__status_akun='aktif',  # hanya yang aktif
        pengajuan_pendaftaran__status_pengajuan='disetujui'  # hanya yang sudah di-approve
    ).order_by('user__nama_lengkap')
    
    # Debug: Cetak jumlah mahasiswa ke console
    print(f"DEBUG [Kamera Presensi]: Jumlah mahasiswa (approved): {mahasiswa_list.count()}")
    
    presensi_data = []
    for mahasiswa in mahasiswa_list:
        # Cari presensi hari ini
        presensi_today = Presensi.objects.filter(
            mahasiswa=mahasiswa,
            tanggal_presensi=today
        ).order_by('-jam_checkin')
        
        latest_presensi = None
        is_checked_in = False
        
        if presensi_today.exists():
            latest_presensi = presensi_today.first()
            # Cek apakah ada yang belum check-out
            pending_checkout = presensi_today.filter(
                jam_checkin__isnull=False,
                jam_checkout__isnull=True
            ).exists()
            is_checked_in = pending_checkout
        
        presensi_data.append({
            'mahasiswa': mahasiswa,
            'presensi': latest_presensi,
            'is_checked_in': is_checked_in,
            'all_presensi_today': presensi_today
        })
    
    context = {
        'presensi_data': presensi_data,
        'today': today,
        'total_mahasiswa': mahasiswa_list.count()
    }
    
    return render(request, 'admin/kamera_presensi_mhs.html', context)

# Tambahkan fungsi-fungsi ini di accounts/views.py

@csrf_exempt
@login_required
def checkin_presensi(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mahasiswa_id = data.get('mahasiswa_id')
            foto_base64 = data.get('foto')
            
            # Decode base64 image
            format, imgstr = foto_base64.split(';base64,')
            ext = format.split('/')[-1]
            
            # Buat nama file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'checkin_{mahasiswa_id}_{timestamp}.{ext}'
            
            # Simpan foto check-in
            foto_data = ContentFile(base64.b64decode(imgstr), name=filename)
            
            # Get mahasiswa
            mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
            
            # Cek apakah sudah ada presensi hari ini yang belum check-out
            existing_presensi = Presensi.objects.filter(
                mahasiswa=mahasiswa,
                tanggal_presensi=date.today(),
                jam_checkout__isnull=True
            ).first()
            
            if existing_presensi:
                return JsonResponse({
                    'success': False,
                    'message': 'Mahasiswa belum check-out dari sesi sebelumnya'
                })
            
            # Ambil kegiatan PA pertama (bisa disesuaikan dengan kebutuhan)
            kegiatan_pa = Kegiatan_PA.objects.first()
            if not kegiatan_pa:
                return JsonResponse({
                    'success': False,
                    'message': 'Tidak ada kegiatan PA yang tersedia'
                })
            
            # Buat presensi baru
            presensi = Presensi.objects.create(
                mahasiswa=mahasiswa,
                kegiatan_pa=kegiatan_pa,
                tanggal_presensi=date.today(),
                jam_checkin=datetime.now().time(),
                foto_checkin=foto_data
            )
            
            # Simpan juga ke FotoWajah untuk dataset
            FotoWajah.objects.create(
                mahasiswa=mahasiswa,
                file_path=foto_data,
                keterangan=f'Check-in {datetime.now().strftime("%d/%m/%Y %H:%M")}'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Check-in berhasil',
                'data': {
                    'presensi_id': presensi.id,
                    'jam_checkin': presensi.jam_checkin.strftime('%H:%M')
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Method not allowed'})

@csrf_exempt
@login_required
def checkout_presensi(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mahasiswa_id = data.get('mahasiswa_id')
            foto_base64 = data.get('foto')
            
            # Decode base64 image
            if foto_base64:
                format, imgstr = foto_base64.split(';base64,')
                ext = format.split('/')[-1]
                
                # Buat nama file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f'checkout_{mahasiswa_id}_{timestamp}.{ext}'
                
                # Simpan foto check-out
                foto_data = ContentFile(base64.b64decode(imgstr), name=filename)
            
            # Get mahasiswa
            mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
            
            # Cari presensi hari ini yang belum check-out
            presensi = Presensi.objects.filter(
                mahasiswa=mahasiswa,
                tanggal_presensi=date.today(),
                jam_checkout__isnull=True
            ).order_by('-jam_checkin').first()
            
            if not presensi:
                return JsonResponse({
                    'success': False,
                    'message': 'Tidak ada sesi check-in yang aktif'
                })
            
            # Update presensi dengan check-out
            presensi.jam_checkout = datetime.now().time()
            
            # Simpan foto jika ada
            if foto_base64:
                presensi.foto_checkout = foto_data
                
            presensi.save()
            
            # Hitung durasi
            if presensi.jam_checkin and presensi.jam_checkout:
                checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
                checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
                durasi = checkout_dt - checkin_dt
                
                # Simpan durasi
                Durasi.objects.create(
                    presensi=presensi,
                    waktu_durasi=durasi
                )
                
                # Update status pemenuhan SKS
                status_sks, created = Status_Pemenuhan_SKS.objects.get_or_create(
                    mahasiswa=mahasiswa,
                    kegiatan_pa=presensi.kegiatan_pa
                )
                
                # Tambahkan jam yang dicapai
                jam_tercapai = durasi.seconds // 3600  # Konversi detik ke jam
                status_sks.jam_tercapai += jam_tercapai
                
                # Cek apakah sudah memenuhi target
                if status_sks.jam_tercapai >= status_sks.jam_target:
                    status_sks.status_pemenuhan = 'memenuhi'
                
                status_sks.save()
            
            # Simpan juga ke FotoWajah untuk dataset
            if foto_base64:
                FotoWajah.objects.create(
                    mahasiswa=mahasiswa,
                    file_path=foto_data,
                    keterangan=f'Check-out {datetime.now().strftime("%d/%m/%Y %H:%M")}'
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Check-out berhasil',
                'data': {
                    'jam_checkout': presensi.jam_checkout.strftime('%H:%M'),
                    'presensi_id': presensi.id
                }
            })
            
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}',
                'trace': traceback.format_exc()
            })
    
    return JsonResponse({'success': False, 'message': 'Method not allowed'})

@login_required
def get_presensi_today(request):
    """API untuk mendapatkan data presensi hari ini"""
    today = date.today()
    mahasiswa_list = Mahasiswa.objects.select_related('user').all()
    
    presensi_list = []
    for mahasiswa in mahasiswa_list:
        presensi_today = Presensi.objects.filter(
            mahasiswa=mahasiswa,
            tanggal_presensi=today
        ).order_by('-jam_checkin')
        
        presensi_data = []
        for presensi in presensi_today:
            presensi_data.append({
                'jam_checkin': presensi.jam_checkin.strftime('%H:%M') if presensi.jam_checkin else '-',
                'jam_checkout': presensi.jam_checkout.strftime('%H:%M') if presensi.jam_checkout else '-',
                'foto_checkin_url': presensi.foto_checkin.url if presensi.foto_checkin else '',
                'foto_checkout_url': presensi.foto_checkout.url if presensi.foto_checkout else ''
            })
        
        # Status check-in aktif
        is_checked_in = any(p.jam_checkin is not None and p.jam_checkout is None for p in presensi_today)
        
        presensi_list.append({
            'id': mahasiswa.id,
            'nama': mahasiswa.user.nama_lengkap or mahasiswa.user.username,
            'nrp': mahasiswa.user.nrp,
            'kelas': mahasiswa.kelas,
            'is_checked_in': is_checked_in,
            'presensi_today': presensi_data
        })
    
    return JsonResponse({
        'success': True,
        'data': presensi_list,
        'today': today.strftime('%d/%m/%Y')
    })

# accounts/views.py - Tambahkan di akhir file
@login_required
def profil_mahasiswa(request):
    user = request.user
    try:
        mahasiswa = Mahasiswa.objects.select_related(
            'jenjang_pendidikan', 
            'user',
            'semester'
        ).prefetch_related('kegiatan_pa').get(user=user)
        
        nama_lengkap = user.nama_lengkap or user.get_full_name() or user.username
        nrp = user.nrp or user.username
        
        # Debug: Cek kegiatan PA yang sudah dipilih
        kegiatan_pa_selected = list(mahasiswa.kegiatan_pa.all())
        print(f"Kegiatan PA untuk {nama_lengkap}: {[k.id for k in kegiatan_pa_selected]}")
        
        # PERBAIKAN 2: Kirim kegiatan_ids_json ke template
        import json
        kegiatan_ids = [k.id for k in kegiatan_pa_selected]
        
        # Get dosen pembimbing
        dosen_pembimbing_qs = Mahasiswa_Dosen.objects.filter(
            mahasiswa=mahasiswa
        ).select_related('dosen').order_by('tipe_pembimbing')
        
        dosen_pembimbing = []
        for idx, md in enumerate(dosen_pembimbing_qs, 1):
            dosen_pembimbing.append({
                'nomor': idx,
                'dosen': md.dosen,
                'nama_dosen': md.dosen.nama_dosen,
                'nip': md.dosen.nip,
                'prodi': md.dosen.prodi,
            })
        
        # Get all data for dropdowns
        dosen_list = Dosen.objects.all().order_by('nama_dosen')
        jenjang_list = Jenjang_Pendidikan.objects.all()
        
        # PERBAIKAN 3: Kirim semester_list, bukan semester_range
        semester_list = Semester.objects.all()
        
        context = {
            'mahasiswa': {
                'nama': nama_lengkap,
                'nrp': nrp,
                'email': user.email,
                'jenjang': mahasiswa.jenjang_pendidikan.nama_jenjang if mahasiswa.jenjang_pendidikan else '',
                'jenjang_pendidikan': mahasiswa.jenjang_pendidikan,
                'kelas': mahasiswa.kelas,
                'semester': mahasiswa.semester.nama_semester if mahasiswa.semester else '',
                'semester_id': mahasiswa.semester.id if mahasiswa.semester else '',  # ID semester
                'angkatan': mahasiswa.angkatan,
                'kegiatan_pa': kegiatan_pa_selected,
            },
            'dosen_pembimbing': dosen_pembimbing,
            'dosen_list': dosen_list,
            'jenjang_list': jenjang_list,
            'semester_list': semester_list,  # Kirim list semester
            'kegiatan_ids_json': json.dumps(kegiatan_ids),  # Kirim JSON
        }
        
    except Mahasiswa.DoesNotExist as e:
        print(f"Error: Mahasiswa not found for user {user.username}: {e}")
        context = {
            'mahasiswa': None,
            'dosen_pembimbing': [],
            'dosen_list': [],
            'jenjang_list': [],
            'semester_list': [],
            'kegiatan_ids_json': '[]',
        }
        
    return render(request, 'mahasiswa/profil_mahasiswa.html', context)

@login_required
def edit_dosen_pembimbing(request):
    if request.method == 'POST':
        try:
            user = request.user
            mahasiswa = Mahasiswa.objects.get(user=user)
            
            # Validasi dosen pembimbing
            dosen1_id = request.POST.get('dosen_pembimbing1')
            dosen2_id = request.POST.get('dosen_pembimbing2')
            dosen3_id = request.POST.get('dosen_pembimbing3')
            
            # Validasi required fields
            if not dosen1_id or not dosen2_id:
                return JsonResponse({'success': False, 'error': 'Dosen pembimbing 1 dan 2 wajib diisi'})
            
            # Validasi dosen tidak sama
            if dosen1_id == dosen2_id:
                return JsonResponse({'success': False, 'error': 'Dosen pembimbing 1 dan 2 tidak boleh sama'})
            
            if dosen3_id and (dosen3_id == dosen1_id or dosen3_id == dosen2_id):
                return JsonResponse({'success': False, 'error': 'Dosen pembimbing 3 tidak boleh sama dengan dosen lainnya'})
            
            # Delete existing dosen pembimbing
            Mahasiswa_Dosen.objects.filter(mahasiswa=mahasiswa).delete()
            
            # Add new dosen pembimbing
            dosen1 = Dosen.objects.get(id=dosen1_id)
            Mahasiswa_Dosen.objects.create(
                mahasiswa=mahasiswa, 
                dosen=dosen1, 
                tipe_pembimbing='pembimbing1'
            )
            
            dosen2 = Dosen.objects.get(id=dosen2_id)
            Mahasiswa_Dosen.objects.create(
                mahasiswa=mahasiswa, 
                dosen=dosen2, 
                tipe_pembimbing='pembimbing2'
            )
            
            if dosen3_id:
                dosen3 = Dosen.objects.get(id=dosen3_id)
                Mahasiswa_Dosen.objects.create(
                    mahasiswa=mahasiswa, 
                    dosen=dosen3, 
                    tipe_pembimbing='pembimbing3'
                )
            
            return JsonResponse({'success': True, 'message': 'Dosen pembimbing berhasil diperbarui'})
            
        except Dosen.DoesNotExist as e:
            return JsonResponse({'success': False, 'error': f'Dosen tidak ditemukan: {str(e)}'})
        except Exception as e:
            print(f"Error saving dosen: {e}")  # Untuk debugging
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def get_kegiatan_pa_by_jenjang(request, jenjang_id):
    """API untuk mendapatkan kegiatan PA berdasarkan jenjang"""
    try:
        kegiatan = Kegiatan_PA.objects.filter(jenjang_pendidikan_id=jenjang_id)
        kegiatan_list = list(kegiatan.values('id', 'nama_kegiatan', 'jumlah_sks', 'target_jam'))
        return JsonResponse({
            'success': True,
            'kegiatan': kegiatan_list
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
def upload_foto_wajah(request):
    if request.method == 'POST' and request.FILES.get('foto_wajah'):
        try:
            user = request.user
            mahasiswa = Mahasiswa.objects.get(user=user)
            
            foto = request.FILES['foto_wajah']
            keterangan = request.POST.get('keterangan', '')
            
            # Simpan foto
            foto_wajah = FotoWajah.objects.create(
                mahasiswa=mahasiswa,
                file_path=foto,
                keterangan=keterangan
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Foto berhasil diupload',
                'foto_id': foto_wajah.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def riwayat_presensi(request):
    # Data dummy untuk contoh
    # Ganti dengan data dari database Anda
    mahasiswa = {
        'nrp': '2141720001',
        'nama': 'Ahmad Rizki Pratama',
        'kelas': 'D3 IT A',
        'jenjang': 'D3'
    }
    
    # Data presensi dummy
    presensi_list = [
        {
            'mahasiswa': mahasiswa,
            'tanggal': datetime(2025, 9, 24),
            'check_in': datetime(2025, 9, 24, 11, 10),
            'check_out': datetime(2025, 9, 24, 16, 12),
            'durasi': '5h 2m',
            'status': 'Hadir'
        },
        {
            'mahasiswa': mahasiswa,
            'tanggal': datetime(2025, 9, 24),
            'check_in': datetime(2025, 9, 24, 10, 32),
            'check_out': datetime(2025, 9, 24, 17, 41),
            'durasi': '7h 9m',
            'status': 'Hadir'
        },
        {
            'mahasiswa': mahasiswa,
            'tanggal': datetime(2025, 9, 24),
            'check_in': datetime(2025, 9, 24, 10, 20),
            'check_out': datetime(2025, 9, 24, 17, 30),
            'durasi': '7h 10m',
            'status': 'Hadir'
        }
    ]
    
    # Statistik
    statistik = {
        'hadir': 3,
        'terlambat': 0,
        'izin': 0,
        'alpha': 0
    }
    
    context = {
        'presensi_list': presensi_list,
        'total_sks': 12,
        'semester_nama': 'Semester Ganjil 2024/2025',
        'statistik': statistik
    }
    
    return render(request, 'mahasiswa/riwayat_presensi.html', context)

# Di views.py
# views.py
from django.shortcuts import render

def progress_sks(request):
    context = {
        'sks': 12,
        'jam_terselesaikan': 234,
        'jam_target_total': 344,
        'jam_sisa': 110,
        'progress_percentage': 68,
        'rata_per_minggu': 15.6,
        'estimasi_selesai': '25 Desember 2024',
        'sisa_waktu': 45,
        'rekomendasi_per_hari': 2.44,
    }
    return render(request, 'mahasiswa/progress_sks.html', context)


# --- ADMIN VIEWS ---

@login_required
def admin_dashboard(request):
    """View untuk dashboard admin"""
    # Periksa apakah user adalah admin
    if not (request.user.role == 'admin' or request.user.is_superuser):
        messages.error(request, 'Akses ditolak. Halaman untuk admin saja.')
        return redirect('login')
    
    # Anda bisa menambahkan data statistik atau informasi lain di sini
    context = {
        'title': 'Dashboard Admin',
        'user': request.user,
        # Tambahkan data lain yang diperlukan untuk dashboard
    }
    return render(request, 'admin/admin_dashboard.html', context)

@login_required
def monitoring_presensi(request):
    """View untuk monitoring presensi admin"""
    return render(request, 'admin/kamera_presensi_mhs.html')

@login_required
def monitor_durasi(request):
    """View untuk monitor durasi presensi admin"""
    return render(request, 'admin/monitor_durasi.html')

@login_required
def management_data(request):
    """View untuk management data admin"""
    return render(request, 'admin/management_data.html')


@login_required
def approval_pendaftaran(request):
    """View untuk approval pendaftaran admin"""
    
    search_query = request.GET.get('search', '').strip()
    
    # SEKARANG SUDAH BISA PAKAI created_at
    pendaftaran_list = Pengajuan_Pendaftaran.objects.select_related(
        'mahasiswa__user', 
        'mahasiswa__jenjang_pendidikan',
        'mahasiswa__semester'
    ).all().order_by('-created_at')  # GUNAKAN -created_at
    
    # Filter berdasarkan search
    if search_query:
        pendaftaran_list = pendaftaran_list.filter(
            Q(mahasiswa__user__nama_lengkap__icontains=search_query) |
            Q(mahasiswa__user__nrp__icontains=search_query) |
            Q(mahasiswa__user__email__icontains=search_query)
        )
    
    # Urutkan berdasarkan status (pending dulu) lalu created_at
    from django.db.models import Case, When, Value, IntegerField
    pendaftaran_list = pendaftaran_list.annotate(
        status_order=Case(
            When(status_pengajuan='pending', then=Value(1)),
            When(status_pengajuan='disetujui', then=Value(2)),
            When(status_pengajuan='ditolak', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('status_order', '-created_at')
    
    # Hitung statistik
    total_pendaftaran = pendaftaran_list.count()
    menunggu_approval = pendaftaran_list.filter(status_pengajuan='pending').count()
    disetujui = pendaftaran_list.filter(status_pengajuan='disetujui').count()
    ditolak = pendaftaran_list.filter(status_pengajuan='ditolak').count()
    
    # Handle download request
    if 'download' in request.GET:
        mahasiswa_id = request.GET.get('download')
        return download_foto_wajah(request, mahasiswa_id)
    
    # Jika request AJAX untuk mengambil detail
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        action = request.GET.get('action', '')
        
        if action == 'detail':
            mahasiswa_id = request.GET.get('mahasiswa_id')
            return get_detail_pendaftaran(request, mahasiswa_id)
        
        elif action == 'approve_modal':
            pengajuan_id = request.GET.get('pengajuan_id')
            return get_approve_modal(request, pengajuan_id)
        
        elif action == 'reject_modal':
            pengajuan_id = request.GET.get('pengajuan_id')
            return get_reject_modal(request, pengajuan_id)
    
    # Jika POST untuk update status
    if request.method == 'POST':
        return update_status_pendaftaran(request)
    
    # GET request biasa - tampilkan halaman utama
    context = {
        'pendaftaran_list': pendaftaran_list,
        'total_pendaftaran': total_pendaftaran,
        'menunggu_approval': menunggu_approval,
        'disetujui': disetujui,
        'ditolak': ditolak,
        'search_query': search_query,
    }
    
    return render(request, 'admin/approval_pendaftaran.html', context)

def get_detail_pendaftaran(request, mahasiswa_id):
    """Ambil data detail pendaftaran untuk modal"""
    mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
    
    # Ambil SEMUA foto wajah (tidak dibatasi 5)
    foto_wajah = FotoWajah.objects.filter(mahasiswa=mahasiswa).order_by('-created_at')
    
    # Ambil semua dosen pembimbing (Pembimbing 1, 2, 3)
    dosen_pembimbing_list = Mahasiswa_Dosen.objects.filter(
        mahasiswa=mahasiswa
    ).select_related('dosen').order_by('tipe_pembimbing')
    
    # Ambil kegiatan PA
    kegiatan_pa_list = mahasiswa.kegiatan_pa.all()
    
    context = {
        'mahasiswa': mahasiswa,
        'foto_wajah': foto_wajah,
        'dosen_pembimbing_list': dosen_pembimbing_list,
        'kegiatan_pa_list': kegiatan_pa_list,
    }
    
    return render(request, 'admin/partials/detail_pendaftaran_content.html', context)

def get_approve_modal(request, pengajuan_id):
    """Ambil konten modal approve"""
    pengajuan = get_object_or_404(Pengajuan_Pendaftaran, id=pengajuan_id)
    
    context = {
        'pengajuan': pengajuan,
    }
    
    return render(request, 'admin/partials/approve_modal_content.html', context)

def get_reject_modal(request, pengajuan_id):
    """Ambil konten modal reject"""
    pengajuan = get_object_or_404(Pengajuan_Pendaftaran, id=pengajuan_id)
    
    context = {
        'pengajuan': pengajuan,
    }
    
    return render(request, 'admin/partials/reject_modal_content.html', context)

def update_status_pendaftaran(request):
    """Update status pendaftaran (approve/reject)"""
    pengajuan_id = request.POST.get('pengajuan_id')
    action = request.POST.get('action')
    alasan_penolakan = request.POST.get('alasan_penolakan', '')
    
    pengajuan = get_object_or_404(Pengajuan_Pendaftaran, id=pengajuan_id)
    
    with transaction.atomic():
        if action == 'approve':
            pengajuan.status_pengajuan = 'disetujui'
            pengajuan.alasan_penolakan = ''
            
            # Aktifkan akun mahasiswa
            mahasiswa = pengajuan.mahasiswa
            user = mahasiswa.user
            user.is_active = True
            user.save()
            
            messages.success(request, f'Pendaftaran {user.nama_lengkap} berhasil disetujui.')
            
        elif action == 'reject':
            if not alasan_penolakan:
                return JsonResponse({
                    'success': False,
                    'message': 'Alasan penolakan harus diisi'
                })
            
            pengajuan.status_pengajuan = 'ditolak'
            pengajuan.alasan_penolakan = alasan_penolakan
            
            # Nonaktifkan akun mahasiswa
            mahasiswa = pengajuan.mahasiswa
            user = mahasiswa.user
            user.is_active = False
            user.save()
            
            messages.warning(request, f'Pendaftaran {user.nama_lengkap} ditolak.')
        
        pengajuan.save()  
    
    return JsonResponse({
        'success': True,
        'message': 'Status pendaftaran berhasil diperbarui'
    })
    """Update status pendaftaran (approve/reject)"""
    pengajuan_id = request.POST.get('pengajuan_id')
    action = request.POST.get('action')
    alasan_penolakan = request.POST.get('alasan_penolakan', '')
    
    pengajuan = get_object_or_404(Pengajuan_Pendaftaran, id=pengajuan_id)
    
    with transaction.atomic():
        if action == 'approve':
            pengajuan.status_pengajuan = 'disetujui'
            pengajuan.alasan_penolakan = ''
            
            # Aktifkan akun mahasiswa
            mahasiswa = pengajuan.mahasiswa
            user = mahasiswa.user
            user.is_active = True
            user.save()
            
            messages.success(request, f'Pendaftaran {user.nama_lengkap} berhasil disetujui.')
            
        elif action == 'reject':
            if not alasan_penolakan:
                return JsonResponse({
                    'success': False,
                    'message': 'Alasan penolakan harus diisi'
                })
            
            pengajuan.status_pengajuan = 'ditolak'
            pengajuan.alasan_penolakan = alasan_penolakan
            
            # Nonaktifkan akun mahasiswa
            mahasiswa = pengajuan.mahasiswa
            user = mahasiswa.user
            user.is_active = False
            user.save()
            
            messages.warning(request, f'Pendaftaran {user.nama_lengkap} ditolak.')
        
        pengajuan.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Status pendaftaran berhasil diperbarui'
    })

def download_foto_wajah(request, mahasiswa_id):
    """Download semua foto wajah mahasiswa dalam format zip"""
    import zipfile
    import io
    import os
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    
    mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
    foto_wajah_list = FotoWajah.objects.filter(mahasiswa=mahasiswa)
    
    if not foto_wajah_list:
        return HttpResponse(
            '<script>alert("Tidak ada foto wajah untuk didownload"); window.history.back();</script>',
            content_type='text/html'
        )
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for foto in foto_wajah_list:
                if foto.file_path and hasattr(foto.file_path, 'path'):
                    file_path = foto.file_path.path
                    if os.path.exists(file_path):
                        file_name = f"{mahasiswa.user.nrp}_{mahasiswa.user.nama_lengkap}_{os.path.basename(file_path)}"
                        zip_file.write(file_path, file_name)
        
        zip_buffer.seek(0)
        
        # Create response
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="foto_wajah_{mahasiswa.user.nrp}_{mahasiswa.user.nama_lengkap.replace(" ", "_")}.zip"'
        
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(
            f'<script>alert("Gagal membuat file zip. Pastikan file foto tersedia."); window.history.back();</script>',
            content_type='text/html'
        )

def render_approval_page(request):
    """Render halaman utama approval"""
    pendaftaran_list = Pengajuan_Pendaftaran.objects.select_related(
        'mahasiswa__user', 
        'mahasiswa__jenjang_pendidikan',
        'mahasiswa__semester'
    ).all().order_by('-id')
    
    total_pendaftaran = pendaftaran_list.count()
    
    context = {
        'pendaftaran_list': pendaftaran_list,
        'total_pendaftaran': total_pendaftaran,
    }
    
    return render(request, 'admin/approval_pendaftaran.html', context)

@login_required
def data_mahasiswa(request):
    """View untuk data mahasiswa admin"""
    # Ambil parameter filter dari URL
    jenjang_filter = request.GET.get('jenjang', '')
    search_query = request.GET.get('search', '').strip()
    
    # Query dasar dengan semua relasi yang dibutuhkan
    mahasiswa_list = Mahasiswa.objects.select_related(
        'user',
        'jenjang_pendidikan',
        'semester'
    ).prefetch_related(
        'kegiatan_pa'
    ).all()
    
    # Filter berdasarkan jenjang pendidikan
    if jenjang_filter:
        mahasiswa_list = mahasiswa_list.filter(
            jenjang_pendidikan__nama_jenjang__iexact=jenjang_filter
        )
    
    # Filter berdasarkan search (nama, NRP, email)
    if search_query:
        mahasiswa_list = mahasiswa_list.filter(
            Q(user__nama_lengkap__icontains=search_query) |
            Q(user__nrp__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(jurusan__icontains=search_query) |
            Q(kelas__icontains=search_query)
        )
    
    # Urutkan berdasarkan NRP
    mahasiswa_list = mahasiswa_list.order_by('user__nrp')
    
    # Ambil semua jenjang pendidikan DENGAN ANNOTATE untuk hitung jumlah mahasiswa
    jenjang_pendidikan_list = Jenjang_Pendidikan.objects.annotate(
        jumlah_mahasiswa=Count('mahasiswa')
    )
    
    # Hitung total mahasiswa (setelah filter)
    total_mahasiswa = mahasiswa_list.count()
    
    # Handle export Excel
    if request.GET.get('export') == 'excel':
        return export_data_mahasiswa_excel(mahasiswa_list)
    
    context = {
        'mahasiswa_list': mahasiswa_list,
        'jenjang_pendidikan_list': jenjang_pendidikan_list,
        'total_mahasiswa': total_mahasiswa,
        'jenjang_filter': jenjang_filter,
        'search_query': search_query,
    }
    
    return render(request, 'admin/data_mahasiswa.html', context)

def export_data_mahasiswa_excel(mahasiswa_list):
    """Export data mahasiswa ke Excel"""
    # Buat workbook baru
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Mahasiswa"
    
    # Style untuk header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    alignment_center = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Header kolom
    headers = [
        'No', 'NRP', 'Nama Mahasiswa', 'Email', 
        'Jenjang', 'Kelas', 'Semester', 'Jurusan/Prodi',
        'Angkatan', 'Status', 'Kegiatan SKS', 'Tanggal Daftar'
    ]
    
    # Tulis header
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment_center
        cell.border = thin_border
    
    # Tulis data
    for row_num, mahasiswa in enumerate(mahasiswa_list, 2):
        # Dapatkan kegiatan SKS sebagai string
        kegiatan_sks = ", ".join([k.nama_kegiatan for k in mahasiswa.kegiatan_pa.all()[:3]])
        if mahasiswa.kegiatan_pa.count() > 3:
            kegiatan_sks += f" (+{mahasiswa.kegiatan_pa.count() - 3} lagi)"
        
        data = [
            row_num - 1,  # No
            mahasiswa.user.nrp or "",
            mahasiswa.user.nama_lengkap or "",
            mahasiswa.user.email or "",
            mahasiswa.jenjang_pendidikan.nama_jenjang if mahasiswa.jenjang_pendidikan else "",
            mahasiswa.kelas or "",
            mahasiswa.semester.nama_semester if mahasiswa.semester else "",
            mahasiswa.jurusan or "",
            mahasiswa.angkatan or "",
            "Aktif" if mahasiswa.user.is_active else "Nonaktif",
            kegiatan_sks,
            mahasiswa.user.date_joined.strftime("%d-%m-%Y %H:%M") if mahasiswa.user.date_joined else ""
        ]
        
        for col_num, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = thin_border
            if col_num == 2:  # Kolom NRP - bold
                cell.font = Font(bold=True)
            if col_num in [1, 10]:  # Kolom No dan Status - center
                cell.alignment = alignment_center
    
    # Auto adjust column width
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 30)
        ws.column_dimensions[column].width = adjusted_width
    
    # Buat response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"data_mahasiswa_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response

@login_required
def edit_mahasiswa(request, mahasiswa_id):
    """View untuk edit data mahasiswa"""
    mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Ambil data yang dibutuhkan untuk form
        jenjang_pendidikan_list = Jenjang_Pendidikan.objects.all()
        semester_list = Semester.objects.all()
        kegiatan_pa_list = Kegiatan_PA.objects.all()
        
        context = {
            'mahasiswa': mahasiswa,
            'jenjang_pendidikan_list': jenjang_pendidikan_list,
            'semester_list': semester_list,
            'kegiatan_pa_list': kegiatan_pa_list,
        }
        
        return render(request, 'admin/partials/edit_mahasiswa_modal.html', context)
    
    # Handle POST request untuk update data
    if request.method == 'POST':
        try:
            # Update data user
            user = mahasiswa.user
            user.nama_lengkap = request.POST.get('nama_lengkap', user.nama_lengkap)
            user.nrp = request.POST.get('nrp', user.nrp)
            user.email = request.POST.get('email', user.email)
            
            # Update status aktif
            status_akun = request.POST.get('status_akun', 'aktif')
            user.is_active = (status_akun == 'aktif')
            user.save()
            
            # Update data mahasiswa
            jenjang_id = request.POST.get('jenjang_pendidikan')
            if jenjang_id:
                mahasiswa.jenjang_pendidikan = Jenjang_Pendidikan.objects.get(id=jenjang_id)
            
            semester_id = request.POST.get('semester')
            if semester_id:
                mahasiswa.semester = Semester.objects.get(id=semester_id)
            
            mahasiswa.kelas = request.POST.get('kelas', mahasiswa.kelas)
            mahasiswa.angkatan = request.POST.get('angkatan', mahasiswa.angkatan)
            mahasiswa.jurusan = request.POST.get('jurusan', mahasiswa.jurusan)
            mahasiswa.save()
            
            # Update kegiatan PA
            kegiatan_ids = request.POST.getlist('kegiatan_pa')
            mahasiswa.kegiatan_pa.set(Kegiatan_PA.objects.filter(id__in=kegiatan_ids))
            
            return JsonResponse({
                'success': True,
                'message': 'Data mahasiswa berhasil diperbarui!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Gagal memperbarui data: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Metode tidak diizinkan'
    }, status=405)

@login_required
def hapus_mahasiswa(request, mahasiswa_id):
    """View untuk hapus data mahasiswa"""
    if request.method == 'POST':
        mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
        
        try:
            # Hapus user terkait juga
            user = mahasiswa.user
            mahasiswa.delete()
            user.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Data mahasiswa berhasil dihapus'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Gagal menghapus data: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Metode tidak diizinkan'
    }, status=405)

@login_required
def master_data_wajah(request):
    """View untuk master data wajah admin"""
    return render(request, 'admin/master_data_wajah.html')

@login_required
def data_sks(request):
    """View untuk data SKS admin"""
    return render(request, 'admin/data_sks.html')

@login_required
def rekap_presensi(request):
    """View untuk rekap presensi admin"""
    return render(request, 'admin/rekap_presensi.html')

@login_required
def status_pemenuhan(request):
    """View untuk status pemenuhan SKS admin"""
    return render(request, 'admin/status_pemenuhan.html')

@login_required
def pengaturan_sistem(request):
    """View untuk pengaturan sistem admin"""
    return render(request, 'admin/pengaturan_sistem.html')
