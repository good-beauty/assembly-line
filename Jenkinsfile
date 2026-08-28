pipeline {
    agent any

    stages {
        stage('Build & Deploy') {
            steps {
                script {
                    // 构建并启动容器
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