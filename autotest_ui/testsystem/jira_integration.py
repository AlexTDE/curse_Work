"""
Интеграция с Jira для автоматического создания и обновления задач при обнаружении дефектов.
"""
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from .models import Defect, Run

logger = logging.getLogger(__name__)

try:
    from jira import JIRA
    JIRA_AVAILABLE = True
except ImportError:
    JIRA_AVAILABLE = False
    logger.warning("jira-python not installed. Jira integration disabled.")


def get_jira_client() -> Optional[JIRA]:
    """
    Создает и возвращает клиент Jira, если настройки доступны.
    """
    if not JIRA_AVAILABLE:
        return None
    
    jira_url = getattr(settings, 'JIRA_URL', '')
    jira_username = getattr(settings, 'JIRA_USERNAME', '')
    jira_api_token = getattr(settings, 'JIRA_API_TOKEN', '')
    
    if not all([jira_url, jira_username, jira_api_token]):
        logger.debug("Jira credentials not configured")
        return None
    
    try:
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_username, jira_api_token)
        )
        return jira
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return None


def create_jira_issue_from_defect(defect: Defect) -> Optional[str]:
    """
    Создает задачу в Jira на основе дефекта.
    
    Args:
        defect: Объект Defect
        
    Returns:
        Ключ созданной задачи (например, 'TEST-123') или None при ошибке
    """
    jira = get_jira_client()
    if not jira:
        return None
    
    project_key = getattr(settings, 'JIRA_PROJECT_KEY', '')
    if not project_key:
        logger.warning("JIRA_PROJECT_KEY not configured")
        return None
    
    # Определяем тип задачи на основе severity
    issue_type = 'Bug'
    if defect.severity == 'critical':
        issue_type = 'Bug'
    elif defect.severity == 'major':
        issue_type = 'Task'
    else:
        issue_type = 'Task'
    
    # Формируем описание
    description = f"""
{defect.description}

**Test Case:** {defect.testcase.title} (ID: {defect.testcase_id})
**Run ID:** {defect.run_id}
**Severity:** {defect.severity}

**Coverage:** {defect.run.coverage or 0:.2f}%
**Diff Score:** {defect.run.reference_diff_score or 0:.4f}

"""
    
    if defect.element:
        description += f"**UI Element:** {defect.element.element_type} (ID: {defect.element_id})\n"
    
    if defect.screenshot:
        description += f"\n**Screenshot:** {defect.screenshot.url}\n"
    
    # Формируем summary
    summary = f"UI Defect: {defect.testcase.title}"
    if defect.element:
        summary += f" - {defect.element.element_type}"
    
    try:
        issue_dict = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description,
            'issuetype': {'name': issue_type},
        }
        
        # Добавляем метаданные в custom fields, если нужно
        if defect.metadata:
            # Можно добавить custom fields здесь
            pass
        
        issue = jira.create_issue(fields=issue_dict)
        
        # Сохраняем ключ задачи в defect и run
        defect.metadata = defect.metadata or {}
        defect.metadata['jira_issue_key'] = issue.key
        defect.save(update_fields=['metadata'])
        
        if defect.run:
            defect.run.task_tracker_issue = issue.key
            defect.run.save(update_fields=['task_tracker_issue'])
        
        logger.info(f"Created Jira issue {issue.key} for defect {defect.id}")
        return issue.key
        
    except Exception as e:
        logger.error(f"Failed to create Jira issue for defect {defect.id}: {e}")
        return None


def update_jira_issue_status(issue_key: str, status: str) -> bool:
    """
    Обновляет статус задачи в Jira.
    
    Args:
        issue_key: Ключ задачи (например, 'TEST-123')
        status: Новый статус ('To Do', 'In Progress', 'Done', 'Closed')
        
    Returns:
        True если успешно, False при ошибке
    """
    jira = get_jira_client()
    if not jira:
        return False
    
    try:
        issue = jira.issue(issue_key)
        jira.transition_issue(issue, status)
        logger.info(f"Updated Jira issue {issue_key} status to {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Jira issue {issue_key}: {e}")
        return False


def sync_defect_to_jira(defect: Defect) -> Optional[str]:
    """
    Синхронизирует дефект с Jira: создает задачу, если её нет, или обновляет существующую.
    
    Args:
        defect: Объект Defect
        
    Returns:
        Ключ задачи в Jira или None
    """
    # Проверяем, есть ли уже задача
    if defect.metadata and defect.metadata.get('jira_issue_key'):
        issue_key = defect.metadata['jira_issue_key']
        logger.debug(f"Defect {defect.id} already has Jira issue {issue_key}")
        return issue_key
    
    # Создаем новую задачу
    return create_jira_issue_from_defect(defect)


def get_jira_issue_url(issue_key: str) -> str:
    """
    Возвращает URL задачи в Jira.
    
    Args:
        issue_key: Ключ задачи (например, 'TEST-123')
        
    Returns:
        URL задачи
    """
    jira_url = getattr(settings, 'JIRA_URL', '')
    if not jira_url:
        return ''
    
    # Убираем trailing slash
    jira_url = jira_url.rstrip('/')
    return f"{jira_url}/browse/{issue_key}"

