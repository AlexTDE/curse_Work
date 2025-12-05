"""
Модуль интеграции с CI/CD системами
Поддерживает: GitHub Actions, GitLab CI, Jenkins
"""

from .webhooks import (
    GitHubWebhookView,
    GitLabWebhookView,
    JenkinsWebhookView,
    GenericCIWebhookView,
)
from .parsers import (
    parse_github_webhook,
    parse_gitlab_webhook,
    parse_jenkins_webhook,
)
from .callbacks import send_ci_callback

__all__ = [
    'GitHubWebhookView',
    'GitLabWebhookView',
    'JenkinsWebhookView',
    'GenericCIWebhookView',
    'parse_github_webhook',
    'parse_gitlab_webhook',
    'parse_jenkins_webhook',
    'send_ci_callback',
]

