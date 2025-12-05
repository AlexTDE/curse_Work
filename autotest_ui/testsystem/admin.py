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
from .versioning_models import TestCaseVersion, ReferenceUpdateRequest
from .analytics import AnalyticsService

User = get_user_model()


class CustomAdminSite(admin.AdminSite):
    site_header = 'Система автотестирования UI'
    site_title = 'AutoTest UI Admin'
    index_title = 'Панель управления'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        """
        Представление для аналитической панели.
        """
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
    fields = ('element_type', 'text', 'confidence', 'bbox')
    readonly_fields = ('bbox', 'confidence', 'element_type', 'text')
    extra = 0
    can_delete = False
    max_num = 0  # Не разрешать добавление новых
    
    def has_add_permission(self, request, obj=None):
        return False


class DefectInline(admin.TabularInline):
    model = Defect
    fields = ('severity', 'description', 'screenshot', 'created_at')
    readonly_fields = ('created_at',)
    extra = 0


@admin.register(TestCase, site=admin_site)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'status_badge', 'created_by', 
        'elements_count', 'runs_count', 'avg_coverage', 'created_at'
    )
    list_filter = ('status', 'created_at', 'created_by')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'elements_count', 'runs_count', 'preview_screenshot')
    inlines = [UIElementInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'status', 'created_by', 'created_at')
        }),
        ('Эталонный скриншот', {
            'fields': ('reference_screenshot', 'preview_screenshot')
        }),
        ('Статистика', {
            'fields': ('elements_count', 'runs_count', 'avg_coverage'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'new': '#6c757d',
            'analyzed': '#0d6efd',
            'ready': '#28a745',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def elements_count(self, obj):
        return obj.elements.count()
    elements_count.short_description = 'Кол-во элементов'
    
    def runs_count(self, obj):
        return obj.runs.count()
    runs_count.short_description = 'Кол-во прогонов'
    
    def avg_coverage(self, obj):
        avg = obj.runs.aggregate(avg=Avg('coverage'))['avg']
        if avg:
            return f"{avg:.2f}%"
        return "N/A"
    avg_coverage.short_description = 'Среднее покрытие'
    
    def preview_screenshot(self, obj):
        if obj.reference_screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;"/>',
                obj.reference_screenshot.url
            )
        return "No screenshot"
    preview_screenshot.short_description = 'Предпросмотр'


@admin.register(Run, site=admin_site)
class RunAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'testcase', 'status_badge', 'started_by', 
        'coverage_display', 'started_at', 'duration'
    )
    list_filter = ('status', 'started_at', 'testcase__status')
    search_fields = ('testcase__title', 'ci_job_id', 'task_tracker_issue')
    readonly_fields = (
        'started_at', 'finished_at', 'reference_diff_score', 
        'coverage', 'duration', 'preview_screenshot'
    )
    inlines = [DefectInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('testcase', 'status', 'started_by', 'started_at', 'finished_at', 'duration')
        }),
        ('Скриншот', {
            'fields': ('actual_screenshot', 'preview_screenshot')
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
    
    def status_badge(self, obj):
        colors = {
            'queued': '#ffc107',
            'processing': '#0d6efd',
            'finished': '#28a745',
            'failed': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def coverage_display(self, obj):
        if obj.coverage:
            color = '#28a745' if obj.coverage >= 80 else '#ffc107' if obj.coverage >= 50 else '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
                color,
                obj.coverage
            )
        return "N/A"
    coverage_display.short_description = 'Покрытие'
    
    def duration(self, obj):
        if obj.started_at and obj.finished_at:
            delta = obj.finished_at - obj.started_at
            return f"{delta.total_seconds():.1f} sec"
        return "N/A"
    duration.short_description = 'Длительность'
    
    def preview_screenshot(self, obj):
        if obj.actual_screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;"/>',
                obj.actual_screenshot.url
            )
        return "No screenshot"
    preview_screenshot.short_description = 'Предпросмотр'


@admin.register(UIElement, site=admin_site)
class UIElementAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'element_type', 'text_preview', 'confidence_badge', 'created_at')
    list_filter = ('element_type', 'created_at')
    search_fields = ('testcase__title', 'text', 'name')
    readonly_fields = ('bbox', 'confidence', 'created_at')
    
    def text_preview(self, obj):
        if obj.text:
            return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
        return "—"
    text_preview.short_description = 'Текст'
    
    def confidence_badge(self, obj):
        color = '#28a745' if obj.confidence >= 0.8 else '#ffc107' if obj.confidence >= 0.5 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2%}</span>',
            color,
            obj.confidence
        )
    confidence_badge.short_description = 'Уверенность'


@admin.register(Defect, site=admin_site)
class DefectAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'run', 'severity_badge', 'description_preview', 'created_at')
    list_filter = ('severity', 'created_at')
    search_fields = ('testcase__title', 'description')
    readonly_fields = ('created_at', 'preview_screenshot')
    
    def severity_badge(self, obj):
        colors = {
            'minor': '#6c757d',
            'major': '#ffc107',
            'critical': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.severity, '#6c757d'),
            obj.get_severity_display()
        )
    severity_badge.short_description = 'Серьёзность'
    
    def description_preview(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_preview.short_description = 'Описание'
    
    def preview_screenshot(self, obj):
        if obj.screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;"/>',
                obj.screenshot.url
            )
        return "No screenshot"
    preview_screenshot.short_description = 'Предпросмотр'


@admin.register(CoverageMetric, site=admin_site)
class CoverageMetricAdmin(admin.ModelAdmin):
    list_display = (
        'run', 'coverage_badge', 'total_elements', 
        'matched_elements', 'mismatched_elements', 'created_at'
    )
    readonly_fields = ('created_at',)
    
    def coverage_badge(self, obj):
        color = '#28a745' if obj.coverage_percent >= 80 else '#ffc107' if obj.coverage_percent >= 50 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 14px;">{:.2f}%</span>',
            color,
            obj.coverage_percent
        )
    coverage_badge.short_description = 'Покрытие'


@admin.register(TestCaseVersion, site=admin_site)
class TestCaseVersionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'testcase', 'version_number', 'reason_badge', 
        'created_by', 'created_at'
    )
    list_filter = ('reason', 'created_at')
    search_fields = ('testcase__title', 'change_comment')
    readonly_fields = ('created_at', 'preview_screenshot')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('testcase', 'version_number', 'created_by', 'created_at')
        }),
        ('Детали изменения', {
            'fields': ('reason', 'change_comment', 'metadata')
        }),
        ('Скриншот', {
            'fields': ('screenshot', 'preview_screenshot')
        }),
    )
    
    def reason_badge(self, obj):
        colors = {
            'manual': '#6c757d',
            'auto_approved': '#0d6efd',
            'design_change': '#28a745',
            'bug_fix': '#ffc107',
            'initial': '#17a2b8',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.reason, '#6c757d'),
            obj.get_reason_display()
        )
    reason_badge.short_description = 'Причина'
    
    def preview_screenshot(self, obj):
        if obj.screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;"/>',
                obj.screenshot.url
            )
        return "No screenshot"
    preview_screenshot.short_description = 'Предпросмотр'


@admin.register(ReferenceUpdateRequest, site=admin_site)
class ReferenceUpdateRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'testcase', 'status_badge', 'requested_by', 
        'reviewed_by', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('testcase__title', 'justification', 'review_comment')
    readonly_fields = ('created_at', 'reviewed_at', 'preview_screenshot')
    actions = ['approve_requests', 'reject_requests']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('testcase', 'source_run', 'status')
        }),
        ('Запрос', {
            'fields': ('requested_by', 'justification', 'created_at')
        }),
        ('Проверка', {
            'fields': ('reviewed_by', 'review_comment', 'reviewed_at')
        }),
        ('Скриншот', {
            'fields': ('proposed_screenshot', 'preview_screenshot')
        }),
        ('Метрики сравнения', {
            'fields': ('comparison_metrics',),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def preview_screenshot(self, obj):
        if obj.proposed_screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;"/>',
                obj.proposed_screenshot.url
            )
        return "No screenshot"
    preview_screenshot.short_description = 'Предпросмотр'
    
    def approve_requests(self, request, queryset):
        from .reference_versioning import ReferenceVersioningService
        
        count = 0
        for req in queryset.filter(status='pending'):
            try:
                ReferenceVersioningService.approve_update_request(
                    request_id=req.id,
                    reviewer=request.user,
                    review_comment='Bulk approved from admin'
                )
                count += 1
            except Exception as e:
                self.message_user(request, f"Error approving request {req.id}: {e}", level='error')
        
        self.message_user(request, f"Successfully approved {count} request(s)")
    approve_requests.short_description = 'Одобрить выбранные запросы'
    
    def reject_requests(self, request, queryset):
        from .reference_versioning import ReferenceVersioningService
        
        count = 0
        for req in queryset.filter(status='pending'):
            try:
                ReferenceVersioningService.reject_update_request(
                    request_id=req.id,
                    reviewer=request.user,
                    review_comment='Bulk rejected from admin'
                )
                count += 1
            except Exception as e:
                self.message_user(request, f"Error rejecting request {req.id}: {e}", level='error')
        
        self.message_user(request, f"Successfully rejected {count} request(s)")
    reject_requests.short_description = 'Отклонить выбранные запросы'


# Регистрируем User admin
admin_site.register(User, BaseUserAdmin)
