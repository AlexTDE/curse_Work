"""
Модуль интеграции с Selenium для автоматического захвата скриншотов и загрузки в API.
"""
from .webdriver_wrapper import UITestWebDriver
from .api_client import APIClient
from .screenshot_capture import ScreenshotCapture

__all__ = ['UITestWebDriver', 'APIClient', 'ScreenshotCapture']

