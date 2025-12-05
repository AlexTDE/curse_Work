from django.contrib import admin

from .models import CoverageMetric, Defect, Run, TestCase, UIElement


class UIElementInline(admin.TabularInline):
    model = UIElement
    readonly_fields = ('bbox', 'confidence', 'element_type')
    extra = 0


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'created_by', 'created_at')
    search_fields = ('title', 'description')
    inlines = [UIElementInline]


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'status', 'started_by', 'started_at', 'finished_at', 'coverage')
    list_filter = ('status', 'testcase__status')
    readonly_fields = ('started_at', 'finished_at', 'reference_diff_score', 'coverage')


@admin.register(UIElement)
class UIElementAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'element_type', 'confidence', 'created_at')
    readonly_fields = ('bbox', 'confidence')


@admin.register(Defect)
class DefectAdmin(admin.ModelAdmin):
    list_display = ('id', 'testcase', 'run', 'severity', 'created_at')
    list_filter = ('severity',)


@admin.register(CoverageMetric)
class CoverageMetricAdmin(admin.ModelAdmin):
    list_display = ('run', 'coverage_percent', 'matched_elements', 'mismatched_elements', 'created_at')
