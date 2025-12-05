"""
Функции для отправки результатов обратно в CI/CD системы
"""
import logging
import requests
from typing import Dict, Any, Optional

from ..models import Run

logger = logging.getLogger(__name__)


def send_ci_callback(run: Run, callback_url: Optional[str] = None) -> bool:
    """
    Отправка результатов прогона обратно в CI/CD систему
    
    Args:
        run: Объект прогона
        callback_url: URL для отправки callback (если не указан, берется из metadata)
    
    Returns:
        True если успешно, False в противном случае
    """
    try:
        # Получаем callback URL из metadata или используем переданный
        if not callback_url:
            details = run.details
            if details:
                import json
                try:
                    metadata = json.loads(details) if isinstance(details, str) else details
                    callback_url = metadata.get('callback_url')
                except:
                    pass
        
        if not callback_url:
            logger.warning(f"Callback URL не указан для прогона {run.id}")
            return False
        
        # Формируем данные для отправки
        payload = {
            'run_id': run.id,
            'ci_job_id': run.ci_job_id,
            'status': run.status,
            'coverage': float(run.coverage) if run.coverage else None,
            'diff_score': float(run.reference_diff_score) if run.reference_diff_score else None,
            'defects_count': run.defects.count(),
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        }
        
        # Добавляем информацию о дефектах
        if run.defects.exists():
            payload['defects'] = [
                {
                    'id': defect.id,
                    'severity': defect.severity,
                    'description': defect.description,
                }
                for defect in run.defects.all()[:10]  # Ограничиваем 10 дефектами
            ]
        
        # Отправляем POST запрос
        response = requests.post(
            callback_url,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Callback успешно отправлен для прогона {run.id}")
            return True
        else:
            logger.error(f"Ошибка отправки callback: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Исключение при отправке callback: {e}")
        return False


def update_ci_status(run: Run) -> bool:
    """
    Обновление статуса в CI/CD системе на основе результатов прогона
    
    Это обертка над send_ci_callback с логикой определения URL
    """
    # Логика определения callback URL в зависимости от CI системы
    details = run.details
    if details:
        import json
        try:
            metadata = json.loads(details) if isinstance(details, str) else details
            ci_system = metadata.get('ci_system', '')
            
            # Для разных CI/CD систем могут быть разные URL
            if ci_system == 'github':
                # GitHub Actions использует специальный API
                callback_url = f"https://api.github.com/repos/{metadata.get('repository')}/actions/runs/{run.ci_job_id}"
            elif ci_system == 'gitlab':
                # GitLab CI использует API
                callback_url = metadata.get('callback_url')
            else:
                callback_url = metadata.get('callback_url')
            
            return send_ci_callback(run, callback_url)
        except Exception as e:
            logger.error(f"Ошибка определения callback URL: {e}")
            return False
    
    return False

