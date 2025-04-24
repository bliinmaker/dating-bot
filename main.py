import logging
from celery.schedules import crontab
from celery_app import celery_app
from bot import main as bot_main
import config
from rating_service import update_all_ratings
from datetime import datetime, timedelta
from models import Session, User, Match

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=config.LOG_FILE
)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(minute=0, hour='*'),
        update_all_ratings.s()
    )

    sender.add_periodic_task(
        crontab(minute=0, hour=0),
        cleanup_expired_data.s()
    )


@celery_app.task
def cleanup_expired_data():
    """Clean up expired user data and sessions"""
    session = Session()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        inactive_matches = session.query(Match).filter(
            Match.created_at < cutoff_date,
            Match.status == "active",
            Match.initiated_chat == False
        ).all()

        for match in inactive_matches:
            match.status = "archived"

        session.commit()
        logging.info(f"Archived {len(inactive_matches)} inactive matches")

        return {"success": True, "archived_matches": len(inactive_matches)}
    except Exception as e:
        session.rollback()
        logging.error(f"Error cleaning up expired data: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()


if __name__ == "__main__":
    bot_main()