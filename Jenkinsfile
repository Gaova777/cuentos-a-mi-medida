// CI/CD for cuentos-a-mi-medida, on a Jenkins running on the machine with Docker and the GPU.
pipeline {
    agent any

    parameters {
        booleanParam(name: 'APPLY_INFRA', defaultValue: true, description: 'terraform apply against LocalStack')
        booleanParam(name: 'RUN_BENCHMARKS', defaultValue: false, description: 'readability, consistency and safety benchmarks (GPU and Ollama, hours)')
    }

    environment {
        PATH = "${env.HOME}/.local/bin:${env.HOME}/.local/opt/node/bin:${env.PATH}"
    }

    stages {
        stage('Install') {
            steps { sh 'uv sync' }
        }
        stage('Lint and unit tests') {
            steps {
                sh 'uv run ruff check src scripts tests'
                sh 'mkdir -p reports && uv run pytest -q --junitxml=reports/pytest.xml'
            }
            post {
                always { junit 'reports/pytest.xml' }
            }
        }
        stage('Web build') {
            steps {
                dir('web') { sh 'npm ci && npm run lint && npm run build' }
            }
        }
        stage('Terraform') {
            steps {
                sh 'terraform -chdir=infra fmt -check'
                sh 'docker compose -f infra/docker-compose.yml up -d'
                sh 'until curl -sf localhost:4566/_localstack/health >/dev/null; do sleep 2; done'
                sh 'terraform -chdir=infra init -input=false && terraform -chdir=infra validate && terraform -chdir=infra plan -input=false'
            }
        }
        stage('Apply to LocalStack') {
            when { expression { params.APPLY_INFRA } }
            steps { sh 'terraform -chdir=infra apply -auto-approve -input=false' }
        }
        stage('Benchmarks') {
            when { expression { params.RUN_BENCHMARKS } }
            steps {
                sh './run.sh readability'
                sh './run.sh consistency'
                sh './run.sh safety'
            }
        }
        stage('Quality gate') {
            steps { sh 'uv run scripts/quality_gate.py' }
        }
    }
}
