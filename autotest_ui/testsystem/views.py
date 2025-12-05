from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import CoverageMetric, Defect, Run, TestCase, UIElement
from .serializers import (
    CoverageMetricSerializer,
    DefectSerializer,
    RunSerializer,
    TestCaseSerializer,
    UIElementSerializer,
)
from .tasks import compare_reference_with_actual, generate_test_from_screenshot
from .ci_integration.utils import get_ci_status_summary


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.all().order_by('-created_at')
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Переопределяем права доступа: все операции требуют авторизации.
        """
        # Для чтения можно разрешить неавторизованным (опционально)
        if self.action in ['list', 'retrieve', 'elements']:
            return [permissions.IsAuthenticatedOrReadOnly()]
        # Для создания, изменения, удаления - только авторизованные
            return [permissions.IsAuthenticated()]
    
    def perform_destroy(self, instance):
        """
        Проверяем права доступа перед удалением.
        Только владелец или суперпользователь может удалить тест-кейс.
        """
        user = self.request.user
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Требуется авторизация")
        
        # Суперпользователь может удалять все
        if user.is_superuser:
            super().perform_destroy(instance)
            return
        
        # Владелец может удалять свои тест-кейсы
        if instance.created_by and instance.created_by == user:
            super().perform_destroy(instance)
            return
        
        # Остальные не могут удалять
        raise permissions.PermissionDenied("Вы можете удалять только свои тест-кейсы")

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """
        Запуск анализа тест-кейса.
        Только владелец или суперпользователь может запускать анализ.
        """
        testcase = self.get_object()
        user = request.user
        
        # Проверка прав доступа
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Требуется авторизация")
        
        if not user.is_superuser:
            if not testcase.created_by or testcase.created_by != user:
                raise permissions.PermissionDenied("Вы можете анализировать только свои тест-кейсы")
        
        job = generate_test_from_screenshot.delay(testcase.id)
        return Response({'task_id': job.id, 'status': 'queued'}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def elements(self, request, pk=None):
        testcase = self.get_object()
        serializer = UIElementSerializer(testcase.elements.all(), many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated:
            serializer.save(created_by=user)
        else:
            serializer.save()


class RunViewSet(viewsets.ModelViewSet):
    queryset = Run.objects.select_related('testcase', 'started_by', 'coverage_metric').prefetch_related('defects')
    serializer_class = RunSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Переопределяем права доступа: все операции требуют авторизации.
        """
        # Для чтения можно разрешить неавторизованным (опционально)
        if self.action in ['list', 'retrieve', 'ci_status', 'ci_status_detail']:
            return [permissions.IsAuthenticatedOrReadOnly()]
        # Для создания, изменения, удаления - только авторизованные
            return [permissions.IsAuthenticated()]
    
    def perform_destroy(self, instance):
        """
        Проверяем права доступа перед удалением.
        Только владелец или суперпользователь может удалить прогон.
        """
        user = self.request.user
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Требуется авторизация")
        
        # Суперпользователь может удалять все
        if user.is_superuser:
            super().perform_destroy(instance)
            return
        
        # Владелец может удалять свои прогоны
        if instance.started_by and instance.started_by == user:
            super().perform_destroy(instance)
            return
        
        # Владелец тест-кейса может удалять прогоны своего тест-кейса
        if instance.testcase.created_by and instance.testcase.created_by == user:
            super().perform_destroy(instance)
            return
        
        # Остальные не могут удалять
        raise permissions.PermissionDenied("Вы можете удалять только свои прогоны или прогоны своих тест-кейсов")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ci_job_id', 'status', 'testcase']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Фильтрация по ci_job_id через query параметр
        ci_job_id = self.request.query_params.get('ci_job_id', None)
        if ci_job_id:
            queryset = queryset.filter(ci_job_id=ci_job_id)
        return queryset

    def perform_create(self, serializer):
        user = getattr(self.request, 'user', None)
        if not serializer.validated_data.get('actual_screenshot'):
            raise ValidationError({'actual_screenshot': 'Screenshot is required for a run'})
        serializer.save(started_by=user if user and user.is_authenticated else None, status='processing')

    @action(detail=True, methods=['post'])
    def compare(self, request, pk=None):
        """
        Запуск сравнения прогона с эталоном.
        Только владелец, владелец тест-кейса или суперпользователь может запускать сравнение.
        """
        run = self.get_object()
        user = request.user
        
        # Проверка прав доступа
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Требуется авторизация")
        
        if not user.is_superuser:
            can_compare = False
            
            # Владелец прогона может запускать сравнение
            if run.started_by and run.started_by == user:
                can_compare = True
            
            # Владелец тест-кейса может запускать сравнение прогонов своего тест-кейса
            if run.testcase.created_by and run.testcase.created_by == user:
                can_compare = True
            
            if not can_compare:
                raise permissions.PermissionDenied("Вы можете запускать сравнение только для своих прогонов или прогонов своих тест-кейсов")
        
        job = compare_reference_with_actual.delay(run.id)
        run.status = 'processing'
        run.save(update_fields=['status'])
        return Response({'task_id': job.id, 'status': 'processing'})

    @action(detail=False, methods=['get'])
    def ci_status(self, request):
        """Получение статуса прогонов для CI/CD системы"""
        ci_job_id = request.query_params.get('ci_job_id')
        if not ci_job_id:
            return Response(
                {'error': 'ci_job_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        summary = get_ci_status_summary(ci_job_id)
        runs = Run.objects.filter(ci_job_id=ci_job_id).order_by('-started_at')
        serializer = RunSerializer(runs, many=True)
        
        return Response({
            'summary': summary,
            'runs': serializer.data
        })

    @action(detail=True, methods=['get'])
    def ci_status_detail(self, request, pk=None):
        """Детальный статус прогона для CI/CD"""
        run = self.get_object()
        serializer = RunSerializer(run)
        
        return Response({
            'run': serializer.data,
            'ci_job_id': run.ci_job_id,
            'status': run.status,
            'coverage': run.coverage,
            'defects_count': run.defects.count(),
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        })


class UIElementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UIElement.objects.select_related('testcase').all()
    serializer_class = UIElementSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class DefectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Defect.objects.select_related('testcase', 'run', 'element').all()
    serializer_class = DefectSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class CoverageMetricViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoverageMetric.objects.select_related('run').all()
    serializer_class = CoverageMetricSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]