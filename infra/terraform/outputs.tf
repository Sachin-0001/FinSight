output "backend_service_name" {
  description = "Backend service name inside cluster."
  value       = kubernetes_service_v1.backend.metadata[0].name
}

output "frontend_service_name" {
  description = "Frontend service name inside cluster."
  value       = kubernetes_service_v1.frontend.metadata[0].name
}

output "frontend_minikube_url_hint" {
  description = "Hint for opening the frontend via Minikube service command."
  value       = "Run: minikube service frontend --url"
}
