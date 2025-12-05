from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CoverageMetricViewSet,
    DefectViewSet,
    RunViewSet,
    TestCaseViewSet,
    UIElementViewSet,
)
from .views_web import (
    index,
    create_testcase,
    analyze_testcase,
    create_run,
    compare_run,
    testcase_detail,
    run_detail,
)
from .ci_integration.webhooks import (
    GitHubWebhookView,
    GitLabWebhookView,
    JenkinsWebhookView,
    GenericCIWebhookView,
)


router = DefaultRouter()
router.register(r'testcases', TestCaseViewSet, basename='testcase')
router.register(r'runs', RunViewSet, basename='run')
router.register(r'elements', UIElementViewSet, basename='element')
router.register(r'defects', DefectViewSet, basename='defect')
router.register(r'coverage', CoverageMetricViewSet, basename='coverage')


urlpatterns = [
    path('', include(router.urls)),
    # CI/CD Webhooks
    path('webhooks/ci/github/', GitHubWebhookView.as_view(), name='github-webhook'),
    path('webhooks/ci/gitlab/', GitLabWebhookView.as_view(), name='gitlab-webhook'),
    path('webhooks/ci/jenkins/', JenkinsWebhookView.as_view(), name='jenkins-webhook'),
    path('webhooks/ci/generic/', GenericCIWebhookView.as_view(), name='generic-ci-webhook'),
]