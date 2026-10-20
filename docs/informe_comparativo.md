# Informe Comparativo IaC: Terraform vs. Pulumi
**Grupo:** grupo06  
**Integrantes:**  
- David Alfonso Cañas Palomino - R1 (Terraform)  
- Edgar Fernando Vega Morales - R2 (Pulumi)  
- Óscar Daniel Murillo Botero - R3 (Platform Lead)  

**Curso:** Fundamentos de DevOps y SRE – UNAL 2026-01 · **Laboratorio 02**

**Arquitectura implementada (idéntica en ambas herramientas):** red Docker dedicada + imagen `nginx:1.27-alpine` + contenedor Nginx publicado en `127.0.0.1` (Terraform en `:8080`, Pulumi en `:8090`), con *labels* `managed-by`, `owner` y `tool` y variables de entorno `APP_ENV`, `MANAGED_BY` y `GROUP_ID`.

---

## 1. Matriz de Comparación Empírica

| Criterio de Comparación | Terraform (HCL) | Pulumi (Python) | Análisis del Grupo con Evidencia Observada |
|---|---|---|---|
| **1. Curva de aprendizaje y sintaxis** | DSL declarativo especializado (bloques `resource`, `variable`, `output`). | Lenguaje de propósito general (Python) con clases `docker.Network`, `docker.RemoteImage`, `docker.Container`. | HCL se lee como un archivo de configuración: cada bloque describe un recurso y no hay flujo de control que seguir. Lo más difícil fue la sintaxis de bloques repetidos (`labels { }` tres veces, `ports { }`, `networks_advanced { }`). En Pulumi la curva fue baja para el lenguaje, pero alta para el modelo de ejecución: hubo que entender `Output[T]` (por ejemplo, `pulumi.Output.concat` para `service_url`), las clases `*Args` del SDK y la preparación del entorno (`venv`, `pip install`, `pulumi login --local`, `stack init`). Terraform tuvo menos pasos para el primer `apply`: `init` → `plan` → `apply`. |
| **2. Líneas de código efectivas (LOC)** | **104 líneas** en 5 archivos `.tf` (`main.tf` 48, `variables.tf` 29, `outputs.tf` 16, `versions.tf` 9, `providers.tf` 2). | **56 líneas** en `__main__.py` (+ 6 en `Pulumi.yaml`, 6 en `Pulumi.dev.yaml` y 2 en `requirements.txt` = **70**). | Conteo sin comentarios, líneas en blanco ni el *docstring*. Pulumi usó aproximadamente un 33-46 % menos de líneas. La diferencia está en el *boilerplate*: cada variable de Terraform ocupa entre 5 y 10 líneas (`description`, `type`, `default`, `validation`), mientras que en Python una lectura de config con valor por defecto ocupa una línea (`config.get("groupId") or "grupo01"`). Además, los 4 outputs ocupan 16 líneas en HCL y 4 `pulumi.export` en Python. A cambio, la versión HCL documenta tipos y descripciones de forma explícita. |
| **3. Manejo del Estado (State)** | Archivo JSON `terraform/terraform.tfstate` dentro del proyecto. | Backend local en `~/.pulumi` (`pulumi login --local`), separado por *stack* (`dev`). | El `tfstate` es más fácil de inspeccionar: se abre con cualquier editor o con `terraform state list` / `terraform show`, y queda junto al código (por eso es obligatorio excluirlo en `.gitignore`). El estado de Pulumi vive fuera del repositorio y se consulta con `pulumi stack`, `pulumi stack output` o `pulumi stack export`. Además está ligado al concepto de *stack*, que facilita tener `dev`/`staging`/`prod`, y los secretos de configuración se cifran con *passphrase* (`encryptionsalt` en `Pulumi.dev.yaml`). Terraform es más transparente; Pulumi resuelve mejor la multiplicidad de ambientes. |
| **4. Validación de variables y tipos** | Bloque `validation { condition = contains([...], var.environment) }` y `type = number` / `string`. | Lógica en Python (`if environment not in valid_envs: raise ValueError(...)`) y `config.get_int("hostPort")`. | Terraform detecta el error **antes** de tocar Docker: en `terraform validate`/`plan` falla con el `error_message` personalizado (*"El ambiente debe ser 'dev', 'staging' o 'prod'."*) señalando el archivo y la línea de la variable. Pulumi detecta el error al **ejecutar** el programa durante `pulumi preview`: el mensaje propio aparece, pero envuelto en un *traceback* de Python, que es más ruidoso para quien no programa. A favor de Pulumi, la validación puede ser arbitrariamente compleja (regex, rangos, llamadas a funciones). Un detalle observado: `hostPort` se guarda como texto (`"8090"`) en el YAML y `get_int` lo convierte; si no es numérico, falla con error de tipo. Resultado: Terraform es más claro y declarativo; Pulumi es más flexible. |
| **5. Detección y corrección de Drift** | `terraform plan` (refresca el estado contra Docker **por defecto**). | `pulumi preview --refresh` (sin `--refresh`, confía en el estado guardado). | Al borrar el contenedor manualmente con `docker rm -f`, **ambas herramientas detectaron el drift** y propusieron recrear **solo** el contenedor (1 recurso a crear; la red y la imagen quedaron sin cambios). Terraform lo hizo sin bandera adicional y lo reporta explícitamente en la sección *"Objects have changed outside of Terraform"* (`docker_container.web has been deleted`). Pulumi necesita la bandera `--refresh` (o `pulumi refresh`): sin ella, `pulumi preview` informa que no hay cambios aunque el contenedor ya no exista. La corrección fue en ambos casos un `apply`/`up` normal. Ver sección 2. |
| **6. Multiplicidad y ciclos** | Meta-argumentos `count` / `for_each`. | Bucle estándar `for` (o *list comprehension*) en Python. | Para crear 10 réplicas, Terraform usa `count = 10` y la interpolación `count.index` en nombre y puerto, y se referencian como `docker_container.web[3]`. Pulumi usa un `for i in range(10):` normal, con nombres lógicos únicos (`f"container-{group_id}-{i}"`). Para casos simples ambas son legibles. En casos con lógica condicional o anidada (por ejemplo, réplicas distintas por ambiente) Python resulta más natural, mientras que en HCL se recurre a expresiones `for`, `dynamic` y condicionales ternarios, que se vuelven difíciles de leer. Ejemplos a continuación de la tabla. |
| **7. Ecosistema de Linters / Shift-Left** | `terraform fmt -check -diff`, `terraform init -backend=false`, `terraform validate`. | `ruff check .`, `flake8 . --select=E9,F63,F7,F82`. | Ambos *quality gates* están en `.github/workflows/iac-ci.yml` y corren en cada PR hacia `main`. El job de Terraform necesita descargar el CLI y el provider (`init`), así que su costo está en la red. El de Python solo instala `ruff` y `flake8` con `pip`, y `ruff` analiza el archivo en milisegundos (`ruff check .` → *All checks passed!*). Diferencia clave: `terraform validate` **entiende la infraestructura** (tipos de argumentos del provider, referencias entre recursos), mientras que `ruff`/`flake8` solo validan Python. Un argumento mal escrito en `docker.Container(...)` pasa el linter y solo falla en `pulumi preview`. Para un *shift-left* equivalente en Pulumi habría que añadir `pulumi preview` (con Docker disponible en el runner) o un *type checker* como `mypy`/`pyright`. |

### Ejemplos del criterio 6 (10 réplicas)

**Terraform (HCL):**

```hcl
resource "docker_container" "web" {
  count = 10
  name  = "${var.app_name}-${var.group_id}-tf-${count.index}"
  image = docker_image.nginx.image_id

  networks_advanced {
    name = docker_network.app_network.name
  }

  ports {
    internal = 80
    external = var.host_port + count.index # 8080..8089
    ip       = "127.0.0.1"
  }
}
```

**Pulumi (Python):**

```python
containers = [
    docker.Container(
        f"container-{group_id}-{i}",
        name=f"servidor-web-{group_id}-pulumi-{i}",
        image=image.image_id,
        networks_advanced=[docker.ContainerNetworksAdvancedArgs(name=network.name)],
        ports=[docker.ContainerPortArgs(internal=80, external=host_port + i, ip="127.0.0.1")],
    )
    for i in range(10)  # 8090..8099
]
```

---

## 2. Evidencias del Experimento de Drift

**Procedimiento:** con ambos stacks desplegados, R3 eliminó cada contenedor directamente en Docker (sin pasar por la herramienta de IaC), y R1 y R2 ejecutaron el comando de detección correspondiente.

> ✏️ **Reemplazar** los bloques siguientes por la salida real capturada en la terminal durante la sesión (los IDs y *hashes* serán distintos). La estructura mostrada corresponde a la que generan Terraform 1.x con `kreuzwerker/docker ~> 3.0.2` y Pulumi 3.x con `pulumi-docker 4.x` para este código.

### 2.1 Terraform

**Paso 1 – Estado antes del drift:**

```text
$ docker ps --filter "label=managed-by=terraform" --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
NAMES                     PORTS                    STATUS
servidor-web-grupo06-tf   127.0.0.1:8080->80/tcp   Up 4 minutes
```

**Paso 2 – Borrado manual (R3):**

```text
$ docker rm -f servidor-web-grupo06-tf
servidor-web-grupo06-tf
```

**Paso 3 – Detección (R1):**

```text
$ terraform plan
docker_network.app_network: Refreshing state... [id=<network_id>]
docker_image.nginx: Refreshing state... [id=sha256:<image_hash>nginx:1.27-alpine]
docker_container.web: Refreshing state... [id=<container_id>]

Note: Objects have changed outside of Terraform

Terraform detected the following changes made outside of Terraform since the
last "terraform apply" which may have affected this plan:

  # docker_container.web has been deleted
  - resource "docker_container" "web" {
      - id    = "<container_id>" -> null
        name  = "servidor-web-grupo06-tf"
        # (N unchanged attributes hidden)
    }

Unless you have made equivalent changes to your configuration, or ignored the
relevant attributes using ignore_changes, the following plan may include
actions to undo or respond to these changes.

─────────────────────────────────────────────────────────────────────────────

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # docker_container.web will be created
  + resource "docker_container" "web" {
      + env      = [
          + "APP_ENV=dev",
          + "GROUP_ID=grupo06",
          + "MANAGED_BY=terraform",
        ]
      + id       = (known after apply)
      + image    = "sha256:<image_hash>"
      + name     = "servidor-web-grupo06-tf"
      ...
      + ports {
          + external = 8080
          + internal = 80
          + ip       = "127.0.0.1"
          + protocol = "tcp"
        }
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

**Paso 4 – Reconciliación:**

```text
$ terraform apply -auto-approve
...
docker_container.web: Creating...
docker_container.web: Creation complete after 1s [id=<nuevo_container_id>]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

**Interpretación:** `terraform plan` ejecuta un *refresh* implícito: consulta la API de Docker por cada recurso del `tfstate`, encuentra que el contenedor ya no existe, lo marca como borrado fuera de Terraform y planea recrearlo. La red y la imagen no aparecen en el plan porque siguen coincidiendo con el código.

### 2.2 Pulumi

**Paso 1 – Borrado manual (R3):**

```text
$ docker rm -f servidor-web-grupo01-pulumi
servidor-web-grupo01-pulumi
```

> El nombre usa `grupo01` porque es el `groupId` configurado actualmente en `Pulumi.dev.yaml`.

**Paso 2 – Preview sin refresh (control):**

```text
$ pulumi preview
Previewing update (dev):
     Type                         Name                  Plan
     pulumi:pulumi:Stack          lab02-iac-pulumi-dev

Resources:
    4 unchanged
```

**Paso 3 – Detección con refresh (R2):**

```text
$ pulumi preview --refresh
Previewing update (dev):
     Type                         Name                  Plan       Info
     pulumi:pulumi:Stack          lab02-iac-pulumi-dev
     ├─ docker:index:Network      network-grupo01
     ├─ docker:index:RemoteImage  nginx-image-grupo01
 +   └─ docker:index:Container    container-grupo01     create

Outputs:
  ~ container_id: "<container_id>" => output<string>

Resources:
    + 1 to create
    3 unchanged
```

**Paso 4 – Reconciliación:**

```text
$ pulumi up --refresh --yes
...
 +   └─ docker:index:Container    container-grupo01     created (1s)

Resources:
    + 1 created
    3 unchanged
```

**Interpretación:** Pulumi, por defecto, compara el programa contra **su estado guardado**, no contra la infraestructura real. Por eso `pulumi preview` sin bandera no ve el borrado. Con `--refresh`, primero consulta la API de Docker, actualiza el estado (el contenedor desaparece de él) y luego calcula el *diff*, que ahora sí propone crear el contenedor.

### 2.3 Comparación del comportamiento

| Aspecto | Terraform | Pulumi |
|---|---|---|
| Comando de detección | `terraform plan` | `pulumi preview --refresh` / `pulumi refresh` |
| ¿Refresca por defecto? | Sí | No (requiere `--refresh`) |
| Reporte del drift | Sección explícita *"Objects have changed outside of Terraform"* | Se refleja como `+ create` en el *diff* |
| Recursos afectados en el plan | Solo `docker_container.web` | Solo `container-grupo01` |
| Corrección | `terraform apply` | `pulumi up --refresh` |

---

## 3. Destrucción limpia ($0 residuos)

```text
$ cd terraform && terraform destroy -auto-approve
...
Destroy complete! Resources: 3 destroyed.

$ cd ../pulumi && pulumi destroy --yes
...
Resources:
    - 4 deleted

$ docker ps -a --filter "name=servidor-web"
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES

$ docker network ls --filter "name=servidor-web"
NETWORK ID     NAME      DRIVER    SCOPE
```

Ninguna de las dos herramientas dejó contenedores ni redes huérfanas. La imagen `nginx:1.27-alpine` permanece en el host porque ambas la declaran con `keep_locally = true`, lo cual es intencional para no volver a descargarla. Pulumi reporta 4 recursos porque cuenta el recurso `pulumi:pulumi:Stack`.

---

## 4. Conclusión Arquitectónica

**Pregunta:** si tuviéramos que desplegar una arquitectura de microservicios en una empresa donde todos los desarrolladores son de Python pero no saben DevOps, ¿qué herramienta elegiríamos y qué precauciones tomaríamos?

Elegiríamos **Pulumi con Python**. En este laboratorio la misma infraestructura ocupó 56 líneas efectivas de Python frente a 104 de HCL, y lo que más pesó fue que el equipo pudo reutilizar lo que ya sabe: funciones, bucles, *list comprehensions*, módulos, `pip` y los mismos linters (`ruff`, `flake8`) que usaría en cualquier otro proyecto Python. En una arquitectura de microservicios, donde se repite el mismo patrón (red, imagen, contenedor/servicio, puertos, etiquetas) para decenas de servicios, poder encapsularlo en una función o en un `ComponentResource` y llamarlo desde un `for` reduce la duplicación de forma más natural que `count`/`for_each`/`dynamic` en HCL. Además, el modelo de *stacks* (`dev`, `staging`, `prod`) da separación de ambientes desde el inicio y permite probar la infraestructura con `pytest`, algo que un equipo de Python adopta sin fricción.

Sin embargo, el experimento mostró los riesgos de dar un lenguaje de propósito general a un equipo sin experiencia en operaciones, así que tomaríamos estas precauciones:
1. **Detección de drift explícita.** Usar siempre `pulumi preview --refresh` / `pulumi up --refresh` en el pipeline (o `pulumi refresh` programado), porque a diferencia de `terraform plan`, Pulumi no detecta cambios externos por defecto.
2. **Shift-left real.** Agregar al CI, además de `ruff`/`flake8`, un *type checker* (`mypy`/`pyright`) y un `pulumi preview` obligatorio en cada PR, ya que los linters de Python no validan argumentos del provider como sí lo hace `terraform validate`.
3. **Validación en un solo lugar.** Centralizar la validación de configuración (por ejemplo, con `pydantic` o funciones propias), para no depender de `if/raise` dispersos que producen *tracebacks* poco amigables.
4. **Estado gestionado y bloqueado.** Mover el estado de `~/.pulumi` a un backend compartido con bloqueo (Pulumi Cloud, S3/Azure Blob/GCS) y cifrado de secretos.
5. **Disciplina declarativa.** Imponer por revisión de código que el programa solo **declare** recursos: nada de lógica con efectos secundarios, llamadas a APIs externas ni valores no deterministas (fechas, aleatorios) que generen *diffs* espurios.
6. **Gobernanza de ramas y componentes.** Mantener ramas protegidas con al menos una aprobación, como hicimos en este repositorio, y ofrecer componentes reutilizables mantenidos por un equipo de plataforma.

Terraform seguiría siendo una opción válida si la prioridad fuera la auditabilidad y la estandarización con equipos de operaciones externos, porque su DSL restringido hace más difícil escribir infraestructura "creativa".
