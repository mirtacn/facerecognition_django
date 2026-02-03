# fix_presensi_aggregate.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pa_app.settings')
django.setup()

from accounts.models import Presensi
from django.db import transaction

def set_presensi_kegiatan_null():
    """
    Set semua kegiatan_pa di presensi menjadi NULL
    Karena sistem sekarang agregat
    """
    print("Mengubah semua presensi ke mode agregat (kegiatan_pa = NULL)...")
    
    with transaction.atomic():
        # Set semua presensi menjadi NULL
        updated = Presensi.objects.all().update(kegiatan_pa=None)
        
        print(f"Berhasil mengubah {updated} data presensi")
        print("Sistem sekarang menggunakan mode AGREGAT (total gabungan)")
        print("Progress SKS dihitung dari total durasi semua presensi")

if __name__ == "__main__":
    set_presensi_kegiatan_null()