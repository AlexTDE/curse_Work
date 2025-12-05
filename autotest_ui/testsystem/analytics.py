"""
Сервис аналитики для административной панели.

Предоставляет агрегированные данные по:
- Общему количеству тест-кейсов и прогонов
- Среднему значению метрики покрытия
- Динамике выявления дефектов
- Статистике по пользователям
- Трендам производительности системы
"""

from django.db.models import Count, Avg, Q, F, Max, Min
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta
from .models import TestCase, Run, UIElement, Defect, CoverageMetric
from .versioning_models import TestCaseVersion, ReferenceUpdateRequest


class AnalyticsService:
    """
    Сервис для получения аналитической информации по системе.
    """
    
    @staticmethod
    def get_overall_statistics():
        """
        Получить общую статистику по системе.
        
        Returns:
            dict с ключами:
            - total_testcases: общее количество тест-кейсов
            - total_runs: общее количество прогонов
            - total_defects: общее количество дефектов
            - avg_coverage: среднее покрытие
            - testcases_by_status: распределение по статусам
            - runs_by_status: распределение прогонов по статусам
        """
        return {
            'total_testcases': TestCase.objects.count(),
            'total_runs': Run.objects.count(),
            'total_defects': Defect.objects.count(),
            'total_ui_elements': UIElement.objects.count(),
            'avg_coverage': CoverageMetric.objects.aggregate(
                avg=Avg('coverage_percent')
            )['avg'] or 0,
            'testcases_by_status': list(
                TestCase.objects.values('status')
                .annotate(count=Count('id'))
                .order_by('status')
            ),
            'runs_by_status': list(
                Run.objects.values('status')
                .annotate(count=Count('id'))
                .order_by('status')
            ),
            'defects_by_severity': list(
                Defect.objects.values('severity')
                .annotate(count=Count('id'))
                .order_by('severity')
            ),
        }
    
    @staticmethod
    def get_defect_dynamics(days=30, granularity='day'):
        """
        Получить динамику выявления дефектов во времени.
        
        Args:
            days: количество дней для анализа
            granularity: гранулярность ('day', 'week', 'month')
        
        Returns:
            list словарей с датой и количеством дефектов
        """
        start_date = timezone.now() - timedelta(days=days)
        
        trunc_function = {
            'day': TruncDate,
            'week': TruncWeek,
            'month': TruncMonth,
        }.get(granularity, TruncDate)
        
        defects_over_time = (
            Defect.objects
            .filter(created_at__gte=start_date)
            .annotate(period=trunc_function('created_at'))
            .values('period')
            .annotate(
                total=Count('id'),
                critical=Count('id', filter=Q(severity='critical')),
                major=Count('id', filter=Q(severity='major')),
                minor=Count('id', filter=Q(severity='minor')),
            )
            .order_by('period')
        )
        
        return list(defects_over_time)
    
    @staticmethod
    def get_coverage_dynamics(days=30, granularity='day'):
        """
        Получить динамику изменения покрытия во времени.
        
        Args:
            days: количество дней для анализа
            granularity: гранулярность ('day', 'week', 'month')
        
        Returns:
            list словарей с датой и средним покрытием
        """
        start_date = timezone.now() - timedelta(days=days)
        
        trunc_function = {
            'day': TruncDate,
            'week': TruncWeek,
            'month': TruncMonth,
        }.get(granularity, TruncDate)
        
        coverage_over_time = (
            CoverageMetric.objects
            .filter(created_at__gte=start_date)
            .annotate(period=trunc_function('created_at'))
            .values('period')
            .annotate(
                avg_coverage=Avg('coverage_percent'),
                max_coverage=Max('coverage_percent'),
                min_coverage=Min('coverage_percent'),
                count=Count('id')
            )
            .order_by('period')
        )
        
        return list(coverage_over_time)
    
    @staticmethod
    def get_user_statistics():
        """
        Получить статистику по пользователям.
        
        Returns:
            dict с данными по активности пользователей
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user_stats = []
        for user in User.objects.all():
            user_stats.append({
                'username': user.username,
                'testcases_created': TestCase.objects.filter(created_by=user).count(),
                'runs_started': Run.objects.filter(started_by=user).count(),
                'versions_created': TestCaseVersion.objects.filter(created_by=user).count(),
                'update_requests': ReferenceUpdateRequest.objects.filter(requested_by=user).count(),
            })
        
        return user_stats
    
    @staticmethod
    def get_testcase_performance():
        """
        Получить статистику производительности по тест-кейсам.
        
        Returns:
            list наиболее проблемных тест-кейсов (с большим количеством дефектов)
        """
        testcases_with_defects = (
            TestCase.objects
            .annotate(
                defect_count=Count('defects'),
                run_count=Count('runs'),
                avg_coverage=Avg('runs__coverage_metric__coverage_percent')
            )
            .filter(defect_count__gt=0)
            .order_by('-defect_count')
            [:10]  # Топ-10 проблемных
        )
        
        return [{
            'id': tc.id,
            'title': tc.title,
            'defect_count': tc.defect_count,
            'run_count': tc.run_count,
            'avg_coverage': round(tc.avg_coverage or 0, 2),
        } for tc in testcases_with_defects]
    
    @staticmethod
    def get_run_performance(days=7):
        """
        Получить статистику по производительности прогонов.
        
        Args:
            days: количество дней для анализа
        
        Returns:
            dict с метриками производительности
        """
        start_date = timezone.now() - timedelta(days=days)
        
        runs = Run.objects.filter(started_at__gte=start_date, finished_at__isnull=False)
        
        # Вычисляем среднее время выполнения
        runs_with_duration = runs.annotate(
            duration=F('finished_at') - F('started_at')
        )
        
        total_runs = runs.count()
        
        if total_runs == 0:
            return {
                'total_runs': 0,
                'avg_duration_seconds': 0,
                'success_rate': 0,
                'failure_rate': 0,
            }
        
        finished_runs = runs.filter(status='finished').count()
        failed_runs = runs.filter(status='failed').count()
        
        return {
            'total_runs': total_runs,
            'finished_runs': finished_runs,
            'failed_runs': failed_runs,
            'success_rate': round((finished_runs / total_runs) * 100, 2),
            'failure_rate': round((failed_runs / total_runs) * 100, 2),
        }
    
    @staticmethod
    def get_versioning_statistics():
        """
        Получить статистику по версионированию эталонов.
        
        Returns:
            dict с данными по версиям и запросам на обновление
        """
        return {
            'total_versions': TestCaseVersion.objects.count(),
            'total_update_requests': ReferenceUpdateRequest.objects.count(),
            'pending_requests': ReferenceUpdateRequest.objects.filter(status='pending').count(),
            'approved_requests': ReferenceUpdateRequest.objects.filter(status='approved').count(),
            'rejected_requests': ReferenceUpdateRequest.objects.filter(status='rejected').count(),
            'versions_by_reason': list(
                TestCaseVersion.objects.values('reason')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
        }
    
    @staticmethod
    def get_comprehensive_report(days=30):
        """
        Получить полный отчёт по системе за указанный период.
        
        Args:
            days: количество дней для анализа
        
        Returns:
            dict со всеми метриками
        """
        return {
            'overall': AnalyticsService.get_overall_statistics(),
            'defect_dynamics': AnalyticsService.get_defect_dynamics(days=days),
            'coverage_dynamics': AnalyticsService.get_coverage_dynamics(days=days),
            'user_stats': AnalyticsService.get_user_statistics(),
            'testcase_performance': AnalyticsService.get_testcase_performance(),
            'run_performance': AnalyticsService.get_run_performance(days=days),
            'versioning': AnalyticsService.get_versioning_statistics(),
        }
