from django.apps import AppConfig
import os

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        # 🔥 AKTIFKAN SCHEDULER 🔥
        if os.environ.get('RUN_MAIN') or not os.environ.get('RUN_MAIN'):
            try:
                from .scheduler import start_scheduler
                start_scheduler()
                print("✅ Accounts app ready - Scheduler is ENABLED")
            except Exception as e:
                print(f"⚠️ Scheduler error: {e}")
        else:
            print("✅ Accounts app ready - Scheduler not started (migration mode)")