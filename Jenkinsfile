pipeline {
    agent any

    environment {
        DOCKER_IMAGE = 'financial-env'
        VENV_DIR     = "${WORKSPACE}/.venv"
        PATH         = "${WORKSPACE}/.venv/bin:${PATH}"
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

        stage('Run Container') {
            steps {
                echo 'Starting the application container...'
                sh '''
                    set -eu
                    CONTAINER_NAME="${DOCKER_IMAGE}-${BUILD_NUMBER}"
                    HOST_PORT="$(shuf -i 20000-29999 -n 1)"

                    echo "${CONTAINER_NAME}" > .container_name
                    echo "${HOST_PORT}" > .host_port

                    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
                    docker run -d \
                        --name "${CONTAINER_NAME}" \
                        -p "${HOST_PORT}:7860" \
                        "${DOCKER_IMAGE}:latest"
                '''
            }
        }

        stage('Verify App') {
            steps {
                echo 'Checking application health...'
                sh '''
                    set -eu
                    HOST_PORT="$(cat .host_port)"
                    sleep 5
                    curl -sf "http://localhost:${HOST_PORT}/health"
                    echo "App is up and healthy!"
                '''
            }
        }

        stage('Cleanup') {
            steps {
                echo 'Stopping and removing container...'
                sh '''
                    set -eu
                    if [ -f .container_name ]; then
                        CONTAINER_NAME="$(cat .container_name)"
                        docker rm -f "${CONTAINER_NAME}" || true
                    fi
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