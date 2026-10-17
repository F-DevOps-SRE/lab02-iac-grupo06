"""Laboratorio 02 - Fundamentos de DevOps y SRE (UNAL 2026-01)
Implementacion de Infraestructura Local con Pulumi y Docker en Python
Costo: $0.00
"""

import pulumi
import pulumi_docker as docker

# 1. Lectura y validacion de la configuracion del stack
config = pulumi.Config()

group_id = config.get("groupId") or "grupo01"
environment = config.get("environment") or "dev"
host_port = config.get_int("hostPort") or 8090
nginx_version = config.get("nginxVersion") or "1.27-alpine"

valid_envs = ["dev", "staging", "prod"]
if environment not in valid_envs:
    raise ValueError(f"Ambiente '{environment}' invalido. Opciones: {valid_envs}")

# Metadatos comunes
common_labels = [
    docker.NetworkLabelArgs(label="managed-by", value="pulumi"),
    docker.NetworkLabelArgs(label="environment", value=environment),
    docker.NetworkLabelArgs(label="owner", value=group_id),
]

# 2. Red Docker aislada para Pulumi
network = docker.Network(
    f"network-{group_id}",
    name=f"servidor-web-{group_id}-pulumi-net",
    labels=common_labels,
)

# 3. Descarga de imagen Nginx
image = docker.RemoteImage(
    f"nginx-image-{group_id}",
    name=f"nginx:{nginx_version}",
    keep_locally=True,
)

# 4. Contenedor Nginx mapeado al puerto 8090
container = docker.Container(
    f"container-{group_id}",
    name=f"servidor-web-{group_id}-pulumi",
    image=image.image_id,
    networks_advanced=[
        docker.ContainerNetworksAdvancedArgs(
            name=network.name,
        )
    ],
    ports=[
        docker.ContainerPortArgs(
            internal=80,
            external=host_port,
            ip="127.0.0.1",
        )
    ],
    envs=[
        f"APP_ENV={environment}",
        "MANAGED_BY=pulumi",
        f"GROUP_ID={group_id}",
    ],
    labels=[
        docker.ContainerLabelArgs(label="managed-by", value="pulumi"),
        docker.ContainerLabelArgs(label="tool", value="iac-pulumi"),
        docker.ContainerLabelArgs(label="owner", value=group_id),
    ],
)

# 5. Salidas exportadas (Outputs)
pulumi.export("container_id", container.id)
pulumi.export("container_name", container.name)
pulumi.export("network_name", network.name)
pulumi.export("service_url", pulumi.Output.concat("http://127.0.0.1:", str(host_port)))