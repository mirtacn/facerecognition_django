# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django import forms
from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
import math
from django.db.models import Sum, F, Case, When, Value
from django.db.models.functions import Coalesce
from django.utils.safestring import mark_safe
from datetime import datetime, date, timedelta 
from .forms import Step1Form, Step2Form, Step3Form
from .models import (
    Mahasiswa, FotoWajah, Kegiatan_PA, Jenjang_Pendidikan,
    Tahun_Ajaran, Dosen, Mahasiswa_Dosen, Pengajuan_Pendaftaran,
    Status_Pemenuhan_SKS, Semester, FotoWajah, Mahasiswa_Dosen, Presensi,Durasi
)
from .forms import FilterRekapPresensiForm
from django.db.models import Sum, F, Case, When, Value
from django.db.models.functions import Coalesce
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils import translation
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
from django.utils.safestring import mark_safe
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import datetime
import logging
from liveness_detection import process_frame_liveness, init_liveness_detection, reset_detection_state

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

@login_required
def riwayat_presensi(request):
    try:
        mahasiswa = Mahasiswa.objects.get(user=request.user)
        
        # Ambil semua presensi mahasiswa ini (tanpa filter kegiatan_pa)
        presensi_qs = Presensi.objects.filter(
            mahasiswa=mahasiswa
        ).order_by('-tanggal_presensi', '-jam_checkin')
        
        presensi_list = []
        
        for p in presensi_qs:
            # Hitung durasi jika ada checkin dan checkout
            durasi_text = "-"
            if p.jam_checkin and p.jam_checkout:
                try:
                    # Gabungkan tanggal dengan waktu
                    checkin_datetime = datetime.combine(p.tanggal_presensi, p.jam_checkin)
                    checkout_datetime = datetime.combine(p.tanggal_presensi, p.jam_checkout)
                    
                    # Jika checkout lebih kecil dari checkin (lewat tengah malam)
                    if checkout_datetime < checkin_datetime:
                        checkout_datetime += timedelta(days=1)
                    
                    # Hitung selisih
                    delta = checkout_datetime - checkin_datetime
                    total_seconds = delta.total_seconds()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    
                    # Format durasi
                    if hours > 0:
                        durasi_text = f"{hours}j {minutes}m"
                    elif minutes > 0:
                        durasi_text = f"{minutes}m"
                    else:
                        durasi_text = "0m"
                        
                except Exception as e:
                    durasi_text = "Error"
                    print(f"ERROR hitung durasi: {e}")
            
            # Tambahkan ke list
            presensi_list.append({
                'tanggal': p.tanggal_presensi,
                'check_in': p.jam_checkin,
                'check_out': p.jam_checkout,
                'durasi': durasi_text,
                'foto_checkin': p.foto_checkin.url if p.foto_checkin else None,
                'foto_checkout': p.foto_checkout.url if p.foto_checkout else None,
            })
        
        # Hitung total SKS dari kegiatan PA yang diambil
        total_sks = sum(k.jumlah_sks for k in mahasiswa.kegiatan_pa.all())
        total_target_jam = sum(k.target_jam for k in mahasiswa.kegiatan_pa.all())
        
        # Ambil nama semester
        semester_nama = mahasiswa.semester.nama_semester if mahasiswa.semester else "-"
        
        # Hitung total durasi yang sudah dikerjakan
        total_durasi = 0
        for p in presensi_list:
            if p['durasi'] != '-' and p['durasi'] != 'Error':
                # Parse durasi teks menjadi jam
                try:
                    if 'j' in p['durasi']:
                        hours = int(p['durasi'].split('j')[0].strip())
                        total_durasi += hours
                except:
                    pass
        
        context = {
            'presensi_list': presensi_list,
            'total_sks': total_sks,
            'total_target_jam': total_target_jam,
            'total_durasi': total_durasi,
            'semester_nama': semester_nama,
            'mahasiswa': mahasiswa,
            'kegiatan_pa_list': mahasiswa.kegiatan_pa.all(),
            'total_kegiatan': mahasiswa.kegiatan_pa.count(),
        }
        
        return render(request, 'mahasiswa/riwayat_presensi.html', context)
        
    except Mahasiswa.DoesNotExist:
        messages.error(request, 'Data mahasiswa tidak ditemukan')
        return redirect('profil_mahasiswa')
    except Exception as e:
        print(f"ERROR in riwayat_presensi: {str(e)}")
        messages.error(request, 'Terjadi kesalahan saat mengambil data presensi')
        return redirect('profil_mahasiswa')

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
    ).filter(  # hanya yang aktif
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
            
            # SIMPLIFIKASI: Buat presensi TANPA kegiatan_pa (karena agregat)
            presensi = Presensi.objects.create(
                mahasiswa=mahasiswa,
                kegiatan_pa=None,  # NULL karena sistem agregat
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

@login_required
def debug_presensi_data(request):
    """Fungsi untuk debugging data presensi"""
    try:
        mahasiswa = Mahasiswa.objects.get(user=request.user)
        
        # Ambil semua presensi
        presensi_list = Presensi.objects.filter(
            mahasiswa=mahasiswa,
            jam_checkin__isnull=False,
            jam_checkout__isnull=False
        ).order_by('-tanggal_presensi')
        
        data = []
        total_hours = 0
        
        for presensi in presensi_list:
            checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
            checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
            
            if checkout_dt < checkin_dt:
                checkout_dt += timedelta(days=1)
            
            durasi = checkout_dt - checkin_dt
            hours = durasi.total_seconds() / 3600
            total_hours += hours
            
            data.append({
                'tanggal': presensi.tanggal_presensi,
                'checkin': presensi.jam_checkin,
                'checkout': presensi.jam_checkout,
                'durasi': str(durasi),
                'hours': round(hours, 2)
            })
        
        return JsonResponse({
            'success': True,
            'total_presensi': len(data),
            'total_hours': round(total_hours, 2),
            'data': data,
            'mahasiswa': {
                'nama': mahasiswa.user.nama_lengkap,
                'nim': mahasiswa.nim
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
def detect_liveness_frame(request):
    """
    API endpoint untuk liveness detection - VERSI AGREGAT (SIMPLE)
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            frame_base64 = data.get('frame')
            mahasiswa_id = data.get('mahasiswa_id')
            action = data.get('action')
            
            if not frame_base64:
                return JsonResponse({
                    'success': False,
                    'error': 'No frame provided',
                    'status': 'ERROR'
                })
            
            # Process frame dengan liveness detection (import dari modul liveness)
            from liveness_detection import process_frame_liveness
            result = process_frame_liveness(frame_base64)
            
            # AUTO-SAVE PRESENSI HANYA JIKA STATUS = REAL & FACE MATCHED
            if result.get('status') == 'REAL' and mahasiswa_id and action:
                # --- TAMBAHAN: FACE RECOGNITION DENGAN INSIGHTFACE (ArcFace) ---
                from .face_recognition_utils import verify_face_with_insightface
                from liveness_detection import reset_detection_state
                
                # OPTIMASI: Kirim face box ke utility recognition
                box = result.get('box')
                recognition_result = verify_face_with_insightface(frame_base64, mahasiswa_id, face_box=box)
                
                if not recognition_result.get('verified'):
                    # Jika gagal recognition, balikkan ke liveness (reset blink)
                    reset_detection_state()
                    result['status'] = 'NOT_RECOGNIZED'
                    result['message'] = recognition_result.get('message', 'Identity not matched')
                    result['verified'] = False
                    result['blink_count'] = 0 # Reset di response juga
                    return JsonResponse(result) 
                
                # Update result with recognition info & Student Name
                mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
                result['recognition_score'] = float(1 - recognition_result.get('distance', 1.0))
                result['nama_mahasiswa'] = mahasiswa.user.nama_lengkap or mahasiswa.user.username
                # ---------------------------------------------------

                try:
                    today = date.today()
                    
                    if action == 'checkin':
                        # Cek apakah sudah ada presensi yang belum check-out hari ini
                        existing_presensi = Presensi.objects.filter(
                            mahasiswa=mahasiswa,
                            tanggal_presensi=today,
                            jam_checkout__isnull=True
                        ).first()
                        
                        if existing_presensi:
                            result['message'] = 'Masih ada sesi yang belum check-out'
                            return JsonResponse(result)
                        
                        # Simpan foto check-in
                        format_ext = frame_base64.split(';base64,')[0].split('/')[-1] if ';base64,' in frame_base64 else 'jpg'
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f'checkin_{mahasiswa_id}_{timestamp}.{format_ext}'
                        
                        imgstr = frame_base64.split(';base64,')[1] if ';base64,' in frame_base64 else frame_base64
                        foto_data = ContentFile(base64.b64decode(imgstr), name=filename)
                        
                        # Buat presensi baru tanpa kegiatan_pa
                        presensi = Presensi.objects.create(
                            mahasiswa=mahasiswa,
                            kegiatan_pa=None,  # NULL karena agregat
                            tanggal_presensi=today,
                            jam_checkin=datetime.now().time(),
                            foto_checkin=foto_data
                        )
                        
                        result['presensi_id'] = presensi.id
                        result['saved'] = True
                        result['action'] = 'checkin'
                        
                    elif action == 'checkout':
                        # Update foto check-out
                        presensi = Presensi.objects.filter(
                            mahasiswa=mahasiswa,
                            tanggal_presensi=today,
                            jam_checkout__isnull=True
                        ).first()
                        
                        if presensi:
                            format_ext = frame_base64.split(';base64,')[0].split('/')[-1] if ';base64,' in frame_base64 else 'jpg'
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f'checkout_{mahasiswa_id}_{timestamp}.{format_ext}'
                            
                            imgstr = frame_base64.split(';base64,')[1] if ';base64,' in frame_base64 else frame_base64
                            foto_data = ContentFile(base64.b64decode(imgstr), name=filename)
                            
                            presensi.jam_checkout = datetime.now().time()
                            presensi.foto_checkout = foto_data
                            presensi.save()
                            
                            result['presensi_id'] = presensi.id
                            result['saved'] = True
                            result['action'] = 'checkout'
                
                except Exception as save_error:
                    print(f"[ERROR] Failed to save presensi: {save_error}")
                    result['save_error'] = str(save_error)
            
            return JsonResponse(result)
            
        except Exception as e:
            print(f"[ERROR] detect_liveness_frame: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'status': 'ERROR'
            })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

def calculate_aggregate_progress(mahasiswa):
    """
    Menghitung progress AGREGAT (total gabungan) dari semua kegiatan PA
    """
    # 1. Hitung total target dari semua kegiatan PA yang diambil
    kegiatan_pa_list = mahasiswa.kegiatan_pa.all()
    
    total_target_jam = 0
    total_sks = 0
    
    for kegiatan in kegiatan_pa_list:
        total_target_jam += kegiatan.target_jam
        total_sks += kegiatan.jumlah_sks
    
    # 2. Hitung total durasi dari SEMUA presensi (AGREGAT - tanpa filter kegiatan_pa)
    presensi_list = Presensi.objects.filter(
        mahasiswa=mahasiswa,
        jam_checkin__isnull=False,
        jam_checkout__isnull=False
    )
    
    total_durasi_detik = 0
    
    for presensi in presensi_list:
        if presensi.jam_checkin and presensi.jam_checkout:
            try:
                # Buat datetime untuk checkin dan checkout
                checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
                checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
                
                # Jika checkout lebih kecil dari checkin (lewat tengah malam)
                if checkout_dt < checkin_dt:
                    checkout_dt += timedelta(days=1)
                
                # Hitung selisih dalam detik
                durasi = checkout_dt - checkin_dt
                total_durasi_detik += durasi.total_seconds()
                
                # Debug log
                print(f"DEBUG - Presensi {presensi.id}: {durasi.total_seconds()} detik")
                
            except Exception as e:
                print(f"Error menghitung durasi presensi {presensi.id}: {e}")
    
    # Konversi detik ke jam
    total_durasi_jam = total_durasi_detik / 3600
    
    # Bulatkan ke 1 angka desimal
    total_durasi_jam = round(total_durasi_jam, 1)
    
    # 3. Hitung progress persentase
    progress_percentage = 0
    if total_target_jam > 0:
        progress_percentage = (total_durasi_jam / total_target_jam) * 100
    
    # Bulatkan progress ke 1 angka desimal
    progress_percentage = round(progress_percentage, 1)
    
    # 4. Debug info
    print(f"\n=== DEBUG AGGREGATE PROGRESS ===")
    print(f"Mahasiswa: {mahasiswa.user.nama_lengkap}")
    print(f"Jumlah Kegiatan: {len(kegiatan_pa_list)}")
    print(f"Total Target Jam: {total_target_jam} jam")
    print(f"Total Durasi: {total_durasi_jam} jam ({total_durasi_detik} detik)")
    print(f"Progress: {progress_percentage}%")
    print(f"Presensi ditemukan: {presensi_list.count()}")
    print(f"===============================\n")
    
    return {
        'total_target_jam': total_target_jam,
        'total_durasi_jam': total_durasi_jam,
        'total_sks': total_sks,
        'progress_percentage': progress_percentage,
        'sisa_jam': max(0, total_target_jam - total_durasi_jam),
        'kegiatan_count': len(kegiatan_pa_list),
        'detail_kegiatan': [
            {
                'nama': kegiatan.nama_kegiatan,
                'sks': kegiatan.jumlah_sks,
                'target_jam': kegiatan.target_jam,
                'jumlah_presensi': Presensi.objects.filter(
                    mahasiswa=mahasiswa,
                    kegiatan_pa=kegiatan,
                    jam_checkin__isnull=False,
                    jam_checkout__isnull=False
                ).count()
            }
            for kegiatan in kegiatan_pa_list
        ]
    }

@csrf_exempt
@login_required
def checkout_presensi(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mahasiswa_id = data.get('mahasiswa_id')
            foto_base64 = data.get('foto')

            if foto_base64:
                format, imgstr = foto_base64.split(';base64,')
                ext = format.split('/')[-1]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f'checkout_{mahasiswa_id}_{timestamp}.{ext}'
                foto_data = ContentFile(base64.b64decode(imgstr), name=filename)

            mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)

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

            presensi.jam_checkout = datetime.now().time()

            if foto_base64:
                presensi.foto_checkout = foto_data

            presensi.save()

            # Hitung dan simpan durasi (tetap pakai Durasi untuk riwayat)
            if presensi.jam_checkin and presensi.jam_checkout:
                checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
                checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
                if checkout_dt < checkin_dt:
                    checkout_dt += timedelta(days=1)
                durasi = checkout_dt - checkin_dt

                Durasi.objects.update_or_create(
                    presensi=presensi,
                    defaults={'waktu_durasi': durasi}
                )

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

# Modifikasi fungsi checkout_presensi untuk langsung update jam_tercapai
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
            
            # Hitung durasi - FIX INI: Gunakan datetime yang benar
            if presensi.jam_checkin and presensi.jam_checkout:
                checkin_dt = datetime.combine(
                    presensi.tanggal_presensi, 
                    presensi.jam_checkin
                )
                checkout_dt = datetime.combine(
                    presensi.tanggal_presensi, 
                    presensi.jam_checkout
                )
                
                # Jika checkout lebih kecil dari checkin (lewat tengah malam)
                if checkout_dt < checkin_dt:
                    checkout_dt += timedelta(days=1)
                
                durasi = checkout_dt - checkin_dt
                
                # Debug: Cetak durasi
                print(f"DEBUG checkout_presensi - Durasi dihitung: {durasi}")
                print(f"DEBUG - Checkin: {checkin_dt}, Checkout: {checkout_dt}")
                
                # Simpan durasi - PERBAIKAN: Buat atau update Durasi
                Durasi.objects.update_or_create(
                    presensi=presensi,
                    defaults={'waktu_durasi': durasi}
                )
                
                print(f"DEBUG - Durasi berhasil disimpan untuk presensi {presensi.id}")
                
                # PERBAIKAN: Hitung total durasi untuk update Status_Pemenuhan_SKS
                total_hours = calculate_total_duration(mahasiswa.id, presensi.kegiatan_pa.id)
                
                # Debug
                print(f"DEBUG - Total hours setelah checkout: {total_hours}")
                
                # Update Status_Pemenuhan_SKS
                status_sks, created = Status_Pemenuhan_SKS.objects.get_or_create(
                    mahasiswa=mahasiswa,
                    kegiatan_pa=presensi.kegiatan_pa,
                    defaults={
                        'jam_target': presensi.kegiatan_pa.target_jam,
                        'jumlah_sks': presensi.kegiatan_pa.jumlah_sks,
                        'jam_tercapai': total_hours
                    }
                )
                
                if not created:
                    status_sks.jam_tercapai = total_hours
                
                # Cek apakah sudah memenuhi target
                if status_sks.jam_tercapai >= status_sks.jam_target:
                    status_sks.status_pemenuhan = 'memenuhi'
                else:
                    status_sks.status_pemenuhan = 'belum memenuhi'
                
                status_sks.save()
                
                print(f"DEBUG - Status SKS updated: {status_sks.jam_tercapai} jam tercapai")
            
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
                    'presensi_id': presensi.id,
                    'total_durasi_jam': total_hours if 'total_hours' in locals() else 0
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
def fix_missing_durations(request):
    """
    Fungsi untuk membuat Durasi dari presensi yang sudah ada
    tapi tidak memiliki Durasi (hanya memperbaiki tabel Durasi saja).
    Tidak lagi update Status_Pemenuhan_SKS karena sistem sekarang agregat.
    """
    if not (request.user.role == 'admin' or request.user.is_superuser):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        # Cari semua presensi yang sudah check-in & check-out tapi belum punya Durasi
        presensi_without_duration = Presensi.objects.filter(
            jam_checkin__isnull=False,
            jam_checkout__isnull=False
        ).exclude(
            durasi__isnull=False  # Exclude yang sudah punya Durasi
        )
        
        fixed_count = 0
        
        for presensi in presensi_without_duration:
            # Hitung durasi
            checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
            checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
            
            if checkout_dt < checkin_dt:
                checkout_dt += timedelta(days=1)
            
            durasi = checkout_dt - checkin_dt
            
            # Buat record Durasi
            Durasi.objects.create(
                presensi=presensi,
                waktu_durasi=durasi
            )
            
            print(f"Fixed: Presensi {presensi.id} - Durasi: {durasi}")
            fixed_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Berhasil memperbaiki {fixed_count} data Durasi yang hilang',
            'fixed_count': fixed_count
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@login_required
def check_duration_status(request):
    """
    Cek status Durasi untuk debugging
    """
    try:
        mahasiswa = Mahasiswa.objects.get(user=request.user)
        
        # Cek semua presensi mahasiswa
        presensi_list = Presensi.objects.filter(
            mahasiswa=mahasiswa
        ).select_related('kegiatan_pa')
        
        result = []
        
        for presensi in presensi_list:
            has_duration = hasattr(presensi, 'durasi')
            durasi_value = presensi.durasi.waktu_durasi if has_duration else None
            
            result.append({
                'id': presensi.id,
                'tanggal': presensi.tanggal_presensi,
                'kegiatan': presensi.kegiatan_pa.nama_kegiatan,
                'checkin': presensi.jam_checkin,
                'checkout': presensi.jam_checkout,
                'has_duration': has_duration,
                'duration_value': str(durasi_value) if durasi_value else None,
            })
        
        # Debug info
        total_presensi = len(result)
        presensi_with_duration = sum(1 for r in result if r['has_duration'])
        
        print(f"DEBUG check_duration_status - Total presensi: {total_presensi}")
        print(f"DEBUG - Presensi dengan Durasi: {presensi_with_duration}")
        print(f"DEBUG - Presensi tanpa Durasi: {total_presensi - presensi_with_duration}")
        
        return JsonResponse({
            'success': True,
            'data': result,
            'summary': {
                'total_presensi': total_presensi,
                'with_duration': presensi_with_duration,
                'without_duration': total_presensi - presensi_with_duration
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        })

@login_required
def get_progress_sks_api(request):
    """API untuk mendapatkan progress SKS berdasarkan durasi"""
    try:
        user = request.user
        mahasiswa = Mahasiswa.objects.get(user=user)
        
        # Ambil semua status pemenuhan SKS untuk mahasiswa ini (hanya kegiatan yang diambil)
        status_list = Status_Pemenuhan_SKS.objects.filter(
            mahasiswa=mahasiswa,
            kegiatan_pa__in=mahasiswa.kegiatan_pa.all()
        ).select_related('kegiatan_pa')
        
        progress_data = []
        total_jam_tercapai = 0
        total_jam_target = 0
        
        for status in status_list:
            # Hitung total durasi untuk kegiatan ini
            total_hours = calculate_total_duration(mahasiswa.id, status.kegiatan_pa.id)
            
            # Update dengan data terbaru
            status.jam_tercapai = total_hours
            if status.jam_tercapai >= status.jam_target:
                status.status_pemenuhan = 'memenuhi'
            else:
                status.status_pemenuhan = 'belum memenuhi'
            status.save()
            
            progress_data.append({
                'kegiatan': status.kegiatan_pa.nama_kegiatan,
                'sks': status.jumlah_sks,
                'jam_target': status.jam_target,
                'jam_tercapai': status.jam_tercapai,
                'progress_percentage': min(100, int((status.jam_tercapai / status.jam_target) * 100)) if status.jam_target > 0 else 0,
                'status': status.status_pemenuhan
            })
            
            total_jam_tercapai += status.jam_tercapai
            total_jam_target += status.jam_target
        
        # Hitung progress keseluruhan
        overall_progress = min(100, int((total_jam_tercapai / total_jam_target) * 100)) if total_jam_target > 0 else 0
        
        return JsonResponse({
            'success': True,
            'data': {
                'mahasiswa': {
                    'nama': mahasiswa.user.nama_lengkap,
                    'nim': mahasiswa.nim,
                    'kelas': mahasiswa.kelas
                },
                'progress_per_kegiatan': progress_data,
                'summary': {
                    'total_jam_tercapai': total_jam_tercapai,
                    'total_jam_target': total_jam_target,
                    'overall_progress_percentage': overall_progress,
                    'sisa_jam': max(0, total_jam_target - total_jam_tercapai)
                }
            }
        })
        
    except Mahasiswa.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Data mahasiswa tidak ditemukan'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)

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
            'nama': mahasiswa.user.nama_lengkap,
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
def progress_sks(request):
    try:
        mahasiswa = Mahasiswa.objects.get(user=request.user)
        
        # Hitung progress AGREGAT
        progress_data = calculate_aggregate_progress(mahasiswa)
        
        total_target = progress_data['total_target_jam']
        total_tercapai = progress_data['total_durasi_jam']
        total_sks = progress_data['total_sks']
        progress_percentage = progress_data['progress_percentage']
        jam_sisa = progress_data['sisa_jam']
        jumlah_kegiatan = progress_data['kegiatan_count']
        detail_kegiatan = progress_data['detail_kegiatan']
        
        # Hitung statistik lainnya
        rata_per_minggu = 0
        if total_tercapai > 0:
            # Hitung jumlah minggu berjalan sejak semester dimulai
            try:
                if mahasiswa.semester and mahasiswa.semester.tanggal_mulai:
                    tanggal_mulai = mahasiswa.semester.tanggal_mulai
                    hari_berjalan = (date.today() - tanggal_mulai).days
                    minggu_berjalan = max(1, math.ceil(hari_berjalan / 7))
                else:
                    minggu_berjalan = 8  # Default 8 minggu
                
                rata_per_minggu = round(total_tercapai / minggu_berjalan, 1)
            except:
                rata_per_minggu = round(total_tercapai / 8, 1)  # Fallback
        
        estimasi_selesai = ""
        sisa_waktu = 0
        rekomendasi_per_hari = 0
        
        if rata_per_minggu > 0 and jam_sisa > 0:
            sisa_minggu = jam_sisa / rata_per_minggu
            tanggal_estimasi = date.today() + timedelta(days=sisa_minggu * 7)
            estimasi_selesai = tanggal_estimasi.strftime("%d %B %Y")
            sisa_waktu = int(sisa_minggu * 7)
            rekomendasi_per_hari = round(jam_sisa / sisa_waktu, 2) if sisa_waktu > 0 else 0
        
        # Data untuk JavaScript
        js_data = {
            'progress_percentage': progress_percentage,
            'jam_terselesaikan': total_tercapai,
            'jam_sisa': jam_sisa,
            'total_sks': total_sks,
            'jam_target_total': total_target,
            'rata_per_minggu': rata_per_minggu,
            'sisa_waktu': sisa_waktu,
            'rekomendasi_per_hari': rekomendasi_per_hari,
            'estimasi_selesai': estimasi_selesai,
            'mahasiswa_nama': mahasiswa.user.nama_lengkap,
            'mahasiswa_nim': mahasiswa.nim,
            'semester_nama': mahasiswa.semester.nama_semester if mahasiswa.semester else "-",
            'kegiatan_count': jumlah_kegiatan,
        }
        
        # Debug info ke console
        print(f"\n=== DEBUG PROGRESS SKS PAGE ===")
        print(f"Mahasiswa: {mahasiswa.user.nama_lengkap} ({mahasiswa.nim})")
        print(f"Total Presensi: {Presensi.objects.filter(mahasiswa=mahasiswa).count()}")
        print(f"Total Durasi: {total_tercapai} jam")
        print(f"Target: {total_target} jam")
        print(f"Progress: {progress_percentage}%")
        print("==============================\n")
        
        context = {
            'mahasiswa': mahasiswa,
            'total_sks': total_sks,
            'jam_terselesaikan': total_tercapai,
            'jam_target_total': total_target,
            'jam_sisa': jam_sisa,
            'progress_percentage': progress_percentage,
            'rata_per_minggu': rata_per_minggu,
            'estimasi_selesai': estimasi_selesai,
            'sisa_waktu': sisa_waktu,
            'rekomendasi_per_hari': rekomendasi_per_hari,
            'jumlah_kegiatan': jumlah_kegiatan,
            'detail_kegiatan': detail_kegiatan,
            'js_data_json': mark_safe(json.dumps(js_data)),
        }
        
        return render(request, 'mahasiswa/progress_sks.html', context)
        
    except Mahasiswa.DoesNotExist:
        messages.error(request, 'Data mahasiswa tidak ditemukan')
        return redirect('profil_mahasiswa')
    except Exception as e:
        print(f"Error in progress_sks: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Terjadi kesalahan saat mengambil data progress SKS: {str(e)}')
        return redirect('profil_mahasiswa')

# --- ADMIN VIEWS ---
@login_required
def admin_dashboard(request):
    if not (request.user.role == 'admin' or request.user.is_superuser):
        return redirect('login')

    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Senin minggu ini

    # Nama hari yang diterjemahkan (lazy)
    DAY_NAMES = [
        _("Senin"), _("Selasa"), _("Rabu"), _("Kamis"),
        _("Jumat"), _("Sabtu"), _("Minggu")
    ]
    day_labels = {i: str(DAY_NAMES[i]) for i in range(7)}

    # Presensi hari ini
    today_present = Presensi.objects.filter(
        tanggal_presensi=today, jam_checkin__isnull=False
    ).values('mahasiswa_id').distinct().count()

    total_approved_students = Mahasiswa.objects.filter(
        pengajuan_pendaftaran__status_pengajuan='disetujui'
    ).count()

    # Mapping warna & badge
    color_map = {
        'D3 - Diploma 3': 'bg-primary',
        'D4 - Diploma 4': 'bg-info',
        'LJ - Lanjut Jenjang': 'bg-success',
        'S2 - Magister': 'bg-warning text-dark',
    }
    badge_map = {
        'D3 - Diploma 3': 'primary',
        'D4 - Diploma 4': 'info',
        'LJ - Lanjut Jenjang': 'success',
        'S2 - Magister': 'warning',
    }

    jenjang_list = Jenjang_Pendidikan.objects.all().order_by('nama_jenjang')

    weekly_data = {}  # key: 0-6 (Senin-Minggu)
    weekly_summary = []
    total_hadir_week = total_mahasiswa_week = 0

    # Data per hari dalam seminggu
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        weekday_num = day_date.weekday()

        # Max hadir hari itu (untuk scaling bar)
        max_hadir_hari = Presensi.objects.filter(
            tanggal_presensi=day_date,
            jam_checkin__isnull=False
        ).values('mahasiswa_id').distinct().count() or 1

        day_entries = []
        for jenjang in jenjang_list:
            hadir = Presensi.objects.filter(
                tanggal_presensi=day_date,
                mahasiswa__jenjang_pendidikan=jenjang,
                jam_checkin__isnull=False
            ).values('mahasiswa_id').distinct().count()

            total_mhs = Mahasiswa.objects.filter(
                jenjang_pendidikan=jenjang,
                pengajuan_pendaftaran__status_pengajuan='disetujui'
            ).count()

            perc = round(hadir / total_mhs * 100, 1) if total_mhs > 0 else 0.0

            # Scaling height: lebih aman, hindari height 0% meski ada hadir
            height_scaled = 0
            if max_hadir_hari > 0 and hadir > 0:
                height_scaled = round((hadir / max_hadir_hari) * 100, 1)
            # Opsional: minimal height 5% kalau ada hadir tapi scaling kecil
            if hadir > 0 and height_scaled < 5:
                height_scaled = 5.0

            day_entries.append({
                'jenjang': jenjang.nama_jenjang,
                'hadir': hadir,
                'total': total_mhs,
                'percentage': perc,
                'height': height_scaled,
                'color': color_map.get(jenjang.nama_jenjang, 'bg-primary'),
                'badge': badge_map.get(jenjang.nama_jenjang, 'primary'),
            })

        weekly_data[weekday_num] = day_entries

    # Ringkasan mingguan per jenjang
    for jenjang in jenjang_list:
        hadir_week = Presensi.objects.filter(
            tanggal_presensi__gte=week_start,
            tanggal_presensi__lte=today,
            mahasiswa__jenjang_pendidikan=jenjang,
            jam_checkin__isnull=False
        ).values('mahasiswa_id').distinct().count()

        total_mhs = Mahasiswa.objects.filter(
            jenjang_pendidikan=jenjang,
            pengajuan_pendaftaran__status_pengajuan='disetujui'
        ).count()

        perc_week = round(hadir_week / total_mhs * 100, 1) if total_mhs > 0 else 0.0

        weekly_summary.append({
            'code': jenjang.nama_jenjang,
            'present': hadir_week,
            'total': total_mhs,
            'percentage': perc_week,
            'color': color_map.get(jenjang.nama_jenjang, 'bg-primary'),
            'badge': badge_map.get(jenjang.nama_jenjang, 'primary'),
        })

        total_hadir_week += hadir_week
        total_mahasiswa_week += total_mhs

    weekly_total_perc = round(total_hadir_week / total_mahasiswa_week * 100, 1) if total_mahasiswa_week > 0 else 0.0

    # Rata-rata mingguan
    daily_percentages = []
    for entries in weekly_data.values():
        day_hadir = sum(e['hadir'] for e in entries)
        day_total = sum(e['total'] for e in entries)
        daily_percentages.append(round(day_hadir / day_total * 100, 1) if day_total > 0 else 0.0)
    avg_attendance_week = round(sum(daily_percentages) / len(daily_percentages), 1) if daily_percentages else 0.0

    # Semester aktif
    try:
        active_ta = Tahun_Ajaran.objects.get(status_aktif='aktif')
        current_semester_name = active_ta.nama_tahun_ajaran or "Semester Aktif"
        days_total = (active_ta.tanggal_selesai - active_ta.tanggal_mulai).days
        days_passed = (today - active_ta.tanggal_mulai).days
        semester_progress = round(days_passed / days_total * 100) if days_total > 0 else 0
        weeks_remaining = max(0, round((days_total - days_passed) / 7))
    except Tahun_Ajaran.DoesNotExist:
        current_semester_name = "Tidak Ada Semester Aktif"
        semester_progress = weeks_remaining = 0

    # Recent activities
    recent_presensi = Presensi.objects.select_related('mahasiswa__user').filter(
        jam_checkin__isnull=False
    ).order_by('-tanggal_presensi', '-jam_checkin')[:4]

    recent_activities = []
    for p in recent_presensi:
        dt = timezone.localtime(timezone.make_aware(datetime.combine(p.tanggal_presensi, p.jam_checkin)))
        time_ago = dt.strftime("%H:%M") if p.tanggal_presensi == today else p.tanggal_presensi.strftime("%d %b")
        initials = ''.join([w[0].upper() for w in (p.mahasiswa.user.nama_lengkap or "").split()[:2]]) or "??"

        recent_activities.append({
            'nama': p.mahasiswa.user.nama_lengkap or p.mahasiswa.nim,
            'nim': p.mahasiswa.nim,
            'action': "Check-out" if p.jam_checkout else "Check-in",
            'time_ago': time_ago,
            'color': 'success' if p.jam_checkout else 'primary',
            'initials': initials,
        })

    # JSON untuk modal
    day_data_json = {}
    for weekday_num, entries in weekly_data.items():
        day_data_json[str(weekday_num)] = [
            {
                'jenjang': e['jenjang'],
                'hadir': e['hadir'],
                'total': e['total'],
                'percentage': e['percentage'],
                'badge': e['badge']
            } for e in entries
        ]

    # Siapkan context
    context = {
        'today_present_count': today_present,
        'today_total_students': total_approved_students,
        'avg_attendance_week': avg_attendance_week,
        'current_semester_name': current_semester_name,
        'semester_progress': semester_progress,
        'weeks_remaining': weeks_remaining,
        'weekly_data': weekly_data,
        'weekly_summary': weekly_summary,
        'weekly_total': {
            'present': total_hadir_week,
            'total': total_mahasiswa_week,
            'percentage': weekly_total_perc,
        },
        'recent_activities': recent_activities,
        'day_data_json': day_data_json,
        'day_labels': day_labels,
    }

    # Pastikan semua hari ada (untuk chart lengkap)
    for i in range(7):
        if i not in weekly_data:
            weekly_data[i] = []

    # Sorted untuk urutan Senin-Minggu
    sorted_weekly = sorted(weekly_data.items(), key=lambda x: x[0])
    context['sorted_weekly'] = sorted_weekly

    return render(request, 'admin/admin_dashboard.html', context)

@login_required
def monitoring_presensi(request):
    """View untuk monitoring presensi admin"""
    return render(request, 'admin/status_pemenuhan_sks.html')

@login_required
def status_pemenuhan_sks(request):
    if not (request.user.role == 'admin' or request.user.is_superuser):
        messages.error(request, 'Akses ditolak. Halaman ini untuk admin.')
        return redirect('admin_dashboard')

    mahasiswa_setuju = Mahasiswa.objects.filter(
        pengajuan_pendaftaran__status_pengajuan='disetujui'
    ).select_related('user', 'jenjang_pendidikan').prefetch_related('kegiatan_pa').distinct()

    jenjang_list = Jenjang_Pendidikan.objects.all().order_by('nama_jenjang')
    data_mahasiswa = []

    for mahasiswa in mahasiswa_setuju:
        # Hitung TOTAL agregat (sama seperti halaman mahasiswa)
        total_jam_ditempuh = calculate_total_duration_all(mahasiswa.id)

        kegiatan_pa_set = mahasiswa.kegiatan_pa.all()
        total_jam_target = sum(k.target_jam for k in kegiatan_pa_set)
        total_sks = sum(k.jumlah_sks for k in kegiatan_pa_set)

        status_overall = 'Memenuhi' if total_jam_ditempuh >= total_jam_target else 'Belum Memenuhi'

        progress_percentage = 0
        progress_class = 'bg-secondary'
        if total_jam_target > 0:
            progress_percentage = (total_jam_ditempuh / total_jam_target) * 100
            if total_jam_ditempuh >= total_jam_target:
                progress_class = 'bg-success'
            elif total_jam_ditempuh >= total_jam_target * 0.7:
                progress_class = 'bg-primary'
            elif total_jam_ditempuh >= total_jam_target * 0.4:
                progress_class = 'bg-warning'
            else:
                progress_class = 'bg-danger'

        sisa_jam = max(0, total_jam_target - total_jam_ditempuh)
        persentase_40 = total_jam_target * 0.4
        persentase_70 = total_jam_target * 0.7

        # Breakdown per kegiatan (proporsional untuk tampilan saja)
        kegiatan_list = []
        for kegiatan in kegiatan_pa_set:
            proporsi = kegiatan.target_jam / total_jam_target if total_jam_target > 0 else 0
            jam_tercapai_proporsional = round(total_jam_ditempuh * proporsi, 1)

            kegiatan_list.append({
                'nama_kegiatan': kegiatan.nama_kegiatan,
                'sks': kegiatan.jumlah_sks,
                'jam_per_minggu': getattr(kegiatan, 'total_jam_minggu', 0),
                'jam_target': kegiatan.target_jam,
                'jam_tercapai': jam_tercapai_proporsional,
                'status_per_kegiatan': 'Memenuhi' if jam_tercapai_proporsional >= kegiatan.target_jam else 'Belum Memenuhi'
            })

        data_mahasiswa.append({
            'nama': mahasiswa.user.nama_lengkap or mahasiswa.user.username,
            'jenjang': mahasiswa.jenjang_pendidikan.nama_jenjang if mahasiswa.jenjang_pendidikan else '-',
            'kegiatan_list': kegiatan_list,
            'total_jam_ditempuh': round(total_jam_ditempuh, 1),
            'total_jam_target': round(total_jam_target, 1),
            'total_sks': total_sks,
            'progress_percentage': round(progress_percentage, 1),
            'progress_class': progress_class,
            'sisa_jam': round(sisa_jam, 1),
            'persentase_40': round(persentase_40, 1),
            'persentase_70': round(persentase_70, 1),
            'status_overall': status_overall
        })

    data_mahasiswa.sort(key=lambda x: x['nama'].lower())

    total_memenuhi = sum(1 for m in data_mahasiswa if m['status_overall'] == 'Memenuhi')
    total_belum_memenuhi = sum(1 for m in data_mahasiswa if m['status_overall'] == 'Belum Memenuhi')
    total_sks_all = sum(m['total_sks'] for m in data_mahasiswa)

    context = {
        'data_mahasiswa': data_mahasiswa,
        'total_mahasiswa': len(data_mahasiswa),
        'total_sks_all': total_sks_all,
        'total_memenuhi': total_memenuhi,
        'total_belum_memenuhi': total_belum_memenuhi,
        'jenjang_list': jenjang_list,
    }
    return render(request, 'admin/status_pemenuhan_sks.html', context)

def calculate_total_duration_all(mahasiswa_id):
    """Total jam dari SEMUA presensi mahasiswa, tanpa peduli kegiatan_pa"""
    presensi_list = Presensi.objects.filter(
        mahasiswa_id=mahasiswa_id,
        jam_checkin__isnull=False,
        jam_checkout__isnull=False
    )
    
    total_seconds = 0
    for presensi in presensi_list:
        if presensi.jam_checkin and presensi.jam_checkout:
            checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
            checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
            if checkout_dt < checkin_dt:
                checkout_dt += timedelta(days=1)
            delta = checkout_dt - checkin_dt
            total_seconds += delta.total_seconds()
    
    return round(total_seconds / 3600, 1)

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
    
    # Query dengan select_related untuk optimasi
    pendaftaran_list = Pengajuan_Pendaftaran.objects.select_related(
        'mahasiswa__user', 
        'mahasiswa__jenjang_pendidikan',
        'mahasiswa__semester'
    ).all()
    
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
    
    # Jika POST untuk update status - PERBAIKAN
    if request.method == 'POST':
        print(f"\n=== DEBUG: POST REQUEST DITERIMA ===")
        print(f"POST data: {dict(request.POST)}")
        
        pengajuan_id = request.POST.get('pengajuan_id')
        action = request.POST.get('action')
        alasan_penolakan = request.POST.get('alasan_penolakan', '')
        
        if not pengajuan_id:
            return JsonResponse({
                'success': False,
                'message': 'ID pengajuan tidak ditemukan'
            })
        
        try:
            # DAPATKAN OBJEK DARI DATABASE
            pengajuan = Pengajuan_Pendaftaran.objects.get(id=pengajuan_id)
            mahasiswa = pengajuan.mahasiswa
            user = mahasiswa.user
            
            print(f"DEBUG: Status sebelum: {pengajuan.status_pengajuan}")
            print(f"DEBUG: Mahasiswa: {user.nama_lengkap}")
            
            # GUNAKAN TRANSACTION ATOMIC UNTUK KONSISTENSI
            with transaction.atomic():
                if action == 'approve':
                    pengajuan.status_pengajuan = 'disetujui'
                    pengajuan.alasan_penolakan = ''
                    
                    # Aktifkan akun mahasiswa
                    user.is_active = True
                    user.status_akun = 'disetujui'  # Tambahan update status_akun

                    
                    print(f"DEBUG: Status diubah menjadi: disetujui")
                    print(f"DEBUG: User {user.username} diaktifkan")
                    
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
                    user.is_active = False
                    user.status_akun = 'ditolak'  # Tambahan update status_akun

                    
                    print(f"DEBUG: Status diubah menjadi: ditolak")
                    print(f"DEBUG: User {user.username} dinonaktifkan")
                    print(f"DEBUG: Alasan: {alasan_penolakan}")
                    
                    messages.warning(request, f'Pendaftaran {user.nama_lengkap} ditolak.')
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Action tidak valid'
                    })
                
                # SIMPAN PERUBAHAN
                pengajuan.save()
                user.save()
                
                # TRANSACTION AKAN COMMIT OTOMATIS DI SINI JIKA TIDAK ADA ERROR
                
            # Refresh dari database untuk memastikan
            pengajuan.refresh_from_db()
            user.refresh_from_db()
            
            print(f"DEBUG: Status setelah refresh: {pengajuan.status_pengajuan}")
            print(f"DEBUG: Updated at: {pengajuan.updated_at}")
            print(f"DEBUG: User active: {user.is_active}")
            print("=== DEBUG: SELESAI ===\n")
            
            return JsonResponse({
                'success': True,
                'message': 'Status pendaftaran berhasil diperbarui',
                'new_status': pengajuan.status_pengajuan
            })
                
        except Pengajuan_Pendaftaran.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Pengajuan tidak ditemukan'
            })
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Terjadi kesalahan: {str(e)}'
            })
    
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
    
    # Ambil semua foto wajah
    foto_wajah = FotoWajah.objects.filter(mahasiswa=mahasiswa).order_by('-created_at')
    
    # Ambil semua dosen pembimbing
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

def download_foto_wajah(request, mahasiswa_id):
    """Download semua foto wajah mahasiswa dalam format zip"""
    mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
    foto_wajah_list = FotoWajah.objects.filter(mahasiswa=mahasiswa)
    
    if not foto_wajah_list:
        messages.error(request, "Tidak ada foto wajah untuk didownload")
        return redirect('approval_pendaftaran')
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for foto in foto_wajah_list:
                if foto.file_path and os.path.exists(foto.file_path.path):
                    file_name = f"{mahasiswa.user.nrp}_{mahasiswa.user.nama_lengkap}_{os.path.basename(foto.file_path.name)}"
                    zip_file.write(foto.file_path.path, file_name)
        
        zip_buffer.seek(0)
        
        # Create response
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="foto_wajah_{mahasiswa.user.nrp}_{mahasiswa.user.nama_lengkap.replace(" ", "_")}.zip"'
        
        return response
    except Exception as e:
        print(f"Error creating zip: {e}")
        messages.error(request, "Gagal membuat file zip. Pastikan file foto tersedia.")
        return redirect('approval_pendaftaran')

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
    mahasiswa_list = Mahasiswa.objects.filter(
        pengajuan_pendaftaran__status_pengajuan__iexact='disetujui'
    )
    
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
    # Ambil data mahasiswa dengan jumlah foto
    mahasiswa_list = Mahasiswa.objects.filter(
        pengajuan_pendaftaran__status_pengajuan='disetujui'
    ).select_related(
        'user', 'jenjang_pendidikan', 'semester'
    ).annotate(
        jumlah_foto=Count('foto_wajah')
    ).order_by('user__nama_lengkap')
    
    # Filter berdasarkan search
    search_query = request.GET.get('search', '')
    if search_query:
        mahasiswa_list = mahasiswa_list.filter(
            user__nama_lengkap__icontains=search_query
        ) | mahasiswa_list.filter(
            user__nrp__icontains=search_query
        ) | mahasiswa_list.filter(
            jurusan__icontains=search_query
        )
    
    context = {
        'mahasiswa_list': mahasiswa_list,
        'total_mahasiswa': Mahasiswa.objects.count(),
        'total_foto': FotoWajah.objects.count(),
        'search_query': search_query,
    }
    return render(request, 'admin/master_data_wajah.html', context)

@login_required
def get_foto_wajah_detail(request, mahasiswa_id):
    """API untuk mendapatkan detail foto wajah mahasiswa (JSON response)"""
    mahasiswa = get_object_or_404(
        Mahasiswa.objects.select_related('user', 'jenjang_pendidikan', 'semester'),
        id=mahasiswa_id
    )
    
    foto_list = FotoWajah.objects.filter(mahasiswa=mahasiswa).order_by('-created_at')
    
    # Siapkan data untuk response JSON
    foto_data = []
    for foto in foto_list:
        foto_data.append({
            'id': foto.id,
            'url': foto.file_path.url,
            'created_at': foto.created_at.strftime("%d %b %Y %H:%M"),
            'keterangan': foto.keterangan or ""
        })
    
    response_data = {
        'success': True,
        'mahasiswa': {
            'id': mahasiswa.id,
            'nama_lengkap': mahasiswa.user.nama_lengkap,
            'nrp': mahasiswa.user.nrp,
            'jurusan': mahasiswa.jurusan,
            'jenjang': mahasiswa.jenjang_pendidikan.nama_jenjang if mahasiswa.jenjang_pendidikan else '-',
            'semester': mahasiswa.semester.nama_semester if mahasiswa.semester else '-',
            'status_akun': mahasiswa.user.get_status_akun_display(),
            'is_active': mahasiswa.user.status_akun == 'aktif',
            'date_joined': mahasiswa.user.date_joined.strftime("%d %b %Y"),
        },
        'fotos': foto_data,
        'total_fotos': len(foto_data)
    }
    
    return JsonResponse(response_data)

@login_required
def download_all_fotos(request, mahasiswa_id):
    """Download semua foto mahasiswa dalam format zip"""
    mahasiswa = get_object_or_404(Mahasiswa, id=mahasiswa_id)
    foto_list = FotoWajah.objects.filter(mahasiswa=mahasiswa)
    
    if not foto_list:
        return JsonResponse({'error': 'Tidak ada foto untuk didownload'}, status=404)
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for foto in foto_list:
            if foto.file_path:
                try:
                    # Baca file dari storage
                    file_content = foto.file_path.read()
                    # Buat nama file yang rapi
                    filename = f"{mahasiswa.user.nrp}_{foto.id:03d}_{foto.created_at.strftime('%Y%m%d_%H%M%S')}.jpg"
                    zip_file.writestr(filename, file_content)
                except Exception as e:
                    continue
    
    zip_buffer.seek(0)
    
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="foto_wajah_{mahasiswa.user.nrp}.zip"'
    return response

@login_required
def data_sks(request):
    """View untuk data SKS/Kegiatan admin"""
    # Ambil semua kegiatan
    kegiatan_list = Kegiatan_PA.objects.select_related('jenjang_pendidikan', 'tahun_ajaran').all().order_by('jenjang_pendidikan__nama_jenjang', 'nama_kegiatan')
    
    # Ambil semua jenjang untuk filter
    jenjang_list = Jenjang_Pendidikan.objects.all()
    
    # Ambil semua tahun ajaran untuk tab semester
    tahun_ajaran_list = Tahun_Ajaran.objects.all().order_by('-tanggal_mulai')
    
    # Filter berdasarkan jenjang
    jenjang_filter = request.GET.get('jenjang', '')
    if jenjang_filter:
        kegiatan_list = kegiatan_list.filter(jenjang_pendidikan_id=jenjang_filter)
    
    # Filter berdasarkan pencarian
    search_query = request.GET.get('search', '')
    if search_query:
        kegiatan_list = kegiatan_list.filter(
            Q(nama_kegiatan__icontains=search_query) |
            Q(jenjang_pendidikan__nama_jenjang__icontains=search_query)
        )
    
    context = {
        'kegiatan_list': kegiatan_list,
        'jenjang_list': jenjang_list,
        'tahun_ajaran_list': tahun_ajaran_list,
        'total_kegiatan': kegiatan_list.count(),
        'jenjang_filter': jenjang_filter,
        'search_query': search_query,
    }
    return render(request, 'admin/data_sks.html', context)

@login_required
def tambah_kegiatan_sks(request):
    """View untuk menambah kegiatan SKS baru"""
    if request.method == 'POST':
        try:
            # Ambil data dari form
            nama_kegiatan = request.POST.get('nama_kegiatan')
            jenjang_id = request.POST.get('jenjang_pendidikan')
            tahun_ajaran_id = request.POST.get('tahun_ajaran')
            jumlah_sks = request.POST.get('jumlah_sks', 0)
            total_jam_minggu = request.POST.get('total_jam_minggu', 0)
            target_jam = request.POST.get('target_jam', 0)
            
            # Validasi data
            if not nama_kegiatan or not jenjang_id:
                messages.error(request, 'Nama kegiatan dan jenjang harus diisi')
                return redirect('data_sks')
            
            # Jika tahun ajaran tidak dipilih, ambil tahun ajaran aktif
            if not tahun_ajaran_id:
                tahun_ajaran_aktif = Tahun_Ajaran.objects.filter(status_aktif='aktif').first()
                if tahun_ajaran_aktif:
                    tahun_ajaran_id = tahun_ajaran_aktif.id
                else:
                    messages.error(request, 'Tidak ada tahun ajaran aktif. Silakan aktifkan tahun ajaran terlebih dahulu.')
                    return redirect('data_sks')
            
            # Buat objek kegiatan baru
            kegiatan = Kegiatan_PA(
                nama_kegiatan=nama_kegiatan,
                jenjang_pendidikan_id=jenjang_id,
                tahun_ajaran_id=tahun_ajaran_id,
                jumlah_sks=jumlah_sks,
                total_jam_minggu=total_jam_minggu,
                target_jam=target_jam
            )
            kegiatan.save()
            
            messages.success(request, 'Kegiatan SKS berhasil ditambahkan')
            return redirect('data_sks')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
            return redirect('data_sks')
    
    return redirect('data_sks')

@login_required
def edit_kegiatan_sks(request, kegiatan_id):
    """View untuk mengedit kegiatan SKS"""
    if request.method == 'POST':
        try:
            kegiatan = get_object_or_404(Kegiatan_PA, id=kegiatan_id)
            
            # Update data
            kegiatan.nama_kegiatan = request.POST.get('nama_kegiatan', kegiatan.nama_kegiatan)
            kegiatan.jenjang_pendidikan_id = request.POST.get('jenjang_pendidikan', kegiatan.jenjang_pendidikan_id)
            kegiatan.tahun_ajaran_id = request.POST.get('tahun_ajaran', kegiatan.tahun_ajaran_id)
            kegiatan.jumlah_sks = request.POST.get('jumlah_sks', kegiatan.jumlah_sks)
            kegiatan.total_jam_minggu = request.POST.get('total_jam_minggu', kegiatan.total_jam_minggu)
            kegiatan.target_jam = request.POST.get('target_jam', kegiatan.target_jam)
            
            kegiatan.save()
            messages.success(request, 'Kegiatan SKS berhasil diperbarui')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('data_sks')

@login_required
def hapus_kegiatan_sks(request, kegiatan_id):
    """View untuk menghapus kegiatan SKS"""
    if request.method == 'POST':
        try:
            kegiatan = get_object_or_404(Kegiatan_PA, id=kegiatan_id)
            
            # Cek apakah kegiatan sudah digunakan
            from .models import Status_Pemenuhan_SKS
            if Status_Pemenuhan_SKS.objects.filter(kegiatan_pa=kegiatan).exists():
                messages.error(request, 'Tidak dapat menghapus kegiatan yang sudah digunakan')
                return redirect('data_sks')
            
            kegiatan.delete()
            messages.success(request, 'Kegiatan SKS berhasil dihapus')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('data_sks')

@login_required
def get_detail_kegiatan(request, kegiatan_id):
    """API untuk mendapatkan detail kegiatan (JSON response)"""
    try:
        kegiatan = get_object_or_404(
            Kegiatan_PA.objects.select_related('jenjang_pendidikan', 'tahun_ajaran'),
            id=kegiatan_id
        )
        
        response_data = {
            'success': True,
            'kegiatan': {
                'id': kegiatan.id,
                'nama_kegiatan': kegiatan.nama_kegiatan,
                'jenjang_pendidikan': {
                    'id': kegiatan.jenjang_pendidikan.id,
                    'nama': kegiatan.jenjang_pendidikan.nama_jenjang
                },
                'tahun_ajaran': {
                    'id': kegiatan.tahun_ajaran.id if kegiatan.tahun_ajaran else None,
                    'nama': kegiatan.tahun_ajaran.nama_tahun_ajaran if kegiatan.tahun_ajaran else None
                },
                'jumlah_sks': kegiatan.jumlah_sks,
                'total_jam_minggu': kegiatan.total_jam_minggu,
                'target_jam': kegiatan.target_jam
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def tambah_tahun_ajaran(request):
    """View untuk menambah tahun ajaran baru"""
    if request.method == 'POST':
        try:
            nama_tahun_ajaran = request.POST.get('nama_tahun_ajaran')
            tanggal_mulai = request.POST.get('tanggal_mulai')
            tanggal_selesai = request.POST.get('tanggal_selesai')
            
            if not nama_tahun_ajaran or not tanggal_mulai or not tanggal_selesai:
                messages.error(request, 'Semua field harus diisi')
                return redirect('data_sks')
            
            tahun_ajaran = Tahun_Ajaran(
                nama_tahun_ajaran=nama_tahun_ajaran,
                tanggal_mulai=tanggal_mulai,
                tanggal_selesai=tanggal_selesai,
                status_aktif='nonaktif'
            )
            tahun_ajaran.save()
            
            messages.success(request, 'Tahun ajaran berhasil ditambahkan')
            return redirect('data_sks')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('data_sks')

@login_required
def edit_tahun_ajaran(request, tahun_id):
    """View untuk mengedit tahun ajaran"""
    if request.method == 'POST':
        try:
            tahun_ajaran = get_object_or_404(Tahun_Ajaran, id=tahun_id)
            
            tahun_ajaran.nama_tahun_ajaran = request.POST.get('nama_tahun_ajaran', tahun_ajaran.nama_tahun_ajaran)
            tahun_ajaran.tanggal_mulai = request.POST.get('tanggal_mulai', tahun_ajaran.tanggal_mulai)
            tahun_ajaran.tanggal_selesai = request.POST.get('tanggal_selesai', tahun_ajaran.tanggal_selesai)
            
            tahun_ajaran.save()
            messages.success(request, 'Tahun ajaran berhasil diperbarui')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('data_sks')

@login_required
def hapus_tahun_ajaran(request, tahun_id):
    """View untuk menghapus tahun ajaran"""
    if request.method == 'POST':
        try:
            tahun_ajaran = get_object_or_404(Tahun_Ajaran, id=tahun_id)
            
            # Cek apakah tahun ajaran digunakan di kegiatan
            if Kegiatan_PA.objects.filter(tahun_ajaran=tahun_ajaran).exists():
                messages.error(request, 'Tidak dapat menghapus tahun ajaran yang sudah digunakan')
                return redirect('data_sks')
            
            tahun_ajaran.delete()
            messages.success(request, 'Tahun ajaran berhasil dihapus')
            
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return redirect('data_sks')

@login_required
def get_detail_tahun_ajaran(request, tahun_id):
    """API untuk mendapatkan detail tahun ajaran"""
    try:
        tahun_ajaran = get_object_or_404(Tahun_Ajaran, id=tahun_id)
        
        response_data = {
            'success': True,
            'tahun_ajaran': {
                'id': tahun_ajaran.id,
                'nama_tahun_ajaran': tahun_ajaran.nama_tahun_ajaran,
                'tanggal_mulai': tahun_ajaran.tanggal_mulai.strftime('%Y-%m-%d'),
                'tanggal_selesai': tahun_ajaran.tanggal_selesai.strftime('%Y-%m-%d'),
                'status_aktif': tahun_ajaran.status_aktif
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def aktifkan_tahun_ajaran(request):
    """View untuk mengaktifkan tahun ajaran"""
    if request.method == 'POST':
        try:
            tahun_id = request.POST.get('tahun_id')
            
            # Nonaktifkan semua tahun ajaran terlebih dahulu
            Tahun_Ajaran.objects.update(status_aktif='nonaktif')
            
            # Aktifkan tahun ajaran yang dipilih
            tahun_ajaran = get_object_or_404(Tahun_Ajaran, id=tahun_id)
            tahun_ajaran.status_aktif = 'aktif'
            tahun_ajaran.save()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

@login_required
def rekap_presensi(request):
    """View untuk rekap presensi admin dengan filter"""
    
    if not (request.user.role == 'admin' or request.user.is_superuser):
        messages.error(request, 'Akses ditolak. Halaman untuk admin saja.')
        return redirect('login')
    
    try:
        tahun_ajaran_aktif = Tahun_Ajaran.objects.get(status_aktif='aktif')
        semester_aktif_info = f"{tahun_ajaran_aktif.nama_tahun_ajaran} (Aktif)"
    except Tahun_Ajaran.DoesNotExist:
        semester_aktif_info = "Tidak ada Tahun Ajaran Aktif"
    
    # 2. Gunakan form yang sudah ada di forms.py
    form = FilterRekapPresensiForm(request.GET or None)
    
    # 3. Query awal dengan semua relasi yang dibutuhkan
    presensi_list = Presensi.objects.select_related(
        'mahasiswa__user',
        'mahasiswa__jenjang_pendidikan',
        'kegiatan_pa'  # PASTIKAN INI DIPILIH
    ).all().order_by('-tanggal_presensi', '-jam_checkin')
    
    # 4. Terapkan filter jika form valid
    if form.is_valid():
        tanggal_mulai = form.cleaned_data.get('tanggal_mulai')
        tanggal_selesai = form.cleaned_data.get('tanggal_selesai')
        tingkatan = form.cleaned_data.get('tingkatan')
        kegiatan = form.cleaned_data.get('kegiatan')
        
        # Filter tanggal
        if tanggal_mulai:
            presensi_list = presensi_list.filter(tanggal_presensi__gte=tanggal_mulai)
        if tanggal_selesai:
            presensi_list = presensi_list.filter(tanggal_presensi__lte=tanggal_selesai)
        
        # Filter tingkatan - PERBAIKAN INI
        if tingkatan:  
        # Jika menggunakan ModelChoiceField, tingkatan adalah objek
            presensi_list = presensi_list.filter(
                mahasiswa__jenjang_pendidikan=tingkatan  # Langsung bandingkan dengan objek
            )
        
        # Filter kegiatan - gunakan many-to-many pada mahasiswa (karena sistem agregat)
        if kegiatan:
            presensi_list = presensi_list.filter(mahasiswa__kegiatan_pa=kegiatan)

    # 5. Default: 7 hari terakhir jika tidak ada filter tanggal
    if not request.GET.get('tanggal_mulai') and not request.GET.get('tanggal_selesai'):
        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=7)
        presensi_list = presensi_list.filter(
            tanggal_presensi__gte=default_start,
            tanggal_presensi__lte=default_end
        )
        # Set initial form values
        form.initial = {
            'tanggal_mulai': default_start,
            'tanggal_selesai': default_end
        }
    
    # 6. Siapkan data untuk template
    data_presensi = []
    
    # Prefetch untuk optimasi ManyToMany
    presensi_list = presensi_list.prefetch_related('mahasiswa__kegiatan_pa')
    
    for presensi in presensi_list:
        # Hitung durasi
        durasi_str = "-"
        if presensi.jam_checkin and presensi.jam_checkout:
            try:
                checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
                checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
                
                if checkout_dt < checkin_dt:
                    checkout_dt += timedelta(days=1)
                
                delta = checkout_dt - checkin_dt
                total_seconds = delta.total_seconds()
                
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                
                if hours > 0:
                    durasi_str = f"{hours}j {minutes}m" if minutes > 0 else f"{hours}j"
                elif minutes > 0:
                    durasi_str = f"{minutes}m"
                else:
                    durasi_str = "0m"
                    
            except Exception as e:
                durasi_str = "Error"
        
        # Ambil tingkatan dari jenjang pendidikan mahasiswa
        tingkatan_value = "-"
        if presensi.mahasiswa.jenjang_pendidikan:
            tingkatan_value = presensi.mahasiswa.jenjang_pendidikan.nama_jenjang
        
        # Ambil SEMUA kegiatan PA yang diambil mahasiswa (sesuai permintaan user)
        kegiatan_pa_list = presensi.mahasiswa.kegiatan_pa.all()
        if kegiatan_pa_list:
            kegiatan_pa_value = ", ".join([k.nama_kegiatan for k in kegiatan_pa_list])
        else:
            kegiatan_pa_value = "-"
        
        data_presensi.append({
            'tanggal': presensi.tanggal_presensi,
            'nrp': presensi.mahasiswa.nim,
            'nama': presensi.mahasiswa.user.nama_lengkap,
            'tingkatan': tingkatan_value,  # Sekarang harus muncul
            'kegiatan_pa': kegiatan_pa_value,  # Sekarang hanya 1 kegiatan sesuai presensi
            'check_in': presensi.jam_checkin,
            'check_out': presensi.jam_checkout,
            'durasi': durasi_str,
        })
    
    # 7. Konteks untuk template
    context = {
        'form': form,
        'data_presensi': data_presensi,
        'semester': semester_aktif_info,
        'total_presensi': len(data_presensi),
    }
    
    return render(request, 'admin/rekap_presensi.html', context)
