import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.scraper import run_scrape
from backend.models import init_db, query_notices
from backend.notifier import send_daily_digest

log = logging.getLogger(__name__)

scheduler = BlockingScheduler()


def scrape_and_notify():
    """爬取 + 新公告邮件推送"""
    log.info("=== 定时任务触发：爬取 + 推送 ===")
    try:
        # 执行爬取
        new_count = run_scrape()

        # 查询今日新入库且未过期的公告
        today = datetime.now().strftime("%Y-%m-%d")
        all_notices = query_notices(skip_expired=True)
        new_notices = [n for n in all_notices if n.get("created_at", "").startswith(today)]

        if new_notices:
            log.info("本次新入库未过期公告 %d 条，准备推送邮件", len(new_notices))
            send_daily_digest(new_notices)
        else:
            log.info("本次无新入库公告，跳过邮件推送")
    except Exception as e:
        log.error("定时任务异常: %s", e)


def schedule_jobs():
    scheduler.add_job(
        scrape_and_notify,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0),
        id="daily_scrape_notify",
        name="工作日早9点爬取+推送",
        replace_existing=True,
    )
    log.info("定时任务已配置：工作日 09:00 自动爬取并推送")


def start_scheduler():
    schedule_jobs()
    log.info("调度器启动，等待触发...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("调度器停止")


if __name__ == "__main__":
    start_scheduler()
