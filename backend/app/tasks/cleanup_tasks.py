"""
Cleanup Background Tasks

Periodic tasks for housekeeping (temp file cleanup, etc.)
"""

import logging
import time
from pathlib import Path

from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="codementor.cleanup-uploads")
def cleanup_uploads_task():
    """
    Delete uploaded files older than UPLOAD_RETENTION_HOURS.

    Runs periodically via Celery Beat to prevent disk accumulation.
    Files are safe to delete after indexing completes (or fails permanently),
    since all content is stored in Qdrant vectors.
    """
    upload_dir = Path(settings.UPLOAD_DIR)

    if not upload_dir.exists():
        return []

    cutoff = time.time() - (settings.UPLOAD_RETENTION_HOURS * 3600)
    deleted = []

    for f in upload_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted.append(f.name)
            except OSError as e:
                logger.warning(f"⚠️  Could not delete {f.name}: {e}")

    if deleted:
        logger.info(f"🗑️  Cleaned up {len(deleted)} expired uploads")

    return deleted
