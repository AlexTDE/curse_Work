"""
Клиент для работы с API системы автоматического тестирования UI.
"""
import logging
import requests
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class APIClient:
    """
    Клиент для взаимодействия с REST API системы тестирования.
    """
    
    def __init__(self, base_url: str, api_token: Optional[str] = None):
        """
        Инициализирует API клиент.
        
        Args:
            base_url: Базовый URL API (например, 'http://localhost:8000')
            api_token: Токен для аутентификации (опционально)
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        
        if api_token:
            self.session.headers.update({
                'Authorization': f'Token {api_token}'
            })
    
    def create_testcase(
        self,
        title: str,
        description: str = "",
        reference_screenshot_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создает новый тест-кейс.
        
        Args:
            title: Название тест-кейса
            description: Описание тест-кейса
            reference_screenshot_path: Путь к эталонному скриншоту
            
        Returns:
            Данные созданного тест-кейса или None при ошибке
        """
        url = f"{self.base_url}/api/testcases/"
        
        data = {
            'title': title,
            'description': description,
        }
        
        files = {}
        if reference_screenshot_path:
            files['reference_screenshot'] = open(reference_screenshot_path, 'rb')
        
        try:
            response = self.session.post(url, data=data, files=files)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created testcase {result.get('id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create testcase: {e}")
            return None
        finally:
            if files:
                files['reference_screenshot'].close()
    
    def create_run(
        self,
        testcase_id: int,
        actual_screenshot_path: str,
        ci_job_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создает новый прогон теста.
        
        Args:
            testcase_id: ID тест-кейса
            actual_screenshot_path: Путь к скриншоту текущего состояния
            ci_job_id: ID CI/CD джобы (опционально)
            
        Returns:
            Данные созданного прогона или None при ошибке
        """
        url = f"{self.base_url}/api/runs/"
        
        data = {
            'testcase': testcase_id,
        }
        
        if ci_job_id:
            data['ci_job_id'] = ci_job_id
        
        files = {
            'actual_screenshot': open(actual_screenshot_path, 'rb')
        }
        
        try:
            response = self.session.post(url, data=data, files=files)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Created run {result.get('id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create run: {e}")
            return None
        finally:
            files['actual_screenshot'].close()
    
    def trigger_compare(self, run_id: int) -> Optional[Dict[str, Any]]:
        """
        Запускает сравнение эталонного и фактического UI.
        
        Args:
            run_id: ID прогона
            
        Returns:
            Результат сравнения или None при ошибке
        """
        url = f"{self.base_url}/api/runs/{run_id}/compare/"
        
        try:
            response = self.session.post(url)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Triggered compare for run {run_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to trigger compare: {e}")
            return None
    
    def get_run_status(self, run_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает статус прогона.
        
        Args:
            run_id: ID прогона
            
        Returns:
            Данные прогона или None при ошибке
        """
        url = f"{self.base_url}/api/runs/{run_id}/"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get run status: {e}")
            return None
    
    def wait_for_run_completion(
        self,
        run_id: int,
        timeout: int = 300,
        poll_interval: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Ожидает завершения прогона.
        
        Args:
            run_id: ID прогона
            timeout: Максимальное время ожидания в секундах
            poll_interval: Интервал опроса в секундах
            
        Returns:
            Финальные данные прогона или None при таймауте/ошибке
        """
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            run_data = self.get_run_status(run_id)
            if not run_data:
                return None
            
            status = run_data.get('status')
            if status in ['finished', 'failed']:
                logger.info(f"Run {run_id} completed with status: {status}")
                return run_data
            
            time.sleep(poll_interval)
        
        logger.warning(f"Run {run_id} timeout after {timeout}s")
        return None

