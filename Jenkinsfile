pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'financial-env'
        APP_PORT     = '7860'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Cloning repository...'
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                echo 'Installing Python dependencies...'
                sh '''
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running tests...'
                sh '''
                    pip install pytest
                    pytest tests/ -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image...'
                sh '''
                    docker build -t ${DOCKER_IMAGE}:latest .
                '''
            }
        }

        stage('Run Container') {
            steps {
                echo 'Starting the application container...'
                sh '''
                    docker stop ${DOCKER_IMAGE} || true
                    docker rm   ${DOCKER_IMAGE} || true
                    docker run -d \
                        --name ${DOCKER_IMAGE} \
                        -p ${APP_PORT}:7860 \
                        ${DOCKER_IMAGE}:latest
                '''
            }
        }

        stage('Verify App') {
            steps {
                echo 'Checking application health...'
                sh '''
                    sleep 5
                    curl -sf http://localhost:${APP_PORT}/health
                    echo "App is up and healthy!"
                '''
            }
        }

        stage('Cleanup') {
            steps {
                echo 'Stopping and removing container...'
                sh '''
                    docker stop ${DOCKER_IMAGE} || true
                    docker rm   ${DOCKER_IMAGE} || true
                '''
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the logs.'
        }
    }
}