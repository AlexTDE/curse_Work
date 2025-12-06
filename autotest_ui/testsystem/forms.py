from django import forms
from django.core.exceptions import ValidationError

from .models import TestCase, Run, Defect
from .validators import validate_image_file


class TestCaseForm(forms.ModelForm):
    """
    Форма для создания/редактирования тест-кейса
    """
    class Meta:
        model = TestCase
        fields = ['title', 'description', 'reference_screenshot']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название тест-кейса'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание тест-кейса'
            }),
            'reference_screenshot': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/bmp,image/webp,image/tiff'
            })
        }
        labels = {
            'title': 'Название',
            'description': 'Описание',
            'reference_screenshot': 'Эталонный скриншот'
        }
        help_texts = {
            'reference_screenshot': 'Разрешены только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
        }
    
    def clean_reference_screenshot(self):
        """
        Валидация эталонного скриншота
        """
        screenshot = self.cleaned_data.get('reference_screenshot')
        
        if screenshot:
            try:
                validate_image_file(screenshot)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        elif not self.instance.pk:  # Новый объект
            raise forms.ValidationError('Эталонный скриншот обязателен')
        
        return screenshot


class RunForm(forms.ModelForm):
    """
    Форма для создания прогона теста
    """
    class Meta:
        model = Run
        fields = ['testcase', 'actual_screenshot', 'ci_job_id', 'task_tracker_issue']
        widgets = {
            'testcase': forms.Select(attrs={'class': 'form-control'}),
            'actual_screenshot': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/bmp,image/webp,image/tiff'
            }),
            'ci_job_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID CI/CD задачи (опционально)'
            }),
            'task_tracker_issue': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID задачи в трекере (опционально)'
            })
        }
        labels = {
            'testcase': 'Тест-кейс',
            'actual_screenshot': 'Фактический скриншот',
            'ci_job_id': 'CI/CD Job ID',
            'task_tracker_issue': 'Task Tracker Issue'
        }
        help_texts = {
            'actual_screenshot': 'Разрешены только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
        }
    
    def clean_actual_screenshot(self):
        """
        Валидация фактического скриншота
        """
        screenshot = self.cleaned_data.get('actual_screenshot')
        
        if not screenshot:
            raise forms.ValidationError('Скриншот обязателен для создания прогона')
        
        try:
            validate_image_file(screenshot)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)
        
        return screenshot


class DefectForm(forms.ModelForm):
    """
    Форма для создания дефекта
    """
    class Meta:
        model = Defect
        fields = ['description', 'severity', 'screenshot']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание дефекта'
            }),
            'severity': forms.Select(attrs={'class': 'form-control'}),
            'screenshot': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/bmp,image/webp,image/tiff'
            })
        }
        labels = {
            'description': 'Описание',
            'severity': 'Критичность',
            'screenshot': 'Скриншот'
        }
        help_texts = {
            'screenshot': 'Разрешены только изображения: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF (макс. 10 MB)'
        }
    
    def clean_screenshot(self):
        """
        Валидация скриншота дефекта (опционально)
        """
        screenshot = self.cleaned_data.get('screenshot')
        
        if screenshot:
            try:
                validate_image_file(screenshot)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        
        return screenshot
