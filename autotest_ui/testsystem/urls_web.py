"""
URL маршруты для веб-интерфейса.
"""
from django.urls import path
from .views_web import (
    index,
    login_view,
    logout_view,
    testcases_list,
    runs_list,
    create_testcase,
    analyze_testcase,
    create_run,
    compare_run,
    testcase_detail,
    run_detail,
    train_ml_model,
    delete_testcase,
    delete_run,
    jira_settings,
    test_jira_connection,
    approve_elements,
)

# CI/CD views
from .views_cicd import (
    cicd_dashboard,
    cicd_job_detail,
    cicd_status_api,
)

urlpatterns = [
    path('', index, name='index'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # Тест-кейсы
    path('testcases/', testcases_list, name='testcases_list'),
    path('testcase/create/', create_testcase, name='create_testcase'),
    path('testcase/<int:testcase_id>/analyze/', analyze_testcase, name='analyze_testcase'),
    path('testcase/<int:testcase_id>/delete/', delete_testcase, name='delete_testcase'),
    path('testcase/<int:testcase_id>/approve-elements/', approve_elements, name='approve_elements'),
    path('testcase/<int:testcase_id>/', testcase_detail, name='testcase_detail'),
    
    # Прогоны
    path('runs/', runs_list, name='runs_list'),
    path('run/create/', create_run, name='create_run'),
    path('run/<int:run_id>/compare/', compare_run, name='compare_run'),
    path('run/<int:run_id>/delete/', delete_run, name='delete_run'),
    path('run/<int:run_id>/', run_detail, name='run_detail'),
    
    # CI/CD Reports
    path('cicd/', cicd_dashboard, name='cicd_dashboard'),
    path('cicd/job/<str:job_id>/', cicd_job_detail, name='cicd_job_detail'),
    path('cicd/status/', cicd_status_api, name='cicd_status_api'),
    
    # ML и настройки
    path('ml/train/', train_ml_model, name='train_ml_model'),
    path('settings/jira/', jira_settings, name='jira_settings'),
    path('settings/jira/test/', test_jira_connection, name='test_jira_connection'),
]
