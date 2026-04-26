#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT_DIR/k8s/finsight-minikube.yaml"
MODE="scale-down"
STOP_MINIKUBE="false"

usage() {
  cat <<'EOF'
Usage:
  ./k8s/stop_minikube.sh [--scale-down|--delete] [--stop-minikube]

Options:
  --scale-down      Gracefully scale backend/frontend deployments to 0 replicas (default)
  --delete          Delete all resources defined in k8s/finsight-minikube.yaml
  --stop-minikube   Also stop the Minikube cluster after workloads are stopped
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scale-down)
      MODE="scale-down"
      shift
      ;;
    --delete)
      MODE="delete"
      shift
      ;;
    --stop-minikube)
      STOP_MINIKUBE="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$MODE" == "scale-down" ]]; then
  echo "Scaling deployments down to 0 replicas..."
  kubectl scale deployment/backend deployment/frontend --replicas=0

  echo "Waiting for deployments to finish termination..."
  kubectl wait --for=delete pod -l app=backend --timeout=180s || true
  kubectl wait --for=delete pod -l app=frontend --timeout=180s || true

  echo "Deployments are scaled down. Services remain in place."
else
  echo "Deleting resources from manifest..."
  kubectl delete -f "$MANIFEST" --ignore-not-found=true
  echo "Resources deleted."
fi

if [[ "$STOP_MINIKUBE" == "true" ]]; then
  echo "Stopping Minikube..."
  minikube stop
fi

echo "Done."
