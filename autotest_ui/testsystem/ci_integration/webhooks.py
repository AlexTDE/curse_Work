"""
Webhook handlers для различных CI/CD систем
"""
import json
import logging
import hmac
import hashlib
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ..models import Run, TestCase
from ..serializers import RunSerializer
from .parsers import (
    parse_github_webhook,
    parse_gitlab_webhook,
    parse_jenkins_webhook,
    parse_generic_webhook,
)
from .callbacks import send_ci_callback

logger = logging.getLogger(__name__)


class BaseCIWebhookView(APIView):
    """Базовый класс для CI/CD webhook'ов"""
    permission_classes = [AllowAny]
    
    def verify_signature(self, request, secret: str) -> bool:
        """Проверка подписи webhook (для безопасности)"""
        if not secret:
            return True  # Если секрет не настроен, пропускаем проверку
        
        # GitHub использует формат "sha256=hash"
        github_sig = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if github_sig:
            if github_sig.startswith('sha256='):
                github_sig = github_sig[7:]
            body = request.body
            expected_signature = hmac.new(
                secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(github_sig, expected_signature)
        
        # GitLab использует токен в заголовке
        gitlab_token = request.META.get('HTTP_X_GITLAB_TOKEN', '')
        if gitlab_token:
            return hmac.compare_digest(gitlab_token, secret)
        
        # Jenkins и другие - проверяем кастомный заголовок
        jenkins_sig = request.META.get('HTTP_X_JENKINS_SIGNATURE', '')
        if jenkins_sig:
            body = request.body
            expected_signature = hmac.new(
                secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(jenkins_sig, expected_signature)
        
        return False
    
    def create_run_from_webhook(self, parsed_data: Dict[str, Any], testcase_id: int = None) -> Run:
        """Создание прогона из данных webhook'а"""
        if not parsed_data:
            raise ValueError("Не удалось распарсить данные webhook'а")
        
        # Если testcase_id не указан, берем первый доступный или создаем новый
        if testcase_id:
            testcase = TestCase.objects.get(pk=testcase_id)
        else:
            # Берем последний готовый тест-кейс
            testcase = TestCase.objects.filter(status='ready').first()
            if not testcase:
                raise ValueError("Нет доступных тест-кейсов для запуска")
        
        # Создаем прогон
        run = Run.objects.create(
            testcase=testcase,
            ci_job_id=parsed_data.get('ci_job_id', ''),
            status='queued',
            details=json.dumps({
                'ci_system': parsed_data.get('ci_system', ''),
                'job_name': parsed_data.get('job_name', ''),
                'branch': parsed_data.get('branch', ''),
                'commit_sha': parsed_data.get('commit_sha', ''),
                'repository': parsed_data.get('repository', ''),
                'run_url': parsed_data.get('run_url', ''),
                'metadata': parsed_data.get('metadata', {}),
            })
        )
        
        logger.info(f"Создан прогон {run.id} из CI/CD webhook: {parsed_data.get('ci_job_id')}")
        return run


@method_decorator(csrf_exempt, name='dispatch')
class GitHubWebhookView(BaseCIWebhookView):
    """Webhook для GitHub Actions"""
    
    def post(self, request):
        try:
            # Проверка подписи (опционально)
            from django.conf import settings
            secret = getattr(settings, 'GITHUB_WEBHOOK_SECRET', None)
            if secret and not self.verify_signature(request, secret):
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            data = json.loads(request.body)
            parsed = parse_github_webhook(data)
            
            if not parsed:
                return Response(
                    {'error': 'Failed to parse webhook data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем прогон
            testcase_id = request.GET.get('testcase_id') or data.get('testcase_id')
            run = self.create_run_from_webhook(parsed, int(testcase_id) if testcase_id else None)
            
            serializer = RunSerializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Ошибка обработки GitHub webhook: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class GitLabWebhookView(BaseCIWebhookView):
    """Webhook для GitLab CI"""
    
    def post(self, request):
        try:
            # Проверка токена
            from django.conf import settings
            token = request.META.get('HTTP_X_GITLAB_TOKEN', '')
            expected_token = getattr(settings, 'GITLAB_WEBHOOK_TOKEN', None)
            
            if expected_token and not self.verify_signature(request, expected_token):
                return Response(
                    {'error': 'Invalid token'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            data = json.loads(request.body)
            parsed = parse_gitlab_webhook(data)
            
            if not parsed:
                return Response(
                    {'error': 'Failed to parse webhook data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем прогон
            testcase_id = request.GET.get('testcase_id') or data.get('testcase_id')
            run = self.create_run_from_webhook(parsed, int(testcase_id) if testcase_id else None)
            
            serializer = RunSerializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Ошибка обработки GitLab webhook: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class JenkinsWebhookView(BaseCIWebhookView):
    """Webhook для Jenkins"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            parsed = parse_jenkins_webhook(data)
            
            if not parsed:
                return Response(
                    {'error': 'Failed to parse webhook data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем прогон
            testcase_id = request.GET.get('testcase_id') or data.get('testcase_id')
            run = self.create_run_from_webhook(parsed, int(testcase_id) if testcase_id else None)
            
            serializer = RunSerializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Ошибка обработки Jenkins webhook: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class GenericCIWebhookView(BaseCIWebhookView):
    """Универсальный webhook для любых CI/CD систем"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            parsed = parse_generic_webhook(data)
            
            if not parsed:
                return Response(
                    {'error': 'Failed to parse webhook data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Создаем прогон
            testcase_id = request.GET.get('testcase_id') or data.get('testcase_id')
            run = self.create_run_from_webhook(parsed, int(testcase_id) if testcase_id else None)
            
            serializer = RunSerializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Ошибка обработки generic webhook: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

