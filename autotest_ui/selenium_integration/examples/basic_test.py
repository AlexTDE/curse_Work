"""
Пример использования Selenium интеграции для автоматического тестирования UI.

Для запуска:
1. Установите зависимости: pip install selenium
2. Убедитесь, что chromedriver установлен и доступен в PATH
3. Настройте API_BASE_URL и TESTCASE_ID
4. Запустите: python basic_test.py
"""
import logging
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from selenium_integration.screenshot_capture import ScreenshotCapture

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    # Настройки
    API_BASE_URL = "http://localhost:8000"
    API_TOKEN = None  # Укажите токен, если требуется аутентификация
    TESTCASE_ID = 1  # ID существующего тест-кейса
    URL_TO_TEST = "https://example.com"
    
    # Создаем экземпляр ScreenshotCapture
    capture = ScreenshotCapture(
        api_base_url=API_BASE_URL,
        api_token=API_TOKEN,
        headless=True
    )
    
    # Захватываем скриншот, запускаем сравнение и ждем результатов
    logger.info(f"Testing URL: {URL_TO_TEST}")
    result = capture.capture_compare_and_wait(
        url=URL_TO_TEST,
        testcase_id=TESTCASE_ID,
        wait_for_element={
            'by': 'TAG_NAME',  # ID, CLASS_NAME, TAG_NAME, CSS_SELECTOR, XPATH
            'value': 'body'
        },
        timeout=300
    )
    
    if result:
        logger.info(f"Test completed!")
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Coverage: {result.get('coverage', 0):.2f}%")
        logger.info(f"Diff Score: {result.get('reference_diff_score', 0):.4f}")
        
        # Проверяем дефекты
        defects_url = f"{API_BASE_URL}/api/runs/{result.get('id')}/defects/"
        logger.info(f"Check defects at: {defects_url}")
    else:
        logger.error("Test failed or timed out")


if __name__ == "__main__":
    main()

