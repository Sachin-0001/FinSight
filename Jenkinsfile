pipeline {
    agent any

    environment {
        PYTHON_VERSION     = '3.11'
        DOCKER_IMAGE       = 'financial-env'
        DOCKER_TAG         = "${env.BUILD_NUMBER}"
        FINANCIAL_ENV_PORT = '7860'
        PYTHONPATH         = '.'
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // ── 1. SOURCE ──────────────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
                sh 'git log -1 --pretty=format:"Commit: %H | Author: %an | Message: %s"'
            }
        }

        // ── 2. ENVIRONMENT SETUP ───────────────────────────────────────────────
        stage('Setup Environment') {
            steps {
                echo '🐍 Setting up Python virtual environment...'
                sh '''
                    python${PYTHON_VERSION} -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    pip install pytest pytest-cov
                '''
            }
        }

        // ── 3. LINT & STATIC ANALYSIS ──────────────────────────────────────────
        stage('Lint & Static Analysis') {
            parallel {
                stage('Flake8') {
                    steps {
                        echo '🔍 Running flake8 linter...'
                        sh '''
                            . .venv/bin/activate
                            pip install flake8 --quiet
                            flake8 server/ models.py client.py inference.py \
                                --max-line-length=120 \
                                --exclude=__pycache__,.venv \
                                --count --statistics || true
                        '''
                    }
                }
                stage('Bandit Security Scan') {
                    steps {
                        echo '🔐 Running bandit security checks...'
                        sh '''
                            . .venv/bin/activate
                            pip install bandit --quiet
                            bandit -r server/ models.py client.py \
                                -ll --format txt || true
                        '''
                    }
                }
            }
        }

        // ── 4. UNIT TESTS ──────────────────────────────────────────────────────
        stage('Unit Tests') {
            steps {
                echo '🧪 Running unit and grader tests...'
                sh '''
                    . .venv/bin/activate
                    pytest tests/test_graders.py \
                        -v \
                        --tb=short \
                        --junitxml=reports/junit.xml \
                        --cov=server \
                        --cov=models \
                        --cov-report=xml:reports/coverage.xml \
                        --cov-report=term-missing
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                    publishCoverage(
                        adapters: [coberturaAdapter('reports/coverage.xml')],
                        sourceFileResolver: sourceFiles('STORE_ALL_BUILD')
                    )
                }
            }
        }

        // ── 5. GRADER DETERMINISM CHECK ────────────────────────────────────────
        stage('Grader Determinism Check') {
            steps {
                echo '🎯 Verifying grader determinism across seeds...'
                sh '''
                    . .venv/bin/activate
                    python -c "
from server.tasks import generate_task_instance, grade_task
from models import FinancialAction
import json

seeds = [1, 42, 99001, 7, 11]
tasks = ['anomaly_classification', 'kpi_extraction', 'compliance_assessment']
all_passed = True

for task in tasks:
    for seed in seeds:
        g = generate_task_instance(task, seed=seed)
        gt = g['ground_truth']
        if task == 'anomaly_classification':
            a = FinancialAction(action_type='classify', value=','.join(gt['anomaly_ids']), confidence=0.9, reasoning='determinism check test run')
        elif task == 'kpi_extraction':
            body = {k: gt[k] for k in ['revenue','gross_profit','net_income','ebitda']}
            a = FinancialAction(action_type='extract_kpi', value=json.dumps(body), confidence=0.9, reasoning='determinism check test run')
        else:
            a = FinancialAction(action_type='flag_issue', value=json.dumps({'issues': gt['issues']}), confidence=0.5, reasoning='determinism check test run')
        s1 = grade_task(task, a, gt)
        s2 = grade_task(task, a, gt)
        assert s1 == s2, f'Non-deterministic: {task} seed={seed}'
        assert 0.0 <= s1 <= 1.0, f'Score out of bounds: {s1}'
        print(f'  ✓ {task} seed={seed} score={s1:.4f}')

print('\\nAll determinism checks passed.')
"
                '''
            }
        }

        // ── 6. BUILD DOCKER IMAGE ──────────────────────────────────────────────
        stage('Build Docker Image') {
            steps {
                echo '🐳 Building Docker image...'
                sh '''
                    docker build \
                        -t ${DOCKER_IMAGE}:${DOCKER_TAG} \
                        -t ${DOCKER_IMAGE}:latest \
                        --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
                        --build-arg VCS_REF=$(git rev-parse --short HEAD) \
                        .
                '''
            }
        }

        // ── 7. INTEGRATION TEST (CONTAINER) ───────────────────────────────────
        stage('Integration Test') {
            steps {
                echo '🔗 Running integration tests against live container...'
                sh '''
                    # Start container
                    CONTAINER_ID=$(docker run -d \
                        -p ${FINANCIAL_ENV_PORT}:7860 \
                        -e FINANCIAL_ENV_DEBUG_METADATA=true \
                        --name finsight-test-${BUILD_NUMBER} \
                        ${DOCKER_IMAGE}:${DOCKER_TAG})

                    echo "Container started: $CONTAINER_ID"

                    # Wait for server to be ready (max 30s)
                    for i in $(seq 1 30); do
                        STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                            http://localhost:${FINANCIAL_ENV_PORT}/health || echo "000")
                        if [ "$STATUS" = "200" ]; then
                            echo "✓ Server healthy after ${i}s"
                            break
                        fi
                        echo "  Waiting... ($i/30)"
                        sleep 1
                    done

                    # Test /health
                    curl -sf http://localhost:${FINANCIAL_ENV_PORT}/health | \
                        python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='healthy'"
                    echo "✓ /health OK"

                    # Test /reset for each task
                    for TASK in anomaly_classification kpi_extraction compliance_assessment; do
                        RESP=$(curl -sf -X POST \
                            -H "Content-Type: application/json" \
                            -d "{\"task_name\": \"$TASK\"}" \
                            http://localhost:${FINANCIAL_ENV_PORT}/reset)
                        echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'content' in d, 'Missing content'
assert 'metadata' in d, 'Missing metadata'
assert d['metadata'].get('episode_id'), 'Missing episode_id'
print('  ✓', '${TASK}', 'reset OK')
"
                    done

                    # Test /state catalog
                    curl -sf http://localhost:${FINANCIAL_ENV_PORT}/state | \
                        python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['tasks'])==3"
                    echo "✓ /state catalog OK"

                    docker stop finsight-test-${BUILD_NUMBER}
                    docker rm  finsight-test-${BUILD_NUMBER}
                    echo "✓ Integration tests passed"
                '''
            }
            post {
                failure {
                    sh 'docker stop finsight-test-${BUILD_NUMBER} || true && docker rm finsight-test-${BUILD_NUMBER} || true'
                }
            }
        }

        // ── 8. SMOKE TEST — FULL EPISODE ROLLOUT ──────────────────────────────
        stage('Smoke Test — Episode Rollout') {
            steps {
                echo '🚬 Smoke-testing a full episode per task...'
                sh '''
                    . .venv/bin/activate
                    python -c "
import json, sys
from client import FinancialDocEnv
from models import FinancialAction
from server.tasks import generate_task_instance, grade_task

# Offline rollout — no HTTP needed
from server.environment import FinancialDocEnvironment

for task_name in ['anomaly_classification', 'kpi_extraction', 'compliance_assessment']:
    env = FinancialDocEnvironment(max_steps=1)
    obs = env.reset(task_name=task_name)
    g = generate_task_instance(task_name, seed=env.last_episode_seed)
    gt = g['ground_truth']

    if task_name == 'anomaly_classification':
        a = FinancialAction(action_type='classify', value=','.join(gt['anomaly_ids']), confidence=0.9, reasoning='smoke test rollout for CI pipeline')
    elif task_name == 'kpi_extraction':
        body = {k: gt[k] for k in ['revenue','gross_profit','net_income','ebitda']}
        a = FinancialAction(action_type='extract_kpi', value=json.dumps(body), confidence=0.9, reasoning='smoke test rollout for CI pipeline')
    else:
        a = FinancialAction(action_type='flag_issue', value=json.dumps({'issues': gt['issues']}), confidence=0.5, reasoning='smoke test rollout for CI pipeline')

    result = env.step(a)
    reward = result.reward
    assert result.done, 'Episode should be done after max_steps=1'
    assert reward is not None and 0.0 <= reward <= 1.0, f'Bad reward: {reward}'
    print(f'  ✓ {task_name}: reward={reward:.4f}')

print('All smoke tests passed.')
"
                '''
            }
        }

        // ── 9. PUSH TO REGISTRY ────────────────────────────────────────────────
        stage('Push to Registry') {
            when {
                branch 'main'
            }
            steps {
                echo '📦 Pushing Docker image to registry...'
                withCredentials([usernamePassword(
                    credentialsId: 'docker-registry-creds',
                    usernameVariable: 'REGISTRY_USER',
                    passwordVariable: 'REGISTRY_PASS'
                )]) {
                    sh '''
                        echo "$REGISTRY_PASS" | docker login -u "$REGISTRY_USER" --password-stdin
                        docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${REGISTRY_USER}/${DOCKER_IMAGE}:${DOCKER_TAG}
                        docker tag ${DOCKER_IMAGE}:latest   ${REGISTRY_USER}/${DOCKER_IMAGE}:latest
                        docker push ${REGISTRY_USER}/${DOCKER_IMAGE}:${DOCKER_TAG}
                        docker push ${REGISTRY_USER}/${DOCKER_IMAGE}:latest
                        docker logout
                    '''
                }
            }
        }

        // ── 10. DEPLOY ─────────────────────────────────────────────────────────
        stage('Deploy') {
            when {
                branch 'main'
            }
            input {
                message 'Deploy to production?'
                ok 'Yes, deploy'
                parameters {
                    choice(name: 'DEPLOY_ENV', choices: ['staging', 'production'], description: 'Target environment')
                }
            }
            steps {
                echo "🚀 Deploying to ${DEPLOY_ENV}..."
                sh '''
                    echo "Deploying ${DOCKER_IMAGE}:${DOCKER_TAG} to ${DEPLOY_ENV}"
                    # Replace with your deploy command, e.g.:
                    # kubectl set image deployment/finsight app=${DOCKER_IMAGE}:${DOCKER_TAG}
                    # docker-compose -f docker-compose.${DEPLOY_ENV}.yml up -d
                    echo "Deploy command placeholder — wire up your orchestrator here."
                '''
            }
        }

    }

    // ── POST ────────────────────────────────────────────────────────────────────
    post {
        always {
            echo '🧹 Cleaning up workspace and dangling images...'
            sh '''
                docker rmi ${DOCKER_IMAGE}:${DOCKER_TAG} || true
                docker image prune -f || true
                rm -rf .venv reports/__pycache__ || true
            '''
        }
        success {
            echo '✅ Pipeline completed successfully!'
        }
        failure {
            echo '❌ Pipeline failed. Check logs above for details.'
            // Add notification step here, e.g.:
            // mail to: 'team@example.com', subject: "Build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
        }
        unstable {
            echo '⚠️  Pipeline finished with warnings (unstable).'
        }
    }
}