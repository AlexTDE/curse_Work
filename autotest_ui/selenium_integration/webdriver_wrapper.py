"""
Обертка над Selenium WebDriver для упрощения работы с UI тестами.
"""
import logging
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


class UITestWebDriver:
    """
    Обертка над Selenium WebDriver для автоматизации браузера и захвата скриншотов.
    """
    
    def __init__(
        self,
        headless: bool = True,
        window_size: tuple = (1920, 1080),
        implicit_wait: int = 10,
        driver_path: Optional[str] = None
    ):
        """
        Инициализирует WebDriver.
        
        Args:
            headless: Запускать браузер в headless режиме
            window_size: Размер окна браузера (width, height)
            implicit_wait: Время неявного ожидания в секундах
            driver_path: Путь к chromedriver (если не указан, используется системный)
        """
        self.headless = headless
        self.window_size = window_size
        self.driver: Optional[webdriver.Chrome] = None
        self._init_driver(driver_path, implicit_wait)
    
    def _init_driver(self, driver_path: Optional[str], implicit_wait: int):
        """Инициализирует Chrome WebDriver."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument(f'--window-size={self.window_size[0]},{self.window_size[1]}')
        
        service = None
        if driver_path:
            service = Service(driver_path)
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(implicit_wait)
            self.driver.set_window_size(*self.window_size)
            logger.info("WebDriver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def navigate(self, url: str) -> bool:
        """
        Переходит по указанному URL.
        
        Args:
            url: URL для перехода
            
        Returns:
            True если успешно, False при ошибке
        """
        if not self.driver:
            logger.error("WebDriver not initialized")
            return False
        
        try:
            self.driver.get(url)
            logger.info(f"Navigated to {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            return False
    
    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: int = 10
    ) -> Optional[object]:
        """
        Ожидает появления элемента на странице.
        
        Args:
            by: Способ поиска (By.ID, By.CLASS_NAME, etc.)
            value: Значение для поиска
            timeout: Время ожидания в секундах
            
        Returns:
            WebElement или None
        """
        if not self.driver:
            return None
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"Element not found: {by}={value} (timeout: {timeout}s)")
            return None
    
    def click_element(self, by: By, value: str, timeout: int = 10) -> bool:
        """
        Кликает по элементу.
        
        Args:
            by: Способ поиска
            value: Значение для поиска
            timeout: Время ожидания в секундах
            
        Returns:
            True если успешно, False при ошибке
        """
        element = self.wait_for_element(by, value, timeout)
        if not element:
            return False
        
        try:
            element.click()
            logger.info(f"Clicked element: {by}={value}")
            return True
        except Exception as e:
            logger.error(f"Failed to click element {by}={value}: {e}")
            return False
    
    def fill_input(self, by: By, value: str, text: str, timeout: int = 10) -> bool:
        """
        Заполняет поле ввода.
        
        Args:
            by: Способ поиска
            value: Значение для поиска
            text: Текст для ввода
            timeout: Время ожидания в секундах
            
        Returns:
            True если успешно, False при ошибке
        """
        element = self.wait_for_element(by, value, timeout)
        if not element:
            return False
        
        try:
            element.clear()
            element.send_keys(text)
            logger.info(f"Filled input {by}={value} with text")
            return True
        except Exception as e:
            logger.error(f"Failed to fill input {by}={value}: {e}")
            return False
    
    def take_screenshot(self, filepath: str) -> bool:
        """
        Делает скриншот текущей страницы.
        
        Args:
            filepath: Путь для сохранения скриншота
            
        Returns:
            True если успешно, False при ошибке
        """
        if not self.driver:
            logger.error("WebDriver not initialized")
            return False
        
        try:
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False
    
    def get_page_title(self) -> str:
        """Возвращает заголовок страницы."""
        if not self.driver:
            return ""
        return self.driver.title
    
    def get_current_url(self) -> str:
        """Возвращает текущий URL."""
        if not self.driver:
            return ""
        return self.driver.current_url
    
    def close(self):
        """Закрывает браузер и освобождает ресурсы."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        """Поддержка контекстного менеджера."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка контекстного менеджера."""
        self.close()

