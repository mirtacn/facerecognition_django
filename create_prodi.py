import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pa_app.settings')
django.setup()

from accounts.models import Jenjang_Pendidikan, Prodi

print("=== MEMBUAT DATA PRODI ===\n")

# Ambil jenjang
d3 = Jenjang_Pendidikan.objects.get(id=1)
d4 = Jenjang_Pendidikan.objects.get(id=2)
s2 = Jenjang_Pendidikan.objects.get(id=4)

# Data Prodi D3
prodi_d3 = [
    ('D3-TE', 'Teknik Elektronika'),
    ('D3-TT', 'Teknik Telekomunikasi'),
    ('D3-TEI', 'Teknik Elektro Industri'),
    ('D3-TI', 'Teknik Informatika'),
    ('D3-TK', 'Teknik Komputer'),
    ('D3-TM', 'Teknik Mekatronika'),
    ('D3-MMB', 'Teknologi Multimedia Broadcasting'),
]

for kode, nama in prodi_d3:
    p, created = Prodi.objects.get_or_create(
        kode_prodi=kode,
        defaults={
            'jenjang': d3,
            'nama_prodi': nama,
            'nama_singkat': nama,
            'is_active': True
        }
    )
    if created:
        print(f"Created: {kode} - {nama}")

# Data Prodi D4
prodi_d4 = [
    ('D4-TE', 'Teknik Elektronika'),
    ('D4-TT', 'Teknik Telekomunikasi'),
    ('D4-TEI', 'Teknik Elektro Industri'),
    ('D4-TI', 'Teknik Informatika'),
    ('D4-TK', 'Teknik Komputer'),
    ('D4-TM', 'Teknik Mekatronika'),
    ('D4-SPE', 'Sistem Pembangkit Energi'),
    ('D4-TG', 'Teknologi Game'),
    ('D4-TRI', 'Teknologi Rekayasa Internet'),
    ('D4-TRM', 'Teknologi Rekayasa Multimedia'),
    ('D4-SDT', 'Sains Data Terapan'),
    ('D4-TRPM', 'Teknologi Rekayasa Perancangan Manufaktur'),
    ('D4-BD', 'Bisnis Digital'),
]

for kode, nama in prodi_d4:
    p, created = Prodi.objects.get_or_create(
        kode_prodi=kode,
        defaults={
            'jenjang': d4,
            'nama_prodi': nama,
            'nama_singkat': nama,
            'is_active': True
        }
    )
    if created:
        print(f"Created: {kode} - {nama}")

# Data Prodi S2
prodi_s2 = [
    ('S2-TE', 'Teknik Elektro'),
    ('S2-TIK', 'Teknik Informatika dan Komputer'),
]

for kode, nama in prodi_s2:
    p, created = Prodi.objects.get_or_create(
        kode_prodi=kode,
        defaults={
            'jenjang': s2,
            'nama_prodi': nama,
            'nama_singkat': nama,
            'is_active': True
        }
    )
    if created:
        print(f"Created: {kode} - {nama}")

print("\n=== DAFTAR PRODI SAAT INI ===")
for p in Prodi.objects.all().select_related('jenjang'):
    print(f"{p.kode_prodi} -> {p.jenjang.nama_jenjang} | {p.nama_prodi}")

print(f"\nTotal Prodi: {Prodi.objects.count()}")
print("\n=== SELESAI ===")