### Arquitectura del ambiente de pruebas (lectura rápida)

![Arquitectura del ambiente de pruebas A5.2](docs/arquitectura-ambiente-pruebas.png)

Este repositorio soporta el ambiente de pruebas de PIONERA para PT5 – A5.2.
La arquitectura está pensada como un entorno de validación reproducible.

Espacio de datos de referencia: INESData

- Los roles de Provider y Consumer se instancian dentro del espacio de datos (INESData).
- Los componentes PIONERA operan fuera del plano de interoperabilidad del espacio de datos.
- El protocolo de interoperabilidad se utiliza exclusivamente entre los conectores del espacio de datos.
- Los resultados del AI Model Hub quedan fuera del plano del espacio de datos y se consumen a nivel de aplicación vía API.

Componentes PIONERA:
- Ontology Hub: gestiona ontologías y modelos semánticos. No consume datasets ni interactúa con componentes de IA directamente.
- Semantic Virtualizer: consume datasets instrumentales y aplica semántica. Es el único punto de acceso a los datos desde el espacio de datos.
- AI Model Hub: consume datos virtualizados una vez autorizado el acceso y ejecuta modelos de IA. Sus resultados quedan fuera del plano de interoperabilidad del espacio de datos.

Otros elementos:
- Los datasets son instrumentales y solo alimentan al Semantic Virtualizer.
- El Provider Connector accede al Semantic Virtualizer mediante APIs internas (HTTP/SPARQL).
- El protocolo de interoperabilidad (DSP) se utiliza exclusivamente entre Provider y Consumer.
- Un portal unificado actúa como capa de visualización (resultados de IA y estado del Consumer), sin participar en mecanismos del espacio de datos.

---

# Despliegue reproducible de un demo de INESData para validación en PIONERA

Este documento describe el flujo completo, reproducible y mayoritariamente automatizado para desplegar un demo de INESData en un entorno de pruebas basado en WSL, el cual debe estar habilitado en el sistema anfitrión. INESData se integra en el ecosistema PIONERA con el objetivo de servir como escenario instrumental para la validación técnica de componentes en la actividad A5.2.

---

## Convenciones usadas

- **Ruta**: directorio desde el que deben ejecutarse los comandos indicados
- **Comando**: acción a ejecutar en la terminal
- **Salida esperada**: estado o resultado observable que confirma la correcta ejecución del paso
- **Propósito**: justificación técnica del paso dentro del flujo de validación

---

# NIVEL 0 – Prerrequisitos del sistema (manual)
> **Precondiciones técnicas:** 
> - La ejecución de este flujo se realiza desde una terminal WSL.
> - El entorno de validación asume que Docker Desktop de Windows está configurado para utilizar el motor WSL 2. Otras opciones de configuración de Docker Desktop no son relevantes para la ejecución de este flujo.


### Propósito
Preparar el sistema anfitrión. No automatizado por diseño, ya que depende del entorno local.

### Requisitos
Las siguientes herramientas deben estar instaladas y accesibles desde la terminal:

- Docker Desktop (en ejecución)
- kubectl
- Minikube
- Helm
- **Python 3.10**  
  Instalado siguiendo la guía externa utilizada en este entorno:  
  [Guía de instalación de Python 3.10 en Linux/WSL](https://gist.github.com/rutcreate/c0041e842f858ceb455b748809763ddb)

---

### Instalación de herramientas (si aplica)

> Este bloque solo es necesario si las herramientas no están instaladas.

**Minikube (Linux / WSL):**
```bash
curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
```
**Helm (Linux / WSL):**
```bash
sudo snap install helm --classic
```

### Verificación
```bash
docker ps
kubectl --help
helm version
python3 --version
```

**Ejemplo de salida esperada**
```text
$ docker ps
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES

$ kubectl --help
kubectl controls the Kubernetes cluster manager.
Find more information at: https://kubernetes.io/docs/reference/kubectl/

$ helm version
version.BuildInfo{Version:"v3.x.x", GitCommit:"...", GitTreeState:"clean", GoVersion:"go1.xx.x"}

$ python3 --version
Python 3.10.x
```

**Criterio de aceptación**
Todos los comandos responden sin error.

---

# NIVEL 1 – Creación del clúster Kubernetes local (Minikube)

### Propósito
Crear un clúster Kubernetes local limpio, reproducible y aislado que sirva como base técnica para la validación de componentes del ecosistema PIONERA en la actividad A5.2.

### Ruta
Terminal del sistema (fuera del directorio del proyecto).

> **Precondición técnica:**  
> Docker Desktop debe estar en ejecución antes de iniciar Minikube, ya que el clúster Kubernetes se despliega utilizando el driver docker.

---

### Comandos
```bash
minikube delete --all --purge
minikube start --driver=docker --cpus=4 --memory=4400
minikube addons enable ingress
```

### Verificación
```bash
minikube status
kubectl get pods -n ingress-nginx
```

**Ejemplo de salida esperada**
```text
$ minikube status
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured

$ kubectl get pods -n ingress-nginx
NAME                                        READY   STATUS      RESTARTS   AGE
ingress-nginx-controller-xxxx               1/1     Running     0          1m
ingress-nginx-admission-create-xxxx         0/1     Completed   0          1m
ingress-nginx-admission-patch-xxxx          0/1     Completed   0          1m
```
**Criterio de aceptación**
El clúster Minikube se encuentra en estado Running y los pods del namespace ingress-nginx están creados y en estado Running o Completed.

---

# NIVEL 2 – Instalación base de INESData (servicios comunes)

### Propósito
Proporcionar a INESData un conjunto mínimo de servicios comunes operativos, necesarios para habilitar la creación y gestión de dataspaces y conectores. Este nivel establece el estado base requerido del sistema para poder ejecutar de forma controlada los escenarios de validación definidos en la actividad A5.2.

---

### Ruta
```text
pionera-env/
```

### Ejecutar `install.py` (automatización)
> **Precondiciones técnicas:**  
> El entorno debe disponer de kubectl y helm operativos, así como de los artefactos de configuración requeridos para los servicios comunes. Estas precondiciones son verificadas automáticamente por el script.

Este comando despliega los servicios comunes de INESData de forma no interactiva, idempotente y QA-safe, aplicando validaciones previas y mecanismos de limpieza controlada en caso de fallo.

```bash
python adapters/inesdata/install.py
```

### Verificación
```bash
kubectl get pods -n common-srvs
```
**Ejemplo de salida esperada**
```text
NAME                                   READY   STATUS    RESTARTS   AGE
common-srvs-postgresql-0               1/1     Running   0          2m
common-srvs-keycloak-0                 1/1     Running   0          2m
common-srvs-vault-0                    1/1     Running   0          2m
common-srvs-minio-0                    1/1     Running   0          2m
```
**Criterio de aceptación**
Todos los pods del namespace common-srvs se encuentran en estado Running.
---

# NIVEL 3 – Post-configuración de Vault y Deployer

### Propósito
Garantizar que Vault se encuentra correctamente inicializado y operativo, habilitando la gestión segura de secretos requerida por INESData, y generar la configuración necesaria para que el Deployer pueda interactuar de forma segura y controlada con los servicios comunes. Este nivel establece los artefactos y credenciales necesarios para habilitar la creación posterior de dataspaces y conectores durante la ejecución de la validación en A5.2.

### Ruta
```text
pionera-env/
```

### Inicialización de Vault (una sola vez)
> - Este paso solo es necesario si Vault no ha sido inicializado previamente en el entorno de pruebas.
> - La inicialización de Vault debe ejecutarse desde el directorio `runtime/workdir/inesdata-deployment/common`, ya que en esta ubicación se genera y gestiona el artefacto `runtime/workdir/inesdata-deployment/common/init-keys-vault.json`, utilizado posteriormente por los scripts de automatización.

1. Ingresar a la carpeta common:
```bash
cd runtime/workdir/inesdata-deployment/common
```
2. El siguiente comando genera el fichero init-keys-vault.json, que contiene las claves necesarias para el proceso de unseal y el acceso inicial a Vault.
```bash
kubectl exec -it common-srvs-vault-0 -n common-srvs -- \
  vault operator init -key-shares=1 -key-threshold=1 -format=json > init-keys-vault.json
```

### Ejecutar `post-common.py` (automatizado)
> **Precondición técnica:**  
> Antes de ejecutar el comando automatizado, debe existir un túnel activo hacia Vault, ya que el script interactúa con Vault a través de la dirección local http://127.0.0.1:8200.
```bash
kubectl port-forward common-srvs-vault-0 -n common-srvs 8200:8200
```
Este script realiza de forma no interactiva e idempotente las siguientes acciones:
- Verifica que Vault está accesible.
- Ejecuta el unseal automático si procede.
- Verifica o habilita el Secrets Engine de tipo KV en la ruta secret.
- Genera o ajusta el fichero deployer.config a partir del estado real del clúster.

```bash
cd ../../../..
python adapters/inesdata/normalize/post-common.py
```

### Verificación
```bash
kubectl exec -it common-srvs-vault-0 -n common-srvs -- vault status
```
**Ejemplo de salida esperada**
```text
$ kubectl exec -it common-srvs-vault-0 -n common-srvs -- vault status
Key             Value
---             -----
Seal Type       shamir
Initialized     true
Sealed          false
Total Shares    1
Threshold       1
Version         1.17.2
Build Date      2024-07-05T15:19:12Z
Storage Type    file
Cluster Name    vault-cluster-3b623214
Cluster ID      26b6afea-6c0f-0db0-0bfc-05ec1d95575d
HA Enabled      false
```
**Criterios de aceptación**
- Vault se encuentra correctamente inicializado y operativo:
  - `Initialized`: true
  - `Sealed`: false
- Existe el fichero `init-keys-vault.json` en la ruta esperada.
- El fichero deployer.config ha sido actualizado correctamente.

**Artefactos generados**
```text
runtime/workdir/inesdata-deployment/common/init-keys-vault.json
runtime/workdir/inesdata-deployment/deployer.config
```

# NIVEL 4 – Preparación del entorno Deployer

### Propósito
Preparar un entorno de ejecución local, aislado y reproducible que permita al Deployer de INESData interactuar de forma controlada con los servicios comunes ya desplegados. Este nivel habilita la ejecución de operaciones lógicas sobre INESData (creación de dataspaces y generación de artefactos) sin modificar directamente la infraestructura Kubernetes, en el contexto de la validación definida en A5.2.

### Ruta
```text
runtime/workdir/inesdata-deployment/
```
### Preparación del entorno Python (una sola vez)
Este entorno virtual aisla el deployer de dependencias y evita interferencias con el sistema anfitrión.
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
### Precondiciones técnicas (túneles requeridos)
Durante la ejecución de este nivel (y de los niveles lógicos posteriores), deben mantenerse activos los siguientes túneles hacia los servicios comunes:
```bash
kubectl port-forward common-srvs-postgresql-0 -n common-srvs 5432:5432 &
kubectl port-forward common-srvs-vault-0 -n common-srvs 8200:8200 &
kubectl port-forward common-srvs-keycloak-0 -n common-srvs 8080:8080 &
```
Estos túneles exponen interfaces locales necesarias para que el Deployer interactúe con los servicios comunes sin exponerlos fuera del clúster.

### Verificación
```bash
source venv/bin/activate
python3 deployer.py --help
```
**Ejemplo de salida esperada**
```bash
(venv) avargas@host:
Usage: deployer.py [OPTIONS] COMMAND [ARGS]...
...
```

**Criterios de aceptación**
- El entorno virtual Python está activo y funcional.
- El Deployer responde correctamente a comandos básicos (`--help`).
- Los túneles a los servicios comunes permanecen activos.
- El entorno queda listo para ejecutar operaciones lógicas de INESData en los niveles posteriores..

---

# NIVEL 5 – Creación lógica del Dataspace

### Propósito
Crear de forma lógica un dataspace de INESData y generar los artefactos de configuración necesarios para su despliegue posterior. Este nivel ejecuta operaciones declarativas a través del Deployer, sin aplicar cambios directos sobre la infraestructura Kubernetes ni sobre los servicios comunes, en el contexto de la validación definida en A5.2.

### Ruta
```
pionera-env/
```

### Ejecutar `dataspace-create.py` (automatización)
> **Precondiciones técnicas:**
> El entorno Deployer debe encontrarse preparado conforme a lo establecido en el NIVEL 4, incluyendo entorno virtual activo, túneles a los servicios comunes y disponibilidad del fichero `deployer.config`.

Este script se ejecuta de forma no interactiva, idempotente y QA-safe y:
- invoca al Deployer para crear el dataspace a nivel lógico,
- normaliza los ficheros values.yaml generados,
- prepara artefactos consistentes para su uso en el despliegue Helm del NIVEL 6.

```bash
python adapters/inesdata/dataspace/dataspace-create.py
```
### Verificación
```bash
ls runtime/workdir/inesdata-deployment/dataspace/step-1/values-demo.yaml
ls runtime/workdir/inesdata-deployment/dataspace/step-2/values-demo.yaml
```
**Ejemplo de salida esperada**
```text
runtime/workdir/inesdata-deployment/dataspace/step-1/values-demo.yaml
runtime/workdir/inesdata-deployment/dataspace/step-2/values-demo.yaml
```

### Artefactos generados
```text
runtime/workdir/inesdata-deployment/dataspace/step-1/values-demo.yaml
runtime/workdir/inesdata-deployment/dataspace/step-2/values-demo.yaml
```

### Criterios de aceptación
- El dataspace lógico ha sido creado sin errores.
- Los ficheros `values-demo.yaml` existen en las rutas esperadas.
- Los artefactos generados están listos para su uso directo por Helm en el NIVEL 6.

---

# NIVEL 6 – Despliegue del Dataspace (infraestructura)

### Propósito
Materializar en infraestructura Kubernetes el dataspace definido de forma lógica en el NIVEL 5, desplegando los componentes necesarios para su funcionamiento operativo. Este nivel aplica cambios controlados sobre la infraestructura (base de datos y servicios) de forma reproducible y QA-safe, en el contexto de la validación definida en A5.2.

### Ruta
```
pionera-env/
```

### Ejecutar `dataspace-deploy.py` (automatización)
> **Precondiciones técnicas:**
> - El dataspace debe haber sido creado lógicamente en el NIVEL 5.
> - Debe existir el fichero values-demo.yaml en `runtime/workdir/inesdata-deployment/dataspace/step-1/`.
> - Los servicios comunes (PostgreSQL) deben encontrarse operativos conforme al NIVEL 2.

Este script se ejecuta de forma no interactiva, idempotente y QA-safe y:
- verifica la disponibilidad real de PostgreSQL,
- ejecuta un reset controlado de la base de datos del dataspace,
- despliega el `registration-service` mediante Helm (`Step-1`),
- garantiza la existencia y alineación de `ConfigMap` y `Secret` usados por el Deployment,
- fuerza un reinicio controlado del servicio para asegurar la correcta aplicación de la configuración,
- garantiza la inicialización del esquema EDC requerido (`edc_participant`).
```bash
python adapters/inesdata/dataspace/dataspace-deploy.py
```

### Verificación
```bash
kubectl get pods -n demo
```
**Ejemplo de salida esperada**
```text
NAME                                         READY   STATUS    RESTARTS   AGE
demo-registration-service-xxxxxxxxxx-xxxxx   1/1     Running   0          1m
```
### Criterios de aceptación
- El namespace del dataspace (`demo`) existe y es accesible.
- El pod `demo-registration-service` se encuentra en estado `Running`.
- La base de datos del dataspace ha sido creada y asociada correctamente.
- El Deployment utiliza `ConfigMap` y `Secret` reales del clúster.
- El servicio queda listo para su uso en los niveles posteriores (NIVEL 7 – conectores).
---

# NIVEL 7 – Creación de Conector (lógico)

### Propósito
Crear de forma lógica un connector de INESData asociado al dataspace ya desplegado, registrándolo correctamente en el esquema EDC y generando los artefactos de configuración necesarios para su despliegue posterior. Este nivel ejecuta operaciones controladas y QA-safe sobre los metadatos y bases de datos de soporte, sin aplicar despliegues Helm ni modificar directamente la infraestructura Kubernetes, en el contexto de la validación definida en A5.2.

### Ruta
```
pionera-env/
```

### Ejecutar `connector-create.py` (automatización)
> **Precondiciones técnicas:**
> - El dataspace debe encontrarse desplegado conforme al NIVEL 6.
> - Debe existir el fichero `values-demo.yaml` del dataspace (`Step-1`).
> - El servicio registration-service debe encontrarse operativo.
> - El esquema EDC (`edc_participant`) debe estar inicializado.
> - El entorno Deployer debe estar preparado conforme al NIVEL 4.

Este script se ejecuta de forma no interactiva, idempotente y QA-safe y:
- verifica las precondiciones del entorno INESData,
- valida la existencia del esquema EDC (`edc_participant`),
- ejecuta una limpieza controlada de bases de datos, roles y registros previos,
- crea lógicamente el connector mediante el Deployer,
- registra el connector en el esquema EDC,
- normaliza los ficheros `values.yaml` generados.
```bash
python adapters/inesdata/connector/connector-create.py
```
### Verificación
> Nota: La contraseña se define en los scripts de automatización del entorno de validación QA (por ejemplo, `dataspace-create.py` y `dataspace-deploy.py`) y se refleja automáticamente en los ficheros `values.yaml` generados bajo `runtime/workdir/inesdata-deployment/common/`. Utilizar dicha credencial en lugar de `<postgres_password>`. Esta contraseña se emplea únicamente con fines de prueba.

```bash
kubectl exec -n common-srvs common-srvs-postgresql-0 -- \
  sh -c "PGPASSWORD=<postgres_password> psql -U postgres -d demo_rs -c \"SELECT participant_id FROM public.edc_participant;\""

```
**Ejemplo de salida esperada:**
```bash
 participant_id 
----------------
 conn-oeg-demo
(1 row)
```

### Artefactos generados
```text
runtime/workdir/inesdata-deployment/connector/values-conn-oeg-demo.yaml
```
### Criterios de aceptación
- El connector se encuentra registrado en la tabla `public.edc_participant`.
- No existen restos inconsistentes de ejecuciones previas (limpieza QA-safe).
- El fichero `values-conn-oeg-demo.yaml` existe y está normalizado.
- El entorno queda listo para el despliegue del connector en fases posteriores (si aplica).

---

# NIVEL 8 – Despliegue del Connector (infraestructura)

### Propósito
Materializar en infraestructura Kubernetes el connector definido de forma lógica en el NIVEL 7 y permitir su ejecución operativa dentro del dataspace desplegado. Este nivel completa la integración instrumental de INESData en el ecosistema PIONERA y valida la interoperabilidad real entre servicios, la resolución DNS cross-namespace y la inicialización efectiva de recursos persistentes.

### Ruta
```text
pionera-env/
```

### Ejecutar `connector-deploy.py` (automatización)
> **Precondiciones técnicas:**
> - El dataspace debe encontrarse desplegado conforme al NIVEL 6.
> - El connector debe haber sido creado lógicamente en el NIVEL 7.
> - Debe existir el fichero `values-<connector>.yaml` normalizado.
> - Los servicios comunes (PostgreSQL, Vault, Keycloak) deben encontrarse operativos.
> - El entorno Deployer debe estar preparado conforme al NIVEL 4.

Este script:
- aplica un parche Helm-safe al chart del connector (resolviendo dependencias estructurales),
- normaliza los valores de configuración requeridos por Helm,
- corrige automáticamente la resolución DNS cross-namespace hacia PostgreSQL,
- despliega el connector mediante `helm upgrade --install`,
- verifica el estado inicial del despliegue y la correcta ejecución de los initContainers.

```text
python adapters/inesdata/connector/connector-deploy.py
```

### Verificación
```text
kubectl get pods -n demo
```

**Ejemplo de salida esperada**
```text
NAME                                         READY   STATUS    RESTARTS   AGE
conn-oeg-demo-xxxxxxxxxx-xxxxx               1/1     Running   0          1m
conn-oeg-demo-interface-xxxxxxxxxx-xxxxx     1/1     Running   0          1m
demo-registration-service-xxxxxxxxxx-xxxxx   1/1     Running   0          19h
```

### Criterios de aceptación
- El connector se encuentra desplegado y en estado Running.
- El `initContainer` del connector se ejecuta correctamente sin errores.
- La base de datos del connector ha sido inicializada.
- La resolución DNS cross-namespace (`*.svc`) es funcional.
- El connector queda operativo dentro del dataspace desplegado.