pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'financial-env'
        APP_PORT     = '7860'
        VENV_DIR     = "${WORKSPACE}/.venv"
        PATH         = "${WORKSPACE}/.venv/bin:${PATH}"
        TERRAFORM_DIR = "${WORKSPACE}/infra/terraform"
        RUN_TERRAFORM_PLAN = "false"
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
                    set -eux
                    python3 -m venv "${VENV_DIR}"
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running tests...'
                sh '''
                    set -eux
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

        stage('Terraform Plan') {
            when {
                expression {
                    return fileExists('infra/terraform') && env.RUN_TERRAFORM_PLAN == 'true'
                }
            }
            steps {
                echo 'Running Terraform init + plan...'
                sh '''
                    set -eux
                    terraform -chdir=${TERRAFORM_DIR} init -input=false
                    terraform -chdir=${TERRAFORM_DIR} plan -input=false -no-color
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