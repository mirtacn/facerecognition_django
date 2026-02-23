# cleanup_duplicate_presensi.py
import os
import django
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pa_app.settings')
django.setup()

from accounts.models import Presensi, Mahasiswa
from django.db.models import Count, Q
from django.utils import timezone

def cleanup_duplicate_presensi():
    """
    Membersihkan data presensi duplikat dan memastikan hanya 1 session aktif per hari
    """
    print("=" * 60)
    print("MEMBERSIHKAN DATA PRESENSI DUPLIKAT")
    print("=" * 60)
    
    # Cari semua mahasiswa
    mahasiswa_list = Mahasiswa.objects.all()
    
    total_fixed = 0
    
    for mahasiswa in mahasiswa_list:
        print(f"\nMemproses mahasiswa: {mahasiswa.user.nama_lengkap} ({mahasiswa.nim})")
        
        # Cek presensi per tanggal
        presensi_per_tanggal = Presensi.objects.filter(
            mahasiswa=mahasiswa
        ).values('tanggal_presensi').annotate(
            total=Count('id')
        ).filter(total__gt=1)
        
        for item in presensi_per_tanggal:
            tanggal = item['tanggal_presensi']
            total = item['total']
            
            print(f"  Tanggal {tanggal}: ditemukan {total} record")
            
            # Ambil semua presensi untuk tanggal ini, urutkan dari yang terbaru
            presensi_list = Presensi.objects.filter(
                mahasiswa=mahasiswa,
                tanggal_presensi=tanggal
            ).order_by('-jam_checkin', '-id')
            
            # Yang pertama (terbaru) akan kita pertahankan jika belum checkout
            # Sisanya akan kita checkout paksa atau hapus
            for i, presensi in enumerate(presensi_list):
                if i == 0:
                    # Record pertama - pertahankan
                    status = "AKTIF" if not presensi.jam_checkout else "SELESAI"
                    print(f"    Record ke-{i+1} (ID: {presensi.id}): Check-in {presensi.jam_checkin}, Check-out {presensi.jam_checkout} - [{status}] - DIPERTAHANKAN")
                else:
                    # Record duplikat - perbaiki
                    if not presensi.jam_checkout:
                        # Yang belum checkout, kita checkout paksa
                        # Gunakan waktu checkout dari record pertama jika ada
                        checkout_time = presensi_list[0].jam_checkout if presensi_list[0].jam_checkout else (timezone.localtime(timezone.now())).time()
                        
                        presensi.jam_checkout = checkout_time
                        presensi.session_status = 'auto_checkout'
                        presensi.save()
                        
                        print(f"    Record ke-{i+1} (ID: {presensi.id}): CHECKOUT PAKSA menjadi {checkout_time}")
                        total_fixed += 1
                    else:
                        # Yang sudah checkout, biarkan saja
                        print(f"    Record ke-{i+1} (ID: {presensi.id}): sudah checkout - DIBIARKAN")
    
    print("\n" + "=" * 60)
    print(f"SELESAI! Total {total_fixed} record diperbaiki.")
    print("=" * 60)

def check_active_sessions():
    """
    Mengecek session yang masih aktif dan mematikannya jika perlu
    """
    print("\n" + "=" * 60)
    print("MENGECEK SESSION AKTIF")
    print("=" * 60)
    
    # Cari semua session aktif (belum checkout)
    active_sessions = Presensi.objects.filter(
        jam_checkout__isnull=True
    ).select_related('mahasiswa__user')
    
    print(f"Ditemukan {active_sessions.count()} session aktif\n")
    
    now_local = timezone.localtime(timezone.now())
    
    for session in active_sessions:
        # Hitung durasi
        checkin_dt = datetime.combine(session.tanggal_presensi, session.jam_checkin)
        checkin_aware = timezone.make_aware(checkin_dt) if timezone.is_naive(checkin_dt) else checkin_dt
        
        duration = now_local - checkin_aware
        hours = duration.total_seconds() / 3600
        
        print(f"Mahasiswa: {session.mahasiswa.user.nama_lengkap}")
        print(f"  Tanggal: {session.tanggal_presensi}")
        print(f"  Check-in: {session.jam_checkin}")
        print(f"  Durasi: {duration}")
        print(f"  Status: {session.session_status}")
        
        # Jika session sudah lebih dari 24 jam, auto checkout
        if hours > 24:
            print(f"  ⚠️ Session > 24 jam, melakukan auto checkout...")
            session.jam_checkout = now_local.time()
            session.session_status = 'auto_checkout'
            session.save()
            print(f"  ✅ Checkout paksa menjadi {now_local.time()}")
        
        print()

if __name__ == "__main__":
    cleanup_duplicate_presensi()
    check_active_sessions()