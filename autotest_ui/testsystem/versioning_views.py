"""
REST API views для управления версиями эталонных скриншотов.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import TestCase
from .versioning_models import TestCaseVersion, ReferenceUpdateRequest
from .reference_versioning import ReferenceVersioningService
from rest_framework import serializers


# ==================== SERIALIZERS ====================

class TestCaseVersionSerializer(serializers.ModelSerializer):
    """ Serializer для версий эталонных скриншотов. """
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    screenshot_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TestCaseVersion
        fields = [
            'id', 'testcase', 'screenshot', 'screenshot_url',
            'version_number', 'created_by', 'created_by_username',
            'created_at', 'change_comment', 'reason', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'version_number']
    
    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
        return None


class ReferenceUpdateRequestSerializer(serializers.ModelSerializer):
    """ Serializer для запросов на обновление эталонов. """
    
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    proposed_screenshot_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ReferenceUpdateRequest
        fields = [
            'id', 'testcase', 'proposed_screenshot', 'proposed_screenshot_url',
            'source_run', 'requested_by', 'requested_by_username',
            'status', 'justification', 'reviewed_by', 'reviewed_by_username',
            'review_comment', 'created_at', 'reviewed_at', 'comparison_metrics'
        ]
        read_only_fields = ['id', 'created_at', 'reviewed_at', 'status']
    
    def get_proposed_screenshot_url(self, obj):
        if obj.proposed_screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.proposed_screenshot.url)
        return None


# ==================== VIEWSETS ====================

class TestCaseVersionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра истории версий эталонных скриншотов.
    
    Endpoints:
    - GET /api/testcase-versions/ - список всех версий
    - GET /api/testcase-versions/{id}/ - конкретная версия
    - GET /api/testcase-versions/?testcase={id} - версии конкретного тест-кейса
    """
    
    queryset = TestCaseVersion.objects.all().select_related('testcase', 'created_by')
    serializer_class = TestCaseVersionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['testcase', 'reason']
    ordering_fields = ['version_number', 'created_at']
    ordering = ['-version_number']


class ReferenceUpdateRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления запросами на обновление эталонов.
    
    Endpoints:
    - POST /api/reference-update-requests/ - создать запрос
    - GET /api/reference-update-requests/ - список запросов
    - GET /api/reference-update-requests/{id}/ - конкретный запрос
    - POST /api/reference-update-requests/{id}/approve/ - одобрить
    - POST /api/reference-update-requests/{id}/reject/ - отклонить
    """
    
    queryset = ReferenceUpdateRequest.objects.all().select_related(
        'testcase', 'source_run', 'requested_by', 'reviewed_by'
    )
    serializer_class = ReferenceUpdateRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['testcase', 'status', 'requested_by']
    ordering_fields = ['created_at', 'reviewed_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Одобрить запрос на обновление.
        
        POST /api/reference-update-requests/{id}/approve/
        Body: {"review_comment": "Approved because..."}
        """
        update_request = self.get_object()
        review_comment = request.data.get('review_comment', '')
        
        try:
            version = ReferenceVersioningService.approve_update_request(
                request_id=update_request.id,
                reviewer=request.user,
                review_comment=review_comment
            )
            
            return Response({
                'status': 'approved',
                'message': 'Reference screenshot updated successfully',
                'version': TestCaseVersionSerializer(version, context={'request': request}).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Отклонить запрос на обновление.
        
        POST /api/reference-update-requests/{id}/reject/
        Body: {"review_comment": "Rejected because..."}
        """
        update_request = self.get_object()
        review_comment = request.data.get('review_comment', '')
        
        try:
            ReferenceVersioningService.reject_update_request(
                request_id=update_request.id,
                reviewer=request.user,
                review_comment=review_comment
            )
            
            return Response({
                'status': 'rejected',
                'message': 'Update request rejected'
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TestCaseVersioningMixin:
    """
    Mixin для добавления версионирования к TestCaseViewSet.
    
    Добавляет к TestCaseViewSet дополнительные endpoints:
    - POST /api/testcases/{id}/update-reference/ - обновить эталон
    - POST /api/testcases/{id}/rollback-to-version/ - откатиться к версии
    - GET /api/testcases/{id}/version-history/ - история версий
    """
    
    @action(detail=True, methods=['post'])
    def update_reference(self, request, pk=None):
        """
        Обновить эталонный скриншот с сохранением истории.
        
        POST /api/testcases/{id}/update-reference/
        Body (multipart/form-data):
            - new_screenshot: файл изображения
            - reason: manual/design_change/bug_fix/auto_approved (опционально)
            - change_comment: комментарий (опционально)
        """
        testcase = self.get_object()
        new_screenshot = request.FILES.get('new_screenshot')
        
        if not new_screenshot:
            return Response(
                {'error': 'new_screenshot is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'manual')
        change_comment = request.data.get('change_comment', '')
        
        try:
            version = ReferenceVersioningService.update_reference_screenshot(
                testcase_id=testcase.id,
                new_screenshot=new_screenshot,
                user=request.user,
                reason=reason,
                change_comment=change_comment
            )
            
            return Response({
                'message': 'Reference screenshot updated',
                'version': TestCaseVersionSerializer(version, context={'request': request}).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def rollback_to_version(self, request, pk=None):
        """
        Откатиться к конкретной версии эталона.
        
        POST /api/testcases/{id}/rollback-to-version/
        Body: {"version_number": 3}
        """
        testcase = self.get_object()
        version_number = request.data.get('version_number')
        
        if not version_number:
            return Response(
                {'error': 'version_number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_version = ReferenceVersioningService.rollback_to_version(
                testcase_id=testcase.id,
                version_number=int(version_number),
                user=request.user
            )
            
            return Response({
                'message': f'Rolled back to version {version_number}',
                'new_version': TestCaseVersionSerializer(new_version, context={'request': request}).data
            })
        except TestCaseVersion.DoesNotExist:
            return Response(
                {'error': f'Version {version_number} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def version_history(self, request, pk=None):
        """
        Получить историю версий эталонного скриншота.
        
        GET /api/testcases/{id}/version-history/
        """
        testcase = self.get_object()
        versions = ReferenceVersioningService.get_version_history(testcase.id)
        
        serializer = TestCaseVersionSerializer(
            versions, 
            many=True, 
            context={'request': request}
        )
        
        return Response(serializer.data)
