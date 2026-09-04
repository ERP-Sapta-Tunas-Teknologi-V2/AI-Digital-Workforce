from apscheduler.schedulers.blocking import BlockingScheduler
from sync import sync_documents
from sync import delete_expired_logs

scheduler = BlockingScheduler(timezone="Asia/Jakarta")

DYNAMIC_CATEGORIES = {"berita"}
STATIC_CATEGORIES = {"stt"}

for category in DYNAMIC_CATEGORIES:
    scheduler.add_job(
        sync_documents,
        "cron",
        hour=0,  # setiap hari pukul 00.00
        minute=0,
        args=[category],
        id="sync_berita_daily",
        replace_existing=True
    )

for category in STATIC_CATEGORIES:
    scheduler.add_job(
        sync_documents,
        "cron",
        day_of_week="mon",  # setiap hari Senin
        hour=1,  # pukul 01.00
        minute=0,
        args=[category],
        id=f"sync_{category}_weekly",
        replace_existing=True
    )

delete_expired_logs()
scheduler.add_job(
    delete_expired_logs,
    "cron",
    hour=2,  # setiap hari pukul 02.00
    minute=0,
    id="delete_expired_query_logs",
    replace_existing=True
)

print("Scheduler started.")
scheduler.start()