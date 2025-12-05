"""
Парсеры для извлечения данных из webhook'ов различных CI/CD систем
"""
import json
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


def parse_github_webhook(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг webhook от GitHub Actions
    
    Ожидаемый формат:
    {
        "action": "workflow_run",
        "workflow_run": {
            "id": 123456,
            "name": "UI Tests",
            "status": "completed",
            "conclusion": "success",
            "head_branch": "main",
            "head_sha": "abc123...",
            "artifacts_url": "https://api.github.com/repos/.../artifacts"
        },
        "repository": {
            "name": "my-repo",
            "full_name": "user/my-repo"
        }
    }
    """
    try:
        workflow_run = request_data.get('workflow_run', {})
        repository = request_data.get('repository', {})
        
        return {
            'ci_system': 'github',
            'ci_job_id': str(workflow_run.get('id', '')),
            'job_name': workflow_run.get('name', ''),
            'status': workflow_run.get('status', 'unknown'),
            'conclusion': workflow_run.get('conclusion', ''),
            'branch': workflow_run.get('head_branch', ''),
            'commit_sha': workflow_run.get('head_sha', ''),
            'repository': repository.get('full_name', ''),
            'artifacts_url': workflow_run.get('artifacts_url', ''),
            'run_url': workflow_run.get('html_url', ''),
            'metadata': {
                'workflow_id': workflow_run.get('workflow_id'),
                'run_number': workflow_run.get('run_number'),
                'event': workflow_run.get('event'),
            }
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга GitHub webhook: {e}")
        return {}


def parse_gitlab_webhook(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг webhook от GitLab CI
    
    Ожидаемый формат:
    {
        "object_kind": "pipeline",
        "object_attributes": {
            "id": 123456,
            "status": "success",
            "ref": "main",
            "sha": "abc123...",
            "web_url": "https://gitlab.com/.../pipelines/123456"
        },
        "project": {
            "name": "my-project",
            "path_with_namespace": "group/my-project"
        },
        "builds": [
            {
                "id": 789,
                "name": "ui-tests",
                "status": "success"
            }
        ]
    }
    """
    try:
        object_attrs = request_data.get('object_attributes', {})
        project = request_data.get('project', {})
        builds = request_data.get('builds', [])
        
        # Берем первый build или создаем общий job_id
        build = builds[0] if builds else {}
        job_id = str(build.get('id', object_attrs.get('id', '')))
        
        return {
            'ci_system': 'gitlab',
            'ci_job_id': job_id,
            'job_name': build.get('name', object_attrs.get('name', '')),
            'status': object_attrs.get('status', 'unknown'),
            'branch': object_attrs.get('ref', ''),
            'commit_sha': object_attrs.get('sha', ''),
            'repository': project.get('path_with_namespace', ''),
            'run_url': object_attrs.get('web_url', ''),
            'metadata': {
                'pipeline_id': object_attrs.get('id'),
                'builds_count': len(builds),
                'source': object_attrs.get('source'),
            }
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга GitLab webhook: {e}")
        return {}


def parse_jenkins_webhook(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг webhook от Jenkins
    
    Ожидаемый формат:
    {
        "name": "UI-Tests",
        "url": "job/UI-Tests/",
        "build": {
            "number": 123,
            "phase": "FINISHED",
            "status": "SUCCESS",
            "url": "job/UI-Tests/123/",
            "scm": {
                "branch": "origin/main",
                "commit": "abc123..."
            },
            "artifacts": [
                {
                    "fileName": "screenshot.png",
                    "relativePath": "screenshots/screenshot.png"
                }
            ]
        }
    }
    """
    try:
        build = request_data.get('build', {})
        scm = build.get('scm', {})
        
        return {
            'ci_system': 'jenkins',
            'ci_job_id': f"{request_data.get('name', '')}-{build.get('number', '')}",
            'job_name': request_data.get('name', ''),
            'status': build.get('status', 'UNKNOWN').lower(),
            'phase': build.get('phase', ''),
            'branch': scm.get('branch', '').replace('origin/', ''),
            'commit_sha': scm.get('commit', ''),
            'repository': request_data.get('url', ''),
            'run_url': build.get('url', ''),
            'artifacts': build.get('artifacts', []),
            'metadata': {
                'build_number': build.get('number'),
                'full_url': build.get('full_url', ''),
            }
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга Jenkins webhook: {e}")
        return {}


def parse_generic_webhook(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Универсальный парсер для любых CI/CD систем
    
    Ожидает стандартный формат:
    {
        "ci_system": "custom",
        "ci_job_id": "12345",
        "job_name": "UI Tests",
        "status": "success",
        "branch": "main",
        "commit_sha": "abc123...",
        "repository": "my-repo",
        "run_url": "https://...",
        "artifacts": [...]
    }
    """
    try:
        return {
            'ci_system': request_data.get('ci_system', 'generic'),
            'ci_job_id': str(request_data.get('ci_job_id', '')),
            'job_name': request_data.get('job_name', ''),
            'status': request_data.get('status', 'unknown'),
            'branch': request_data.get('branch', ''),
            'commit_sha': request_data.get('commit_sha', ''),
            'repository': request_data.get('repository', ''),
            'run_url': request_data.get('run_url', ''),
            'artifacts': request_data.get('artifacts', []),
            'metadata': request_data.get('metadata', {}),
        }
    except Exception as e:
        logger.error(f"Ошибка парсинга generic webhook: {e}")
        return {}

