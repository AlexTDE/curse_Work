"""
Утилиты для работы с CI/CD интеграцией
"""
import logging
from typing import List

from ..models import Run

logger = logging.getLogger(__name__)


def get_runs_by_ci_job(ci_job_id: str) -> List[Run]:
    """Получение всех прогонов по CI job ID"""
    return Run.objects.filter(ci_job_id=ci_job_id).order_by('-started_at')


def get_ci_status_summary(ci_job_id: str) -> dict:
    """
    Получение сводки статусов для CI/CD системы
    
    Returns:
        {
            'total_runs': int,
            'finished': int,
            'failed': int,
            'processing': int,
            'queued': int,
            'overall_status': str,  # 'success', 'failure', 'running', 'pending'
            'coverage_avg': float,
            'defects_count': int,
        }
    """
    runs = get_runs_by_ci_job(ci_job_id)
    
    if not runs.exists():
        return {
            'total_runs': 0,
            'finished': 0,
            'failed': 0,
            'processing': 0,
            'queued': 0,
            'overall_status': 'unknown',
            'coverage_avg': 0.0,
            'defects_count': 0,
        }
    
    total = runs.count()
    finished = runs.filter(status='finished').count()
    failed = runs.filter(status='failed').count()
    processing = runs.filter(status='processing').count()
    queued = runs.filter(status='queued').count()
    
    # Определяем общий статус
    if failed > 0:
        overall_status = 'failure'
    elif processing > 0 or queued > 0:
        overall_status = 'running'
    elif finished == total:
        overall_status = 'success'
    else:
        overall_status = 'pending'
    
    # Среднее покрытие
    finished_runs = runs.filter(status='finished', coverage__isnull=False)
    coverage_avg = 0.0
    if finished_runs.exists():
        coverage_avg = sum(run.coverage for run in finished_runs) / finished_runs.count()
    
    # Общее количество дефектов
    defects_count = sum(run.defects.count() for run in runs)
    
    return {
        'total_runs': total,
        'finished': finished,
        'failed': failed,
        'processing': processing,
        'queued': queued,
        'overall_status': overall_status,
        'coverage_avg': round(coverage_avg, 2),
        'defects_count': defects_count,
    }

