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

⬅️ [Nivel anterior: Nivel 0 – Post-configuración de Vault y Deployer](../nivel-0/README.md)  
➡️ [Siguiente nivel: Nivel 2 – Creación lógica del Dataspace](../nivel-2/README.md)
🏠 [Volver al README principal](/README.md)