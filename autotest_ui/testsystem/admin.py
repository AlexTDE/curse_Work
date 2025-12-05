"""
Расширенная административная панель с аналитикой.
"""

from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

from .models import CoverageMetric, Defect, Run, TestCase, UIElement

# Пытаемся импортировать модели версионирования
try:
    from .versioning_models import TestCaseVersion, ReferenceUpdateRequest
    VERSIONING_AVAILABLE = True
except ImportError:
    VERSIONING_AVAILABLE = False
    TestCaseVersion = None
    ReferenceUpdateRequest = None

# Пытаемся импортировать аналитику
try:
    from .analytics import AnalyticsService
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    AnalyticsService = None

User = get_user_model()


class CustomAdminSite(admin.AdminSite):
    site_header = 'Система автотестирования UI'
    site_title = 'AutoTest UI Admin'
    index_title = 'Панель управления'
    
    def get_urls(self):
        urls = super().get_urls()
        if ANALYTICS_AVAILABLE:
            custom_urls = [
                path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
            ]
            return custom_urls + urls
        return urls
    
    def analytics_view(self, request):
        """Представление для аналитической панели."""
        if not ANALYTICS_AVAILABLE:
            return render(request, 'admin/error.html', {
                'title': 'Ошибка',
                'message': 'Модуль аналитики не доступен',
            })
        
        days = int(request.GET.get('days', 30))
        
        context = {
            'title': 'Аналитика системы',
            'analytics': AnalyticsService.get_comprehensive_report(days=days),
            'days': days,
            'site_header': self.site_header,
            'site_title': self.site_title,
            'has_permission': True,
        }
        
        return render(request, 'admin/analytics_dashboard.html', context)


# Используем кастомный admin site
admin_site = CustomAdminSite(name='custom_admin')


class UIElementInline(admin.TabularInline):
    model = UIElement
    fields = ('element_type', 'text', 'confidence')
    readonly_fields = ('element_type', 'text', 'confidence')
    extra = 0
    can_delete = False
    max_num = 0
    
    def has_add_permission(self, request, obj=None):
        return False


class DefectInline(admin.TabularInline):
    model = Defect
    fields = ('severity', 'description', 'created_at')
    readonly_fields = ('created_at',)
    extra = 0


@admin.register(TestCase, site=admin_site)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at', 'created_by')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)
    inlines = [UIElementInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'status', 'created_by', 'created_at')
        }),
        ('Эталонный скриншот', {
            'fields': ('reference_screenshot',)
        }),
    )


@admin.register(Run, site=admin_site)
class RunAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'status', 'started_by', 'started_at', 'finished_at')
    list_filter = ('status', 'started_at')
    search_fields = ('testcase__title', 'ci_job_id', 'task_tracker_issue')
    readonly_fields = ('started_at', 'finished_at', 'reference_diff_score', 'coverage')
    inlines = [DefectInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('testcase', 'status', 'started_by', 'started_at', 'finished_at')
        }),
        ('Скриншот', {
            'fields': ('actual_screenshot',)
        }),
        ('Метрики', {
            'fields': ('reference_diff_score', 'coverage'),
        }),
        ('Интеграции', {
            'fields': ('ci_job_id', 'task_tracker_issue'),
            'classes': ('collapse',)
        }),
        ('Детали и ошибки', {
            'fields': ('details', 'error_message'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UIElement, site=admin_site)
class UIElementAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'element_type', 'text_short', 'confidence', 'created_at')
    list_filter = ('element_type', 'created_at')
    search_fields = ('testcase__title', 'text', 'name')
    readonly_fields = ('created_at',)
    
    def text_short(self, obj):
        """Shortened text for list display"""
        if obj.text:
            return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
        return "—"
    text_short.short_description = 'Текст'


@admin.register(Defect, site=admin_site)
class DefectAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'run', 'severity', 'description_short', 'created_at')
    list_filter = ('severity', 'created_at')
    search_fields = ('testcase__title', 'description')
    readonly_fields = ('created_at',)
    
    def description_short(self, obj):
        """Shortened description for list display"""
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_short.short_description = 'Описание'


@admin.register(CoverageMetric, site=admin_site)
class CoverageMetricAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'run', 'coverage_percent', 'total_elements', 
        'matched_elements', 'mismatched_elements', 'created_at'
    )
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    search_fields = ('run__testcase__title',)


# Регистрируем модели версионирования
if VERSIONING_AVAILABLE and TestCaseVersion:
    @admin.register(TestCaseVersion, site=admin_site)
    class TestCaseVersionAdmin(admin.ModelAdmin):
        list_display = ('id', 'testcase', 'version_number', 'reason', 'created_by', 'created_at')
        list_filter = ('reason', 'created_at')
        search_fields = ('testcase__title', 'change_comment')
        readonly_fields = ('created_at',)


if VERSIONING_AVAILABLE and ReferenceUpdateRequest:
    @admin.register(ReferenceUpdateRequest, site=admin_site)
    class ReferenceUpdateRequestAdmin(admin.ModelAdmin):
        list_display = ('id', 'testcase', 'status', 'requested_by', 'reviewed_by', 'created_at')
        list_filter = ('status', 'created_at')
        search_fields = ('testcase__title', 'justification', 'review_comment')
        readonly_fields = ('created_at', 'reviewed_at')


# Регистрируем User admin
admin_site.register(User, BaseUserAdmin)
