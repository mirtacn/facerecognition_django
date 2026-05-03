# accounts/management/commands/init_master_data.py

from django.core.management.base import BaseCommand
from accounts.models import Jenjang_Pendidikan, Semester, Prodi, Dosen, Kegiatan_PA, Tahun_Ajaran, Kelas
from datetime import date

class Command(BaseCommand):
    help = 'Initialize ALL master data from actual campus data'

    def handle(self, *args, **options):
        self.stdout.write("="*60)
        self.stdout.write("INITIALIZING MASTER DATA FROM CAMPUS DATA")
        self.stdout.write("="*60 + "\n")
        
        # =========================================================
        # 1. JENJANG PENDIDIKAN
        # =========================================================
        self.stdout.write("📌 [1/8] Creating Education Levels...")
        jenjang_data = ["D3 - Diploma 3", "D4 - Diploma 4", "LJ - Lanjut Jenjang", "S2 - Magister"]
        for nama in jenjang_data:
            j, created = Jenjang_Pendidikan.objects.get_or_create(nama_jenjang=nama)
            status = "✓" if created else "→"
            self.stdout.write(f"  {status} {nama}")
        
        # =========================================================
        # 2. SEMESTER (Sesuai jenjang)
        # =========================================================
        self.stdout.write("\n📌 [2/8] Creating Semesters...")
        
        for i in range(1, 7):
            Semester.objects.get_or_create(
                jenjang='D3',
                nomor_semester=i,
                defaults={'nama_semester': f"Semester {i}"}
            )
            self.stdout.write(f"  ✓ D3 - Semester {i}")
        
        for i in range(1, 9):
            Semester.objects.get_or_create(
                jenjang='D4',
                nomor_semester=i,
                defaults={'nama_semester': f"Semester {i}"}
            )
            self.stdout.write(f"  ✓ D4 - Semester {i}")
        
        for i in range(1, 5):
            Semester.objects.get_or_create(
                jenjang='S2',
                nomor_semester=i,
                defaults={'nama_semester': f"Semester {i}"}
            )
            self.stdout.write(f"  ✓ S2 - Semester {i}")
        
        # =========================================================
        # 3. PRODI (22 Program Studi)
        # =========================================================
        self.stdout.write("\n📌 [3/8] Creating Study Programs...")
        d3 = Jenjang_Pendidikan.objects.get(nama_jenjang="D3 - Diploma 3")
        d4 = Jenjang_Pendidikan.objects.get(nama_jenjang="D4 - Diploma 4")
        s2 = Jenjang_Pendidikan.objects.get(nama_jenjang="S2 - Magister")
        
        prodi_list = [
            (d3, 'D3-TE', 'Teknik Elektronika'),
            (d3, 'D3-TT', 'Teknik Telekomunikasi'),
            (d3, 'D3-TEI', 'Teknik Elektro Industri'),
            (d3, 'D3-TI', 'Teknik Informatika'),
            (d3, 'D3-TK', 'Teknik Komputer'),
            (d3, 'D3-TM', 'Teknik Mekatronika'),
            (d3, 'D3-MMB', 'Teknologi Multimedia Broadcasting'),
            (d4, 'D4-TE', 'Teknik Elektronika'),
            (d4, 'D4-TT', 'Teknik Telekomunikasi'),
            (d4, 'D4-TEI', 'Teknik Elektro Industri'),
            (d4, 'D4-TI', 'Teknik Informatika'),
            (d4, 'D4-TK', 'Teknik Komputer'),
            (d4, 'D4-TM', 'Teknik Mekatronika'),
            (d4, 'D4-SPE', 'Sistem Pembangkit Energi'),
            (d4, 'D4-TG', 'Teknologi Game'),
            (d4, 'D4-TRI', 'Teknologi Rekayasa Internet'),
            (d4, 'D4-TRM', 'Teknologi Rekayasa Multimedia'),
            (d4, 'D4-SDT', 'Sains Data Terapan'),
            (d4, 'D4-TRPM', 'Teknologi Rekayasa Perancangan Manufaktur'),
            (d4, 'D4-BD', 'Bisnis Digital'),
            (s2, 'S2-TE', 'Teknik Elektro'),
            (s2, 'S2-TIK', 'Teknik Informatika dan Komputer'),
        ]
        
        for jenjang, kode, nama in prodi_list:
            Prodi.objects.get_or_create(
                kode_prodi=kode,
                defaults={
                    'jenjang': jenjang,
                    'nama_prodi': nama,
                    'nama_singkat': nama,
                    'is_active': True
                }
            )
            self.stdout.write(f"  ✓ {kode} - {nama}")
        
        # =========================================================
        # 4. TAHUN AJARAN 2025/2026
        # =========================================================
        self.stdout.write("\n📌 [4/8] Creating Academic Year 2025/2026...")
        ta, created = Tahun_Ajaran.objects.get_or_create(
            nama_tahun_ajaran="2025/2026",
            defaults={
                'tanggal_mulai': date(2025, 8, 1),
                'tanggal_selesai': date(2026, 7, 31),
                'status_aktif': 'aktif'
            }
        )
        self.stdout.write(f"  ✓ {ta.nama_tahun_ajaran}")
        
        # =========================================================
        # 5. DOSEN
        # =========================================================
        self.stdout.write("\n📌 [5/8] Creating Lecturers...")
        dosen_list = [
            ('197308162001121001', 'Ali Ridho Barakbah, S.Kom, Ph.D', 'Teknik Informatika'),
            ('196904041995121002', 'Prof. Iwan Syarif, S.Kom, M.Kom, M.Sc, Ph.D', 'Teknik Informatika'),
            ('198108082005011001', 'Prof. M Udin Harus Al Rasyid, S.Kom, Ph.D', 'Teknik Informatika'),
            ('198508072015041003', 'Nur Rosyid Mubtadai, S.Kom., MT.', 'Teknik Informatika'),
            ('197505302003121001', 'Ahmad Syauqi Ahsan, S.Kom., M.T', 'Teknik Informatika'),
            ('197811032005011002', 'Hero Yudo Martono, S.T, M.T', 'Teknik Informatika'),
            ('197609212003121002', 'Arif Basofi, S.Kom, M.T', 'Teknik Informatika'),
            ('198901292019031013', 'Fadilah Fahrul Hardiansyah, S.ST., M.Kom', 'Teknik Informatika'),
        ]
        
        for nip, nama, prodi in dosen_list:
            Dosen.objects.get_or_create(
                nip=nip,
                defaults={'nama_dosen': nama, 'prodi': prodi}
            )
            self.stdout.write(f"  ✓ {nama}")
        
        # =========================================================
        # 6. KEGIATAN PA
        # =========================================================
        self.stdout.write("\n📌 [6/8] Creating PA Activities...")
        
        ta_2025 = Tahun_Ajaran.objects.get(nama_tahun_ajaran="2025/2026")
        
        kegiatan_list = [
            ('D3 - Diploma 3', 'Proposal Proyek Akhir', 1, 3, 48),
            ('D3 - Diploma 3', 'Proyek Akhir', 4, 12, 192),
            ('D4 - Diploma 4', 'Proposal Proyek Akhir', 1, 3, 48),
            ('D4 - Diploma 4', 'Proyek Akhir - 1', 3, 9, 144),
            ('D4 - Diploma 4', 'Proyek Akhir - 2', 8, 24, 384),
            ('LJ - Lanjut Jenjang', 'Proposal Proyek Akhir', 1, 2, 32),
            ('LJ - Lanjut Jenjang', 'Proyek Akhir - 1', 3, 9, 144),
            ('LJ - Lanjut Jenjang', 'Proyek Akhir - 2', 8, 24, 384),
            ('S2 - Magister', 'Progres Tesis - 1', 2, 4, 64),
            ('S2 - Magister', 'Progres Tesis - 2', 2, 4, 64),
            ('S2 - Magister', 'Proposal Tesis', 1, 2, 32),
            ('S2 - Magister', 'Tesis Akhir', 6, 18, 288),
        ]
        
        for jenjang_nama, nama_kegiatan, sks, jam_minggu, target_jam in kegiatan_list:
            jenjang = Jenjang_Pendidikan.objects.get(nama_jenjang=jenjang_nama)
            Kegiatan_PA.objects.get_or_create(
                jenjang_pendidikan=jenjang,
                tahun_ajaran=ta_2025,
                nama_kegiatan=nama_kegiatan,
                defaults={
                    'jumlah_sks': sks,
                    'total_jam_minggu': jam_minggu,
                    'target_jam': target_jam
                }
            )
            self.stdout.write(f"  ✓ {jenjang_nama} - {nama_kegiatan} ({sks} SKS)")
                
        # =========================================================
        # 7. KELAS (Hanya A, B, C, D, E - tanpa relasi apapun)
        # =========================================================
        self.stdout.write("\n📌 [7/8] Creating Classes...")

        kelas_list = ['A', 'B', 'C', 'D', 'E']
        for nama in kelas_list:
            Kelas.objects.get_or_create(
                nama_kelas=nama,
                defaults={
                    'kode_kelas': nama,
                    'is_active': True
                }
            )
            self.stdout.write(f"  ✓ Kelas {nama}")

        total_kelas = Kelas.objects.count()
        self.stdout.write(f"  ✅ Total classes created: {total_kelas}")
        # =========================================================
        # 8. CREATE SUPERUSER ADMIN
        # =========================================================
        self.stdout.write("\n📌 [8/8] Creating Superuser Admin...")
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admin_nip = "198108082005011001"
        admin_password = "udin1981"
        admin_nama = "Prof. M Udin Harus Al Rasyid, S.Kom, Ph.D"
        admin_email = "udinharun@gmail.com"
        
        if not User.objects.filter(username=admin_nip).exists():
            User.objects.create_superuser(
                username=admin_nip,
                email=admin_email,
                password=admin_password,
                nrp=admin_nip,
                nama_lengkap=admin_nama,
                role="admin",
                status_akun="aktif",
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ Admin created: {admin_nip}"))
        else:
            self.stdout.write(f"  → Admin already exists: {admin_nip}")
        
        # =========================================================
        # SUMMARY
        # =========================================================
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("✅ ALL MASTER DATA INITIALIZED SUCCESSFULLY!"))
        self.stdout.write("="*60)
        self.stdout.write(f"  📊 Jenjang Pendidikan : {Jenjang_Pendidikan.objects.count()}")
        self.stdout.write(f"  📊 Semesters          : {Semester.objects.count()}")
        self.stdout.write(f"  📊 Prodi              : {Prodi.objects.count()}")
        self.stdout.write(f"  📊 Dosen              : {Dosen.objects.count()}")
        self.stdout.write(f"  📊 Kegiatan PA        : {Kegiatan_PA.objects.count()}")
        self.stdout.write(f"  📊 Kelas              : {Kelas.objects.count()}")
        self.stdout.write("="*60)
        self.stdout.write(self.style.SUCCESS("\n🎉 SISTEM SIAP DIGUNAKAN!"))