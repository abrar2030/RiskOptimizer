"""
Celery application configuration for RiskOptimizer.
Handles asynchronous task processing for heavy computations.
"""

import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Dict

import redis
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
celery_app = Celery(
    "src",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "src.tasks.risk_tasks",
        "src.tasks.portfolio_tasks",
        "src.tasks.report_tasks",
        "src.tasks.maintenance_tasks",
    ],
)
celery_app.conf.update(
    task_routes={
        "src.tasks.risk_tasks.*": {"queue": "risk_calculations"},
        "src.tasks.portfolio_tasks.*": {"queue": "portfolio_operations"},
        "src.tasks.report_tasks.*": {"queue": "report_generation"},
        "src.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("risk_calculations", routing_key="risk"),
        Queue("portfolio_operations", routing_key="portfolio"),
        Queue("report_generation", routing_key="reports"),
        Queue("maintenance", routing_key="maintenance"),
    ),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_send_sent_event=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    task_default_retry_delay=60,
    task_max_retries=3,
    beat_schedule={
        "cleanup-expired-tasks": {
            "task": "src.tasks.maintenance_tasks.cleanup_expired_tasks",
            "schedule": crontab(minute=0, hour=2),
        },
        "update-market-data": {
            "task": "src.tasks.maintenance_tasks.update_market_data",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "generate-daily-reports": {
            "task": "src.tasks.report_tasks.generate_daily_reports",
            "schedule": crontab(minute=0, hour=8),
        },
        "cache-warmup": {
            "task": "src.tasks.maintenance_tasks.cache_warmup",
            "schedule": crontab(minute=0, hour=6),
        },
    },
)
celery_app.conf.update(
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None


def get_task_status(task_id: str) -> object:
    """Get the status of a task by ID."""
    return celery_app.AsyncResult(task_id)


def cancel_task(task_id: str) -> object:
    """Cancel a task by ID."""
    celery_app.control.revoke(task_id, terminate=True)


def get_active_tasks() -> object:
    """Get list of active tasks."""
    inspect = celery_app.control.inspect()
    return inspect.active()


def get_scheduled_tasks() -> object:
    """Get list of scheduled tasks."""
    inspect = celery_app.control.inspect()
    return inspect.scheduled()


def get_worker_stats() -> object:
    """Get worker statistics."""
    inspect = celery_app.control.inspect()
    return inspect.stats()


class TaskResultManager:
    """Manages task results and provides utilities for task monitoring."""

    def __init__(self) -> None:
        self.redis_client = redis_client

    def store_task_progress(
        self, task_id: str, progress_data: Dict[str, Any]
    ) -> object:
        """Store task progress information."""
        if not self.redis_client:
            return
        try:
            key = f"task_progress:{task_id}"
            self.redis_client.hset(key, mapping=progress_data)
            self.redis_client.expire(key, 3600)
        except Exception as e:
            logger.warning(f"Could not store task progress: {e}")

    def get_task_progress(self, task_id: str) -> object:
        """Get task progress information."""
        if not self.redis_client:
            return {}
        try:
            key = f"task_progress:{task_id}"
            return self.redis_client.hgetall(key)
        except Exception:
            return {}

    def store_task_metadata(self, task_id: str, metadata: Dict[str, Any]) -> object:
        """Store task metadata."""
        if not self.redis_client:
            return
        try:
            key = f"task_metadata:{task_id}"
            self.redis_client.hset(key, mapping=metadata)
            self.redis_client.expire(key, 86400)
        except Exception as e:
            logger.warning(f"Could not store task metadata: {e}")

    def get_task_metadata(self, task_id: str) -> object:
        """Get task metadata."""
        if not self.redis_client:
            return {}
        try:
            key = f"task_metadata:{task_id}"
            return self.redis_client.hgetall(key)
        except Exception:
            return {}

    def cleanup_expired_task_data(self) -> int:
        """Clean up expired task data by scanning for orphaned task keys."""
        if not self.redis_client:
            return 0
        deleted = 0
        try:
            for prefix in ("task_progress:*", "task_metadata:*"):
                keys = self.redis_client.keys(prefix)
                for key in keys:
                    ttl = self.redis_client.ttl(key)
                    if ttl == -1:
                        self.redis_client.expire(key, 3600)
                    elif ttl == -2:
                        deleted += 1
        except Exception as e:
            logger.warning(f"Error during task data cleanup: {e}")
        return deleted


task_result_manager = TaskResultManager()


class TaskError(Exception):
    """Base exception for task errors."""


class TaskTimeoutError(TaskError):
    """Exception raised when a task times out."""


class TaskValidationError(TaskError):
    """Exception raised when task input validation fails."""


def task_with_progress(**kwargs) -> object:
    """
    Decorator for Celery tasks that report progress via TaskResultManager.

    The decorated function must accept ``self`` as its first argument (a Celery
    task instance or a mock for testing).  The decorator registers the function
    as a plain (non-bound) Celery task; the ``self`` argument is passed by the
    caller or by the Celery worker via ``Task.apply()``.
    """

    def decorator(func):
        @celery_app.task(**kwargs)
        @wraps(func)
        def wrapper(*args, **kw):
            # args[0] is the task self (mock in tests, Celery task in prod)
            bound_self = args[0] if args else None
            task_id = getattr(getattr(bound_self, "request", None), "id", "unknown")
            try:
                task_result_manager.store_task_metadata(
                    task_id,
                    {
                        "task_name": func.__name__,
                        "started_at": str(datetime.utcnow()),
                        "status": "STARTED",
                    },
                )
                result = func(*args, **kw)
                task_result_manager.store_task_metadata(
                    task_id,
                    {"completed_at": str(datetime.utcnow()), "status": "SUCCESS"},
                )
                return result
            except Exception as exc:
                task_result_manager.store_task_metadata(
                    task_id,
                    {
                        "failed_at": str(datetime.utcnow()),
                        "status": "FAILURE",
                        "error": str(exc),
                    },
                )
                raise

        return wrapper

    return decorator


if __name__ == "__main__":
    celery_app.start()
