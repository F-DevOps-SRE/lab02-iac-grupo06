# lab02-iac-grupo06

Segundo laboratorio del curso **Fundamentos de DevOps y SRE** – Universidad Nacional de Colombia (2026-01).

**Infraestructura como Código: Terraform vs. Pulumi (100 % local / costo $0).**

## 1. Integrantes y roles

| Rol | Integrante | Responsabilidad principal | Revisión cruzada (QA) |
|---|---|---|---|
| **R1** – Ingeniero Terraform | David Alfonso Cañas Palomino | Carpeta `terraform/` (red, imagen, contenedor en puerto `8080`, variables y outputs) | Revisa el PR de Pulumi y ejecuta `pulumi preview` |
| **R2** – Ingeniero Pulumi | Edgar Fernando Vega Morales | Carpeta `pulumi/` en Python (red, imagen, contenedor en puerto `8090`, configuración y outputs) | Revisa el PR de Terraform y ejecuta `terraform plan` |
| **R3** – Platform & CI Lead | Óscar Daniel Murillo Botero | Repositorio, ramas protegidas, `.gitignore`, pipeline de GitHub Actions y coordinación del informe | Simulación de *drift* y auditoría del `destroy` limpio |

---

## 2. Arquitectura

```
+--------------------------------------------------------------+
|                    MÁQUINA LOCAL (Docker Engine)             |
|                                                              |
|   [TERRAFORM - HCL]                 [PULUMI - PYTHON]        |
|   Provider: kreuzwerker/docker      Provider: pulumi-docker  |
|   State: terraform.tfstate          State: ~/.pulumi (local) |
|            |                                 |               |
|   servidor-web-grupo06-net          servidor-web-<grupo>-    |
|            |                        pulumi-net               |
|   servidor-web-grupo06-tf                    |               |
|   (nginx:1.27-alpine)               servidor-web-<grupo>-    |
|            |                        pulumi (nginx:1.27-alp.) |
+------------|---------------------------------|---------------+
             v                                 v
     http://localhost:8080             http://localhost:8090
```

| Recurso | Terraform | Pulumi |
|---|---|---|
| Red | `docker_network.app_network` → `servidor-web-grupo06-net` | `docker.Network` → `servidor-web-<groupId>-pulumi-net` |
| Imagen | `docker_image.nginx` → `nginx:1.27-alpine` (`keep_locally = true`) | `docker.RemoteImage` → `nginx:1.27-alpine` (`keep_locally=True`) |
| Contenedor | `docker_container.web` → `servidor-web-grupo06-tf` | `docker.Container` → `servidor-web-<groupId>-pulumi` |
| Puerto host | `127.0.0.1:8080` | `127.0.0.1:8090` |
| Estado | `terraform/terraform.tfstate` | Backend local en `~/.pulumi` |

> El `groupId` de Pulumi se lee de `pulumi/Pulumi.dev.yaml`. Para que los nombres coincidan con Terraform, debe valer `grupo06` (ver [Notas](#9-notas-y-observaciones-del-repositorio)).

---

## 3. Estructura del repositorio

```
lab02-iac-grupo06/
├── README.md                     # Este archivo
├── .gitignore                    # Excluye tfstate, .terraform/, venv y secretos
├── terraform.tfvars.example      # Valores de ejemplo para Terraform
├── .github/workflows/iac-ci.yml  # Pipeline Shift-Left (fmt/validate + ruff/flake8)
├── terraform/                    # R1
│   ├── versions.tf               # Terraform >= 1.5.0, provider kreuzwerker/docker ~> 3.0.2
│   ├── providers.tf              # Provider Docker (socket local autodetectado)
│   ├── variables.tf              # app_name, group_id, environment, host_port, nginx_version
│   ├── main.tf                   # docker_network + docker_image + docker_container
│   └── outputs.tf                # container_id, container_name, network_name, service_url
├── pulumi/                       # R2
│   ├── Pulumi.yaml               # Metadatos del proyecto (runtime python + venv)
│   ├── Pulumi.dev.yaml           # Configuración del stack dev
│   ├── requirements.txt          # pulumi>=3.100, pulumi-docker>=4.0
│   └── __main__.py               # Infraestructura en Python
└── docs/
    └── informe_comparativo.md    # Matriz comparativa, evidencias de drift y conclusiones
```

---

## 4. Prerrequisitos

Todas las herramientas son gratuitas. **No se necesitan cuentas en AWS, GCP, Azure ni en pulumi.com.**

| Herramienta | Versión mínima | Verificación |
|---|---|---|
| Docker Engine / Docker Desktop | Cualquiera reciente | `docker --version` y `docker ps` |
| Terraform (u OpenTofu) | 1.5.0 | `terraform -version` |
| Pulumi CLI | 3.100 | `pulumi version` |
| Python | 3.10 | `python --version` (o `python3 --version`) |
| Git | — | `git --version` |

Recomendado antes de empezar (para no depender de la red durante la práctica):

```bash
docker pull nginx:1.27-alpine
```

Clonar el repositorio:

```bash
git clone <URL-del-repositorio>/lab02-iac-grupo06.git
cd lab02-iac-grupo06
```

---

## 5. Despliegue local con Terraform (puerto 8080)

```bash
cd terraform

# (Opcional) Personalizar variables. El ejemplo está en la raíz del repo.
cp ../terraform.tfvars.example terraform.tfvars
# Ajustar group_id = "grupo06" en terraform.tfvars

terraform fmt          # Formato canónico
terraform init         # Descarga el provider kreuzwerker/docker
terraform validate     # Valida sintaxis y tipos
terraform plan         # Muestra el plan: 3 recursos a crear
terraform apply -auto-approve
```

Si no se crea `terraform.tfvars`, Terraform usa los valores por defecto de `variables.tf` (`group_id = "grupo06"`, `host_port = 8080`).

**Verificación:**

```bash
terraform output                       # container_id, container_name, network_name, service_url
docker ps --filter "label=managed-by=terraform"
curl http://localhost:8080             # o abrir en el navegador: página de bienvenida de Nginx
```

**Variables disponibles** (sobrescribibles con `-var` o `terraform.tfvars`):

| Variable | Tipo | Default | Validación |
|---|---|---|---|
| `app_name` | string | `servidor-web` | — |
| `group_id` | string | `grupo06` | — |
| `environment` | string | `dev` | Debe ser `dev`, `staging` o `prod` |
| `host_port` | number | `8080` | — |
| `nginx_version` | string | `1.27-alpine` | — |

Ejemplo: `terraform plan -var="host_port=8081"`.

---

## 6. Despliegue local con Pulumi (puerto 8090)

```bash
cd pulumi

# 1. Backend de estado 100 % local (sin cuenta en pulumi.com)
pulumi login --local

# 2. Entorno virtual de Python
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Seleccionar (o crear) el stack local "dev"
pulumi stack select dev || pulumi stack init dev
#   Si pide passphrase, se puede dejar vacía (Enter) o usar una clave simple.
#   Para no escribirla cada vez:
#   export PULUMI_CONFIG_PASSPHRASE=""            # Linux / macOS
#   $env:PULUMI_CONFIG_PASSPHRASE=""              # Windows PowerShell

# 5. Previsualizar y desplegar
pulumi preview
pulumi up --yes
```

**Verificación:**

```bash
pulumi stack output                    # container_id, container_name, network_name, service_url
docker ps --filter "label=managed-by=pulumi"
curl http://localhost:8090
```

**Configuración del stack** (`Pulumi.dev.yaml`, se modifica con `pulumi config set <clave> <valor>`):

| Clave | Default en código | Validación |
|---|---|---|
| `groupId` | `grupo01` | — |
| `environment` | `dev` | `ValueError` si no es `dev`, `staging` o `prod` |
| `hostPort` | `8090` | Debe ser un entero (`config.get_int`) |
| `nginxVersion` | `1.27-alpine` | — |

Ejemplo: `pulumi config set hostPort 8091`.

---

## 7. Experimento de *drift* (reproducción)

Con ambos stacks desplegados:

```bash
# Terraform: borrar el contenedor por fuera de la herramienta y planear
docker rm -f servidor-web-grupo06-tf
cd terraform && terraform plan          # Detecta el borrado y propone "1 to add"
terraform apply -auto-approve           # Reconcilia (recrea el contenedor)

# Pulumi: borrar el contenedor por fuera de la herramienta y previsualizar con refresh
docker rm -f servidor-web-<groupId>-pulumi
cd ../pulumi && pulumi preview --refresh   # Consulta Docker y propone "1 to create"
pulumi up --refresh --yes                  # Reconcilia (recrea el contenedor)
```

> `terraform plan` refresca el estado por defecto. `pulumi preview` **sin** `--refresh` confía en el estado guardado y no detecta el borrado.

Los resultados y el análisis están en [`docs/informe_comparativo.md`](docs/informe_comparativo.md).

---

## 8. Validación Shift-Left y destrucción limpia

### Linters locales (lo mismo que ejecuta el pipeline)

```bash
# Terraform
cd terraform
terraform fmt -check -diff
terraform init -backend=false
terraform validate

# Pulumi (Python)
cd ../pulumi
pip install ruff flake8
ruff check .            # o: ruff check . --fix / ruff format .
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

El workflow [`.github/workflows/iac-ci.yml`](.github/workflows/iac-ci.yml) corre estos dos *quality gates* (`validate-terraform` y `validate-pulumi`) en cada Pull Request y en cada push a `main`.

### Destrucción limpia ($0 residuos)

```bash
cd terraform && terraform destroy -auto-approve
cd ../pulumi && pulumi destroy --yes

# Verificar que no queden recursos huérfanos
docker ps -a --filter "name=servidor-web"
docker network ls --filter "name=servidor-web"
```

Opcional, para borrar también el stack de Pulumi: `pulumi stack rm dev`.

---

## 9. Notas y observaciones del repositorio

- `terraform.tfvars.example` está en la raíz del repositorio. La guía lo ubica en `terraform/terraform.tfvars.example`, así que conviene moverlo allí y cambiar `group_id = "grupo01"` por `"grupo06"`.
- `pulumi/Pulumi.dev.yaml` tiene `groupId: grupo01`. Con ese valor los recursos de Pulumi se llaman `servidor-web-grupo01-pulumi(-net)`. Para alinearlo con el grupo: `pulumi config set groupId grupo06`.
- Archivos que **no** deben subirse (ya excluidos en `.gitignore`): `*.tfstate`, `.terraform/`, `.terraform.lock.hcl`, `terraform.tfvars`, `venv/`, `__pycache__/`.

---

## 10. Solución de problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker no está corriendo | Iniciar Docker Desktop o `sudo systemctl start docker`; verificar con `docker ps` |
| `Bind for 127.0.0.1:8080 failed: port is already allocated` | Puerto 8080 ocupado | `host_port = 8081` en `terraform.tfvars` y volver a aplicar |
| `Bind for 127.0.0.1:8090 failed: port is already allocated` | Puerto 8090 ocupado | `pulumi config set hostPort 8091` |
| `pulumi: error: no current stack` | No hay stack seleccionado | `pulumi stack select dev` o `pulumi stack init dev` |
| `pulumi login` pide credenciales web | Intenta conectarse a Pulumi Cloud | `pulumi login --local` |
| `No module named 'pulumi_docker'` | venv inactivo o sin dependencias | Activar `venv` y `pip install -r requirements.txt` |
| `terraform validate` falla en `validation` | Terraform < 1.3 | Actualizar a >= 1.5.0 |
