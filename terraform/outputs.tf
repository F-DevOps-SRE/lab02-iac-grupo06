output "container_id" {
  description = "ID del contenedor Docker"
  value       = docker_container.web.id
}
output "container_name" {
  description = "Nombre del contenedor en ejecución"
  value       = docker_container.web.name
}
output "network_name" {
  description = "Nombre de la red Docker"
  value       = docker_network.app_network.name
}
output "service_url" {
  description = "URL local de acceso al servicio"
  value       = "http://127.0.0.1:${var.host_port}"
}
