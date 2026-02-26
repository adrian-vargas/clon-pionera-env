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
sudo apt install python3.10-venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r runtime/workdir/inesdata-deployment/requirements.txt
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
- El entorno queda listo para ejecutar operaciones lógicas de INESData en los niveles posteriores.

---

⬅️ [Nivel anterior: Nivel 3 – Post-configuración de Vault y Deployer](../nivel-3/README.md)  
➡️ [Siguiente nivel: Nivel 5 – Creación lógica del Dataspace](../nivel-5/README.md)
🏠 [Volver al README principal](/README.md)