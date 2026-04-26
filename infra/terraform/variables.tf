variable "kubeconfig_path" {
  description = "Path to kubeconfig file."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Kubeconfig context to target (minikube by default)."
  type        = string
  default     = "minikube"
}

variable "namespace" {
  description = "Kubernetes namespace for FinSight resources."
  type        = string
  default     = "default"
}

variable "backend_image" {
  description = "Backend container image."
  type        = string
  default     = "finsight-backend:local"
}

variable "frontend_image" {
  description = "Frontend container image."
  type        = string
  default     = "finsight-frontend:local"
}

variable "backend_replicas" {
  description = "Number of backend replicas."
  type        = number
  default     = 3
}

variable "frontend_replicas" {
  description = "Number of frontend replicas."
  type        = number
  default     = 3
}

variable "frontend_node_port" {
  description = "NodePort exposed for frontend service."
  type        = number
  default     = 30080
}
