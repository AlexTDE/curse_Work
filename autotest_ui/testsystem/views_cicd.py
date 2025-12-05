"""
Веб-интерфейс для просмотра CI/CD отчётов.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta

from .models import Run, TestCase, Defect


@login_required
def cicd_dashboard(request):
    """
    Главная страница CI/CD отчётов со статистикой по всем сборкам.
    """
    # Получаем параметры фильтрации
    days = int(request.GET.get('days', 7))
    status = request.GET.get('status', '')
    
    # Фильтруем прогоны с CI/CD job_id за последние N дней
    start_date = timezone.now() - timedelta(days=days)
    runs = Run.objects.filter(
        ci_job_id__isnull=False,
        started_at__gte=start_date
    ).select_related('testcase', 'started_by')
    
    if status:
        runs = runs.filter(status=status)
    
    # Группируем по ci_job_id
    ci_jobs = runs.values('ci_job_id').annotate(
        total_runs=Count('id'),
        finished_runs=Count('id', filter=Q(status='finished')),
        failed_runs=Count('id', filter=Q(status='failed')),
        processing_runs=Count('id', filter=Q(status='processing')),
        avg_coverage=Avg('coverage_metric__coverage_percent'),
        defect_count=Count('defects')
    ).order_by('-total_runs')
    
    # Общая статистика
    total_jobs = ci_jobs.count()
    total_runs_count = runs.count()
    finished_count = runs.filter(status='finished').count()
    failed_count = runs.filter(status='failed').count()
    
    success_rate = 0
    if total_runs_count > 0:
        success_rate = round((finished_count / total_runs_count) * 100, 2)
    
    context = {
        'ci_jobs': ci_jobs,
        'total_jobs': total_jobs,
        'total_runs': total_runs_count,
        'finished_runs': finished_count,
        'failed_runs': failed_count,
        'success_rate': success_rate,
        'days': days,
        'selected_status': status,
    }
    
    return render(request, 'testsystem/cicd_dashboard.html', context)


@login_required
def cicd_job_detail(request, job_id):
    """
    Детальная информация о конкретной CI/CD сборке.
    """
    # Получаем все прогоны для этого job_id
    runs = Run.objects.filter(
        ci_job_id=job_id
    ).select_related(
        'testcase', 'started_by', 'coverage_metric'
    ).prefetch_related(
        'defects'
    ).order_by('-started_at')
    
    if not runs.exists():
        return render(request, 'testsystem/cicd_job_detail.html', {
            'error': f'CI/CD Job {job_id} не найден',
            'job_id': job_id,
        })
    
    # Статистика по сборке
    total_runs = runs.count()
    finished_runs = runs.filter(status='finished').count()
    failed_runs = runs.filter(status='failed').count()
    processing_runs = runs.filter(status='processing').count()
    
    # Средние метрики
    avg_coverage = runs.filter(
        coverage_metric__isnull=False
    ).aggregate(Avg('coverage_metric__coverage_percent'))['coverage_metric__coverage_percent__avg']
    
    # Дефекты
    total_defects = Defect.objects.filter(run__in=runs).count()
    critical_defects = Defect.objects.filter(
        run__in=runs, severity='critical'
    ).count()
    
    # Success rate
    success_rate = 0
    if total_runs > 0:
        success_rate = round((finished_runs / total_runs) * 100, 2)
    
    context = {
        'job_id': job_id,
        'runs': runs,
        'total_runs': total_runs,
        'finished_runs': finished_runs,
        'failed_runs': failed_runs,
        'processing_runs': processing_runs,
        'success_rate': success_rate,
        'avg_coverage': round(avg_coverage, 2) if avg_coverage else 0,
        'total_defects': total_defects,
        'critical_defects': critical_defects,
    }
    
    return render(request, 'testsystem/cicd_job_detail.html', context)


@login_required
def cicd_status_api(request):
    """
    API endpoint для получения статуса CI/CD сборки (для использования в CI/CD).
    Используется в скриптах сборки для проверки результатов.
    """
    job_id = request.GET.get('ci_job_id')
    
    if not job_id:
        return JsonResponse({
            'error': 'ci_job_id parameter is required'
        }, status=400)
    
    runs = Run.objects.filter(ci_job_id=job_id).select_related(
        'testcase', 'coverage_metric'
    ).prefetch_related('defects')
    
    if not runs.exists():
        return JsonResponse({
            'error': f'No runs found for CI job {job_id}'
        }, status=404)
    
    # Формируем ответ
    runs_data = []
    for run in runs:
        runs_data.append({
            'id': run.id,
            'testcase_id': run.testcase.id,
            'testcase_title': run.testcase.title,
            'status': run.status,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
            'coverage': run.coverage_metric.coverage_percent if hasattr(run, 'coverage_metric') and run.coverage_metric else None,
            'defects_count': run.defects.count(),
            'reference_diff_score': run.reference_diff_score,
        })
    
    total_runs = runs.count()
    finished_runs = runs.filter(status='finished').count()
    failed_runs = runs.filter(status='failed').count()
    
    # Определяем общий статус сборки
    if failed_runs > 0:
        overall_status = 'failed'
    elif finished_runs == total_runs:
        overall_status = 'success'
    else:
        overall_status = 'in_progress'
    
    return JsonResponse({
        'ci_job_id': job_id,
        'overall_status': overall_status,
        'total_runs': total_runs,
        'finished_runs': finished_runs,
        'failed_runs': failed_runs,
        'success_rate': round((finished_runs / total_runs) * 100, 2) if total_runs > 0 else 0,
        'runs': runs_data,
    })
