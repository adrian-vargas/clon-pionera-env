# NIVEL 9 - Despliegue del Portal Público (infraestructura)

### Propósito

Este nivel confirma que el Portal se despliega correctamente en Kubernetes, que puede conectarse a la base de datos y a los servicios internos del dataspace, y que el despliegue es estable y reproducible conforme a A5.2.

### Ruta

``` text
pionera-env/
```

### Ejecutar `portal-create.py` (fase lógica)

> **Precondiciones técnicas:** 
> - El dataspace y el connector deben estar desplegados y operativos.
> - Los servicios comunes (PostgreSQL, Vault y Keycloak) deben estar en ejecución.
> - El fichero values-demo.yaml debe existir en dataspace/step-2/.
> - El entorno Deployer debe estar configurado (Nivel 4).
> - Cerrar la consola `kubectl port-forward common-srvs-keycloak-0 -n common-srvs 8080:8080 &` para Keycloak, ya que el portal debe operar exclusivamente mediante resolución DNS interna del cluster. No se permite dependencia de port-forward para validación de infraestructura.
> - Abrir un túnel:
``` bash
minikube tunnel
```
> - En caso de que el tunel no resuelva la conexión, ejecutar:
```bash
sudo kubectl --kubeconfig=/home/avargas/.kube/config port-forward -n ingress-nginx deployment/ingress-nginx-controller 80:80
```
Este script:
- verifica la existencia del connector activo
- normaliza automáticamente `values-demo.yaml`
- elimina valores `CHANGEME`
- corrige y normaliza las URLs internas de PostgreSQL y Keycloak para comunicación intra-clúster
- genera backup automático del fichero de configuración
- garantiza la existencia de un alias DNS `ExternalName` para PostgreSQL en el namespace `demo`.

``` text
python3 adapters/inesdata/portal/portal-create.py
```

### Ejecutar `portal-deploy.py` (automatización de despliegue)

Este script: 
- ejecuta `helm upgrade --install` del chart del Portal
- espera de forma controlada la disponibilidad de pods
- detecta estados `CrashLoopBackOff`
- valida la correcta inicialización del backend
- genera evidencia técnica en `runtime/`

``` text
python3 adapters/inesdata/portal/portal-deploy.py
```

### Verificación

``` text
kubectl get pods -n demo # Esperar algunos minutos a que todos los pods estén en Running

# Verificación por ingress:

# - Frontend
curl -I http://demo.dev.ds.inesdata.upm

# - Backend (panel administrativo)
curl -I http://backend-demo.dev.ds.inesdata.upm/admin

```

**Ejemplo de salida esperada**

``` text
NAME                                           READY   STATUS    RESTARTS   AGE
conn-oeg-demo-xxxxxxxxxx-xxxxx                  1/1     Running   0          5m
conn-oeg-demo-interface-xxxxxxxxxx-xxxxx        1/1     Running   0          5m
demo-public-portal-backend-xxxxxxxxxx-xxxxx     1/1     Running   0          2m
demo-public-portal-frontend-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
demo-registration-service-xxxxxxxxxx-xxxxx      1/1     Running   0          1h

HTTP/1.1 200 OK
HTTP/1.1 200 OK

```

### Criterios de aceptación

-   El backend y el frontend del Portal se encuentran en estado Running.
-   El backend del Portal inicia sin errores de resolución DNS ni de conexión a PostgreSQL.
-   La resolución DNS cross-namespace es operativa.
-   El despliegue Helm es reproducible.
-   El acceso HTTP responde con código `200 OK` en:
    - Frontend: http://demo.dev.ds.inesdata.upm
    - Backend: http://backend-demo.dev.ds.inesdata.upm/admin

> **Nota:**
> - El despliegue aplica un post-renderer Helm automático para eliminar hostPort y garantizar compatibilidad con Ingress en entorno Minikube sin modificar el chart oficial.
> - La inicialización funcional del Portal (bootstrap de contenido, generación de API tokens, configuración de permisos y creación del menú público) se aborda en el Nivel 10 mediante automatización reproducible.
> - En configuración Minikube con driver Docker bajo WSL2, el acceso a los dominios definidos en Ingress requiere la ejecución activa de minikube tunnel, ya que la exposición de puertos 80/443 no es automática en esta configuración de red. Esta condición es propia del entorno de pruebas y no afecta la validación funcional del Portal.

---

⬅️ [Nivel anterior: Nivel 8 - Configuración y Despliegue del Connector INESData](../nivel-8/README.md) </br>
➡️ [Siguiente nivel: Nivel 10 - Configuración del Portal Público](../nivel-10/README.md)</br>
🏠 [Volver al README principal](/README.md)

