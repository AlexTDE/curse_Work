// Пример Jenkins Pipeline для интеграции с системой тестирования UI
// Jenkinsfile

pipeline {
    agent any
    
    environment {
        TEST_API_URL = 'http://your-test-api.com/api'
        TEST_API_TOKEN = credentials('test-api-token')
        TESTCASE_ID = '1'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install selenium requests pillow
                '''
            }
        }
        
        stage('Run UI Tests') {
            steps {
                script {
                    sh '''
                        . venv/bin/activate
                        python scripts/run_ui_tests.py
                    '''
                }
            }
        }
        
        stage('Upload Screenshots') {
            steps {
                script {
                    sh '''
                        . venv/bin/activate
                        python scripts/upload_screenshots.py \
                            --api-url "$TEST_API_URL" \
                            --token "$TEST_API_TOKEN" \
                            --testcase-id "$TESTCASE_ID" \
                            --screenshots-dir ./screenshots
                    '''
                }
            }
        }
        
        stage('Trigger Webhook') {
            steps {
                script {
                    def webhookPayload = [
                        name: env.JOB_NAME,
                        url: env.JOB_URL,
                        build: [
                            number: env.BUILD_NUMBER,
                            phase: 'FINISHED',
                            status: currentBuild.result ?: 'SUCCESS',
                            url: env.BUILD_URL,
                            scm: [
                                branch: env.GIT_BRANCH,
                                commit: env.GIT_COMMIT
                            ],
                            artifacts: []
                        ]
                    ]
                    
                    sh """
                        curl -X POST "$TEST_API_URL/webhooks/ci/jenkins/?testcase_id=$TESTCASE_ID" \
                            -H "Content-Type: application/json" \
                            -d '${groovy.json.JsonOutput.toJson(webhookPayload)}'
                    """
                }
            }
        }
        
        stage('Wait for Results') {
            steps {
                script {
                    sh '''
                        . venv/bin/activate
                        python scripts/wait_for_results.py \
                            --api-url "$TEST_API_URL" \
                            --ci-job-id "${JOB_NAME}-${BUILD_NUMBER}" \
                            --timeout 300
                    '''
                }
            }
        }
        
        stage('Get Results') {
            steps {
                script {
                    sh '''
                        . venv/bin/activate
                        python scripts/get_test_results.py \
                            --api-url "$TEST_API_URL" \
                            --ci-job-id "${JOB_NAME}-${BUILD_NUMBER}"
                    '''
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'screenshots/**', allowEmptyArchive: true
            archiveArtifacts artifacts: 'test-results.json', allowEmptyArchive: true
        }
        failure {
            echo "UI tests failed!"
        }
    }
}

