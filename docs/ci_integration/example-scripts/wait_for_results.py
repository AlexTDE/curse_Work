#!/usr/bin/env python3
"""
Пример скрипта для ожидания результатов тестирования
Использование: python wait_for_results.py --api-url http://localhost:8000/api --ci-job-id 123 --timeout 300
"""
import argparse
import time
import requests
import sys


def check_status(api_url: str, ci_job_id: str) -> dict:
    """Проверка статуса прогонов"""
    url = f"{api_url}/runs/ci-status/"
    params = {'ci_job_id': ci_job_id}
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description='Wait for test results')
    parser.add_argument('--api-url', required=True, help='API base URL')
    parser.add_argument('--ci-job-id', required=True, help='CI job ID')
    parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds')
    parser.add_argument('--interval', type=int, default=5, help='Check interval in seconds')
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    print(f"Waiting for results for CI job {args.ci_job_id}...")
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > args.timeout:
            print(f"Timeout reached ({args.timeout}s)")
            return 1
        
        try:
            status = check_status(args.api_url, args.ci_job_id)
            summary = status['summary']
            
            print(f"[{elapsed:.0f}s] Status: {summary['overall_status']}, "
                  f"Finished: {summary['finished']}/{summary['total_runs']}")
            
            if summary['overall_status'] in ['success', 'failure']:
                print(f"\n✓ Tests completed: {summary['overall_status']}")
                print(f"  Coverage: {summary['coverage_avg']}%")
                print(f"  Defects: {summary['defects_count']}")
                
                if summary['overall_status'] == 'failure':
                    return 1
                return 0
            
            time.sleep(args.interval)
            
        except Exception as e:
            print(f"Error checking status: {e}")
            time.sleep(args.interval)


if __name__ == '__main__':
    exit(main())

