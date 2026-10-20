# 1. Red Docker aislada para el grupo
resource "docker_network" "app_network" {
  name = "${var.app_name}-${var.group_id}-net"
  labels {
    label = "managed-by"
    value = "terraform"
  }
  labels {
    label = "environment"
    value = var.environment
  }
  labels {
    label = "owner"
    value = var.group_id
  }
}
# 2. Descarga y retención local de la imagen Nginx
resource "docker_image" "nginx" {
  name         = "nginx:${var.nginx_version}"
  keep_locally = true
}
# 3. Contenedor Nginx conectado a la red
resource "docker_container" "web" {
  name  = "${var.app_name}-${var.group_id}-tf"
  image = docker_image.nginx.image_id
  networks_advanced {
    name = docker_network.app_network.name
  }
  ports {
    internal = 80
    external = var.host_port
    ip       = "127.0.0.1"
  }
  env = [
    "APP_ENV=${var.environment}",
    "MANAGED_BY=terraform",
    "GROUP_ID=${var.group_id}"
  ]
  labels {
    label = "managed-by"
    value = "terraform"
  }
  labels {
    label = "tool"
    value = "iac-terraform"
  }
  labels {
    label = "owner"
    value = var.group_id
  }
}
