#!/usr/bin/env python3
"""
Пример скрипта для получения результатов тестирования
Использование: python get_test_results.py --api-url http://localhost:8000/api --ci-job-id 123
"""
import argparse
import requests
import json


def main():
    parser = argparse.ArgumentParser(description='Get test results')
    parser.add_argument('--api-url', required=True, help='API base URL')
    parser.add_argument('--ci-job-id', required=True, help='CI job ID')
    parser.add_argument('--output', help='Output file (JSON)')
    
    args = parser.parse_args()
    
    url = f"{args.api_url}/runs/ci-status/"
    params = {'ci_job_id': args.ci_job_id}
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    summary = data['summary']
    runs = data['runs']
    
    print(f"\n{'='*60}")
    print(f"Test Results for CI Job: {args.ci_job_id}")
    print(f"{'='*60}")
    print(f"Overall Status: {summary['overall_status']}")
    print(f"Total Runs: {summary['total_runs']}")
    print(f"  - Finished: {summary['finished']}")
    print(f"  - Failed: {summary['failed']}")
    print(f"  - Processing: {summary['processing']}")
    print(f"  - Queued: {summary['queued']}")
    print(f"Average Coverage: {summary['coverage_avg']}%")
    print(f"Total Defects: {summary['defects_count']}")
    print(f"{'='*60}\n")
    
    if runs:
        print("Runs:")
        for run in runs:
            print(f"  Run #{run['id']}: {run['status']}")
            if run.get('coverage'):
                print(f"    Coverage: {run['coverage']}%")
            if run.get('defects'):
                print(f"    Defects: {len(run['defects'])}")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    # Возвращаем код выхода в зависимости от статуса
    if summary['overall_status'] == 'failure':
        return 1
    return 0


if __name__ == '__main__':
    exit(main())

