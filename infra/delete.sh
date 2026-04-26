#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"

command -v terraform >/dev/null 2>&1 || { echo "terraform is not installed"; exit 1; }

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Terraform directory not found: ${TF_DIR}"
  exit 1
fi

echo "Destroying Terraform-managed Kubernetes resources..."
terraform -chdir="${TF_DIR}" init -input=false
terraform -chdir="${TF_DIR}" destroy -input=false -auto-approve

echo "Done. Resources removed."
