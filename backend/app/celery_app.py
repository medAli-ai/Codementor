"""
Celery Application Configuration

This file configures the Celery worker for background tasks.
Tasks are queued in Redis and processed by Celery workers.
"""
from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "codementor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.rag_tasks', 'app.tasks.cleanup_tasks']  # Import task modules
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # Soft limit at 25 minutes
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
    beat_schedule={
        'cleanup-expired-uploads': {
            'task': 'codementor.cleanup-uploads',
            'schedule': 3600.0,  # every hour
        },
    }
)

# Optional: Configure result expiration
celery_app.conf.result_expires = 3600  # Results expire after 1 hour

if __name__ == '__main__':
    celery_app.start()
