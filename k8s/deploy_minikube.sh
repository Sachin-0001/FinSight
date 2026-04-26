#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/5] Ensuring minikube is running..."
minikube status >/dev/null 2>&1 || minikube start

echo "[2/5] Building backend image in minikube..."
minikube image build -t finsight-backend:local "$ROOT_DIR"

echo "[3/5] Building frontend image in minikube..."
minikube image build -t finsight-frontend:local "$ROOT_DIR/frontend"

echo "[4/5] Applying Kubernetes manifests..."
kubectl apply -f "$ROOT_DIR/k8s/finsight-minikube.yaml"

echo "[5/5] Waiting for deployments to become ready..."
kubectl rollout status deployment/backend --timeout=180s
kubectl rollout status deployment/frontend --timeout=180s

echo "Done. Opening service URL..."
minikube service frontend --url
