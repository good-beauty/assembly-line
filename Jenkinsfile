pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/yourname/test-pipeline.git'
            }
        }

        stage('Build & Deploy') {
            steps {
                script {
                    // 如果容器未启动，则构建并启动
                    sh 'docker compose up -d --build'
                }
            }
        }

        stage('Run Pipeline') {
            steps {
                script {
                    // 等待 app 容器就绪
                    sh 'sleep 10'
                    // 进入 app 容器执行流水线
                    sh 'docker exec test-pipeline-app python run_pipeline.py'
                }
            }
        }

        stage('Archive Report') {
            steps {
                // 归档 Allure 报告结果
                allure includeProperties: false, jdk: '', results: [[path: 'backend/allure-results']]
            }
        }

        stage('Notify') {
            steps {
                script {
                    // 可选：发送钉钉通知，后续第7周实现
                    echo 'Pipeline completed successfully!'
                }
            }
        }
    }

    post {
        failure {
            echo 'Pipeline failed!'
        }
    }
}