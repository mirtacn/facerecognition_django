# accounts/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import register_events, DjangoJobStore
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Presensi, Durasi
import logging

logger = logging.getLogger(__name__)

def auto_checkout_expired_sessions():
    """
    Job untuk auto checkout session waiting_monitoring yang sudah lewat deadline
    """
    now = timezone.now()
    
    # Cari session yang masih waiting_monitoring dan sudah lewat deadline
    expired_sessions = Presensi.objects.filter(
        session_status='waiting_monitoring',
        monitoring_deadline__lte=now,
        jam_checkout__isnull=True
    )
    
    count = 0
    for presensi in expired_sessions:
        print(f"[SCHEDULER] 🔴 AUTO CHECKOUT: Session {presensi.id} - Deadline: {presensi.monitoring_deadline}")
        
        # Lakukan auto checkout
        presensi.session_status = 'auto_checkout'
        presensi.jam_checkout = now.time()
        presensi.consecutive_failures = 0
        
        # Hitung durasi
        checkin_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkin)
        checkout_dt = datetime.combine(presensi.tanggal_presensi, presensi.jam_checkout)
        if checkout_dt < checkin_dt:
            checkout_dt += timedelta(days=1)
        durasi = checkout_dt - checkin_dt
        
        Durasi.objects.update_or_create(
            presensi=presensi,
            defaults={'waktu_durasi': durasi}
        )
        
        presensi.save()
        count += 1
    
    if count > 0:
        print(f"[SCHEDULER] ✅ Auto-checkout {count} expired sessions")
    else:
        print(f"[SCHEDULER] Tidak ada session expired - {now.strftime('%H:%M:%S')}")

def start_scheduler():
    """
    Memulai scheduler untuk auto checkout
    """
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    
    # Jalankan setiap 1 menit
    scheduler.add_job(
        auto_checkout_expired_sessions,
        trigger=IntervalTrigger(minutes=1),
        id="auto_checkout_expired_sessions",
        max_instances=1,
        replace_existing=True,
    )
    
    register_events(scheduler)
    scheduler.start()
    print("[SCHEDULER] ✅ Scheduler started - Auto checkout akan berjalan setiap 1 menit")