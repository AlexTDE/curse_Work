"""
Утилиты для захвата скриншотов через Selenium и загрузки в API.
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from .webdriver_wrapper import UITestWebDriver
from .api_client import APIClient

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """
    Класс для автоматического захвата скриншотов и загрузки в API.
    """
    
    def __init__(
        self,
        api_base_url: str,
        api_token: Optional[str] = None,
        headless: bool = True
    ):
        """
        Инициализирует ScreenshotCapture.
        
        Args:
            api_base_url: Базовый URL API
            api_token: Токен для аутентификации
            headless: Запускать браузер в headless режиме
        """
        self.api_client = APIClient(api_base_url, api_token)
        self.headless = headless
        self.temp_dir = Path(tempfile.gettempdir()) / 'ui_test_screenshots'
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def capture_and_upload(
        self,
        url: str,
        testcase_id: int,
        wait_for_element: Optional[Dict[str, str]] = None,
        ci_job_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Захватывает скриншот страницы и загружает его в API.
        
        Args:
            url: URL для открытия
            testcase_id: ID тест-кейса
            wait_for_element: Словарь с 'by' и 'value' для ожидания элемента (опционально)
            ci_job_id: ID CI/CD джобы (опционально)
            
        Returns:
            Данные созданного прогона или None при ошибке
        """
        screenshot_path = self.temp_dir / f"screenshot_{testcase_id}_{Path(url).name}.png"
        
        with UITestWebDriver(headless=self.headless) as driver:
            # Переходим на страницу
            if not driver.navigate(url):
                return None
            
            # Ждем элемент, если указан
            if wait_for_element:
                from selenium.webdriver.common.by import By
                by = getattr(By, wait_for_element.get('by', 'ID'))
                value = wait_for_element.get('value')
                if not driver.wait_for_element(by, value, timeout=10):
                    logger.warning(f"Element not found, but continuing: {by}={value}")
            
            # Делаем скриншот
            if not driver.take_screenshot(str(screenshot_path)):
                return None
        
        # Загружаем в API
        run_data = self.api_client.create_run(
            testcase_id=testcase_id,
            actual_screenshot_path=str(screenshot_path),
            ci_job_id=ci_job_id
        )
        
        # Удаляем временный файл
        try:
            screenshot_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temp file {screenshot_path}: {e}")
        
        return run_data
    
    def capture_compare_and_wait(
        self,
        url: str,
        testcase_id: int,
        wait_for_element: Optional[Dict[str, str]] = None,
        ci_job_id: Optional[str] = None,
        timeout: int = 300
    ) -> Optional[Dict[str, Any]]:
        """
        Захватывает скриншот, запускает сравнение и ждет результатов.
        
        Args:
            url: URL для открытия
            testcase_id: ID тест-кейса
            wait_for_element: Словарь с 'by' и 'value' для ожидания элемента
            ci_job_id: ID CI/CD джобы
            timeout: Максимальное время ожидания результатов
            
        Returns:
            Финальные данные прогона с результатами сравнения
        """
        # Захватываем и загружаем скриншот
        run_data = self.capture_and_upload(
            url=url,
            testcase_id=testcase_id,
            wait_for_element=wait_for_element,
            ci_job_id=ci_job_id
        )
        
        if not run_data:
            return None
        
        run_id = run_data.get('id')
        if not run_id:
            return None
        
        # Запускаем сравнение
        self.api_client.trigger_compare(run_id)
        
        # Ждем результатов
        return self.api_client.wait_for_run_completion(run_id, timeout=timeout)

