from celery import Celery
import config
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    'dating_bot',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

logger.info("Celery app initialized")