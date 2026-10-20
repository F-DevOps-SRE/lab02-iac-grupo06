variable "app_name" {
  description = "Nombre base de la aplicación"
  type        = string
  default     = "servidor-web"
}
variable "group_id" {
  description = "Identificador del grupo (ej: grupo01)"
  type        = string
  default     = "grupo06"
}
variable "environment" {
  description = "Ambiente de ejecución"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "El ambiente debe ser 'dev', 'staging' o 'prod'."
  }
}
variable "host_port" {
  description = "Puerto expuesto en el host local"
  type        = number
  default     = 8080
}
variable "nginx_version" {
  description = "Versión de la imagen Nginx"
  type        = string
  default     = "1.27-alpine"
}
