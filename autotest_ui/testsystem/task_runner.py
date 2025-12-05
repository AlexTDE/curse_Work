import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from celery import Task
from celery.exceptions import TimeoutError


logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionResult:
    """Результат запуска задачи (асинхронно или синхронно)."""

    mode: str
    task_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    @property
    def is_async(self) -> bool:
        return self.mode.startswith('async')

    @property
    def is_sync(self) -> bool:
        return self.mode.startswith('sync')


def _run_sync(task: Task, *args, **kwargs) -> TaskExecutionResult:
    """Выполняет задачу синхронно и возвращает результат."""
    eager_result = task.apply(args=args, kwargs=kwargs)
    return TaskExecutionResult(mode='sync', result=eager_result.get())


def run_task_with_fallback(task: Task, *args, **kwargs) -> TaskExecutionResult:
    """
    Пытается запустить задачу через Celery, а при необходимости выполняет её синхронно.

    Поведение управляется настройками:
    - TASKS_FORCE_SYNC: всегда выполнять задачи синхронно (по умолчанию True для dev/Windows)
    - TASKS_FALLBACK_TO_SYNC: если Celery недоступен, выполнить синхронно
    - TASKS_WAIT_FOR_RESULT: если >0, ждать завершения Celery-задачи указанное время
    """
    force_sync = getattr(settings, 'TASKS_FORCE_SYNC', False)
    fallback_sync = getattr(settings, 'TASKS_FALLBACK_TO_SYNC', True)
    wait_timeout = getattr(settings, 'TASKS_WAIT_FOR_RESULT', 0)

    if force_sync:
        logger.info("TASKS_FORCE_SYNC=1 — задача %s выполняется синхронно", task.name)
        return _run_sync(task, *args, **kwargs)

    try:
        async_result = task.apply_async(args=args, kwargs=kwargs)
        logger.info("Задача %s поставлена в очередь Celery (task_id=%s)", task.name, async_result.id)

        if wait_timeout > 0:
            try:
                value = async_result.get(timeout=wait_timeout)
                return TaskExecutionResult(
                    mode='async-completed',
                    task_id=async_result.id,
                    result=value,
                )
            except TimeoutError:
                logger.debug(
                    "Задача %s не завершилась за %s сек, продолжаем в фоне",
                    task.name,
                    wait_timeout,
                )

        return TaskExecutionResult(mode='async', task_id=async_result.id)
    except Exception as exc:
        logger.warning("Не удалось поставить задачу %s в Celery: %s", task.name, exc)
        if not fallback_sync:
            raise
        logger.info("Выполняем задачу %s синхронно (fallback).", task.name)
        fallback_result = _run_sync(task, *args, **kwargs)
        fallback_result.mode = 'sync-fallback'
        fallback_result.error = str(exc)
        return fallback_result

