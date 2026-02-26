# NIVEL 8 – Configuración y Despliegue del Connector INESData

### Propósito
Configurar y desplegar en Kubernetes el connector definido de forma lógica en el NIVEL 7 y permitir su ejecución operativa dentro del dataspace desplegado. Este nivel consolida la configuración técnica final antes de pruebas operativas.

### Ruta
```text
pionera-env/
```

### Ejecutar `connector-setup.py` (automatización)
> **Precondiciones técnicas:**
> - Debe existir el fichero `values-<connector>.yaml` normalizado.
> - Los servicios comunes (PostgreSQL, Vault, Keycloak) deben encontrarse operativos.
> - Cerrar la consola:
kubectl port-forward common-srvs-keycloak-0 -n common-srvs 8080:8080
> - Abrir `minikube tunnel` en una consola nueva.
> - Abrir el tunel de la API del conector:
``` bash
kubectl port-forward deployment/conn-oeg-demo 19193:19193 -n demo
```

Este script:
- Configuración OAuth alineada con Keycloak
- Integración estructural con Vault
- Normalización Helm-safe del chart
- PostgreSQL vía DNS Kubernetes (FQDN)
- Despliegue idempotente y reproducible
- Verificación automática del rollout

```text
python3 adapters/inesdata/integration/auth/auth-bootstrap.py
python3 adapters/inesdata/integration/connector/connector-setup.py
```

### Verificación
```text
kubectl get svc -n common-srvs common-srvs-keycloak

kubectl get pods -n demo

kubectl logs deployment/conn-oeg-demo -n demo --tail=20
```

**Ejemplo de salida esperada**
```text
# Debe haber una IP asignada
$ kubectl get svc -n common-srvs common-srvs-keycloak
NAME                   TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
common-srvs-keycloak   ClusterIP   10.105.176.69   <none>        80/TCP    28m


NAME                                         READY   STATUS    RESTARTS   AGE
conn-oeg-demo-xxxxxxxxxx-xxxxx               1/1     Running   0          1m
conn-oeg-demo-interface-xxxxxxxxxx-xxxxx     1/1     Running   0          1m
demo-registration-service-xxxxxxxxxx-xxxxx   1/1     Running   0          19h

$ kubectl logs deployment/conn-oeg-demo -n demo --tail=20
10:39:39.192 [main] INFO  o.upm.inesdata.monitor.Slf4jMonitor -- Runtime 0e8412e3-9201-4197-8bc9-dfa5fc149d32 ready
```

### Criterios de aceptación
- El connector se encuentra desplegado y en estado Running.
- El `initContainer` del connector se ejecuta correctamente sin errores.
- La base de datos del connector ha sido inicializada.
- La resolución DNS cross-namespace (`*.svc`) es funcional.
- El connector queda operativo dentro del dataspace desplegado.

---

⬅️ [Nivel anterior: Nivel 7 - Creación del Connector (lógica)](../nivel-7/README.md) <br>
➡️ [Siguiente nivel: Nivel 9 - Despliegue del Portal Público](../nivel-9/README.md) </br>
🏠 [Volver al README principal](/README.md)