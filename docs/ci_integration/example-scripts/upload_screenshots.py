#!/usr/bin/env python3
"""
Пример скрипта для загрузки скриншотов в систему тестирования
Использование: python upload_screenshots.py --api-url http://localhost:8000/api --token YOUR_TOKEN --testcase-id 1 --screenshots-dir ./screenshots
"""
import argparse
import os
import requests
from pathlib import Path


def upload_screenshot(api_url: str, token: str, testcase_id: int, screenshot_path: str) -> dict:
    """Загрузка одного скриншота"""
    url = f"{api_url}/runs/"
    
    headers = {}
    if token:
        headers['Authorization'] = f'Token {token}'
    
    with open(screenshot_path, 'rb') as f:
        files = {
            'actual_screenshot': (os.path.basename(screenshot_path), f, 'image/png')
        }
        data = {
            'testcase': testcase_id,
        }
        
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser(description='Upload screenshots to test system')
    parser.add_argument('--api-url', required=True, help='API base URL')
    parser.add_argument('--token', help='API token')
    parser.add_argument('--testcase-id', type=int, required=True, help='Test case ID')
    parser.add_argument('--screenshots-dir', required=True, help='Directory with screenshots')
    
    args = parser.parse_args()
    
    screenshots_dir = Path(args.screenshots_dir)
    if not screenshots_dir.exists():
        print(f"Error: Directory {screenshots_dir} does not exist")
        return 1
    
    screenshots = list(screenshots_dir.glob('*.png')) + list(screenshots_dir.glob('*.jpg'))
    
    if not screenshots:
        print(f"No screenshots found in {screenshots_dir}")
        return 1
    
    print(f"Uploading {len(screenshots)} screenshots...")
    
    for screenshot in screenshots:
        try:
            result = upload_screenshot(
                args.api_url,
                args.token,
                args.testcase_id,
                str(screenshot)
            )
            print(f"✓ Uploaded {screenshot.name}: Run ID {result['id']}")
        except Exception as e:
            print(f"✗ Failed to upload {screenshot.name}: {e}")
    
    return 0


if __name__ == '__main__':
    exit(main())

