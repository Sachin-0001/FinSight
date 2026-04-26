#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"

command -v minikube >/dev/null 2>&1 || { echo "minikube is not installed"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl is not installed"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "terraform is not installed"; exit 1; }

if ! minikube status >/dev/null 2>&1; then
  echo "Starting minikube..."
  minikube start
fi

echo "Building backend image in minikube..."
minikube image build -t finsight-backend:local "${ROOT_DIR}"

echo "Building frontend image in minikube..."
minikube image build -t finsight-frontend:local "${ROOT_DIR}/frontend"

if [[ ! -f "${TF_DIR}/terraform.tfvars" ]]; then
  cp "${TF_DIR}/terraform.tfvars.example" "${TF_DIR}/terraform.tfvars"
fi

echo "Applying Terraform..."
terraform -chdir="${TF_DIR}" init -input=false
terraform -chdir="${TF_DIR}" plan -input=false -no-color
terraform -chdir="${TF_DIR}" apply -input=false -auto-approve

echo "Done. Frontend URL:"
minikube service frontend --url
