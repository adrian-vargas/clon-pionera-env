import json
import subprocess
import time
import os
import signal
import sys
from pathlib import Path
import requests
import time

# ==========================================================
# UTILIDADES Y CONFIGURACIÓN GLOBAL
# ==========================================================
pf_processes = {}

from pathlib import Path
import time

def wait_for_file(path: Path, timeout=30):
    print(f"⏳ Esperando fichero {path}...")
    start = time.time()

    while time.time() - start < timeout:
        if path.exists() and path.stat().st_size > 0:
            print("✓ Fichero generado correctamente")
            return
        time.sleep(1)

    raise RuntimeError(f"❌ El fichero {path} no se generó en el tiempo esperado")

def wait_for_keycloak(timeout=120):
    print("⏳ Esperando a que Keycloak esté listo (localhost:8080)...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            r = requests.get("http://127.0.0.1:8080/realms/master", timeout=3)
            if r.status_code == 200:
                print("✓ Keycloak listo")
                return
        except requests.exceptions.RequestException:
            pass

        time.sleep(3)

    raise RuntimeError("❌ Keycloak no estuvo listo en el tiempo esperado")

# Definimos ROOT aquí para que sea accesible desde cualquier nivel
# Suponiendo que deploy.py está en adapters/inesdata/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def tunnel_running():
    result = subprocess.run(
        "pgrep -f 'minikube tunnel'",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def retry(func, retries=30, delay=5):
    for intento in range(1, retries + 1):
        try:
            return func()
        except Exception as e:
            print(f"\n❌ Intento {intento}/{retries} fallido: {e}")
            if intento == retries:
                raise
            time.sleep(delay)

def run(cmd, background=False):
    print(f"\n=== Ejecutando: {cmd} ===\n")
    if background:
        return subprocess.Popen(cmd, shell=True)
    else:
        subprocess.run(cmd, shell=True, check=True)

def wait_for_pod_running(pod_name, namespace):
    def check():
        cmd = (
            f"kubectl get pod {pod_name} -n {namespace} "
            "-o jsonpath='{.status.phase}'"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if "Running" not in result.stdout:
            raise RuntimeError(f"{pod_name} no está en Running aún")
        print(f"✓ {pod_name} está en estado Running")
    retry(check)

# ==========================================================
# NIVEL 1
# ==========================================================

def nivel_1():
    print("\n==============================")
    print("== NIVEL 1: Minikube ==")
    print("==============================")

    import subprocess
    import time
    import sys

    # ------------------------------------------------------
    # 0. Cerrar túneles previos (evita procesos zombie)
    # ------------------------------------------------------
    print("🧹 Cerrando túneles minikube previos...")

    subprocess.run("pkill -f 'minikube tunnel'", shell=True)
    time.sleep(2)

    # ------------------------------------------------------
    # 1. Eliminar cluster previo
    # ------------------------------------------------------
    print("🔥 Eliminando cluster previo...")
    subprocess.run("minikube delete --all --purge", shell=True)

    time.sleep(3)

    # ------------------------------------------------------
    # 2. Crear cluster limpio
    # ------------------------------------------------------
    print("🚀 Creando nuevo cluster Minikube...")

    result = subprocess.run(
        "minikube start --driver=docker --cpus=4 --memory=4400",
        shell=True
    )

    if result.returncode != 0:
        sys.exit("❌ Falló minikube start")

    # ------------------------------------------------------
    # 3. Esperar API server realmente disponible
    # ------------------------------------------------------
    print("⏳ Esperando disponibilidad del API server...")

    for _ in range(60):
        check = subprocess.run(
            "kubectl get nodes",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if check.returncode == 0:
            print("✔ API server disponible")
            break

        time.sleep(2)
    else:
        sys.exit("❌ API server no responde")

    # ------------------------------------------------------
    # 4. Activar Ingress
    # ------------------------------------------------------
    print("🌐 Activando addon ingress...")
    subprocess.run("minikube addons enable ingress", shell=True, check=True)

    # ------------------------------------------------------
    # 5. Esperar controlador ingress-nginx
    # ------------------------------------------------------
    print("⏳ Esperando ingress controller...")

    subprocess.run(
        "kubectl wait --namespace ingress-nginx "
        "--for=condition=ready pod "
        "--selector=app.kubernetes.io/component=controller "
        "--timeout=180s",
        shell=True,
        check=True
    )

    # ------------------------------------------------------
    # 6. Esperar admission webhook
    # ------------------------------------------------------
    print("⏳ Esperando admission webhook...")

    subprocess.run(
        "kubectl wait --namespace ingress-nginx "
        "--for=condition=complete job "
        "--selector=app.kubernetes.io/component=admission-webhook "
        "--timeout=180s",
        shell=True,
        check=True
    )

    # ------------------------------------------------------
    # 7. Verificación final (evidencia)
    # ------------------------------------------------------
    print("\n📋 Estado final del cluster:")

    subprocess.run("minikube status", shell=True)
    subprocess.run("kubectl get nodes -o wide", shell=True)
    subprocess.run("kubectl get pods -n ingress-nginx", shell=True)

    print("\n✔ NIVEL 1 COMPLETADO CORRECTAMENTE")

# ==========================================================
# NIVEL 2
# ==========================================================

def nivel_2():
    print("\n== NIVEL 2: Bootstrap ==")

    run("helm repo add minio https://charts.min.io/")
    run("helm repo add hashicorp https://helm.releases.hashicorp.com")
    run("helm repo update")

    run("pip install PyYAML")

    run("python3 adapters/inesdata/bootstrap.py")
    run("python3 adapters/inesdata/normalize/normalize-base.py")
    run("python3 adapters/inesdata/install.py")

    run("kubectl get pods -n common-srvs")

# ==========================================================
# NIVEL 3
# ==========================================================

def nivel_3():
    print("\n== NIVEL 3: Vault ==")

    from pathlib import Path
    import json
    import time
    import subprocess

    init_file = Path("runtime/workdir/inesdata-deployment/common/init-keys-vault.json")

    # ------------------------------------------------------
    # Utilidad: esperar fichero
    # ------------------------------------------------------
    def wait_for_file(path: Path, timeout=30):
        print(f"⏳ Esperando fichero {path}...")
        start = time.time()

        while time.time() - start < timeout:
            if path.exists() and path.stat().st_size > 0:
                print("✓ Fichero generado correctamente")
                return
            time.sleep(1)

        raise RuntimeError(f"❌ El fichero {path} no se generó en el tiempo esperado")

    # ------------------------------------------------------
    # 1. Esperar pod
    # ------------------------------------------------------
    retry(lambda: run(
        "kubectl get pod common-srvs-vault-0 -n common-srvs"
    ))

    wait_for_pod_running("common-srvs-vault-0", "common-srvs")

    # ------------------------------------------------------
    # 2. Obtener estado JSON
    # ------------------------------------------------------
    result = subprocess.run(
        "kubectl exec common-srvs-vault-0 -n common-srvs -- vault status -format=json",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode not in [0, 2]:
        raise RuntimeError("Vault no responde correctamente")

    status = json.loads(result.stdout)

    initialized = status.get("initialized", False)
    sealed = status.get("sealed", True)

    print(f"Initialized: {initialized}")
    print(f"Sealed: {sealed}")

    # ------------------------------------------------------
    # 3. Inicializar si no está inicializado
    # ------------------------------------------------------
    if not initialized:
        print("🔐 Inicializando Vault...")

        result = subprocess.run(
            "kubectl exec common-srvs-vault-0 -n common-srvs -- "
            "vault operator init -key-shares=1 -key-threshold=1 -format=json",
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )

        init_file.parent.mkdir(parents=True, exist_ok=True)
        init_file.write_text(result.stdout)

        wait_for_file(init_file)

        # Recargar estado
        result = subprocess.run(
            "kubectl exec common-srvs-vault-0 -n common-srvs -- vault status -format=json",
            shell=True,
            capture_output=True,
            text=True
        )

        status = json.loads(result.stdout)
        sealed = status.get("sealed", True)

    else:
        if not init_file.exists():
            raise RuntimeError(
                "❌ Vault está inicializado pero init-keys-vault.json no existe."
            )

    # ------------------------------------------------------
    # 4. Unseal si está sellado
    # ------------------------------------------------------
    if sealed:
        print("🔓 Ejecutando unseal...")

        key = subprocess.check_output(
            "jq -r '.unseal_keys_hex[0]' "
            "runtime/workdir/inesdata-deployment/common/init-keys-vault.json",
            shell=True
        ).decode().strip()

        subprocess.run(
            f"kubectl exec common-srvs-vault-0 -n common-srvs -- "
            f"vault operator unseal {key}",
            shell=True,
            check=True
        )

    # ------------------------------------------------------
    # 5. Verificación final Vault
    # ------------------------------------------------------
    final = subprocess.run(
        "kubectl exec common-srvs-vault-0 -n common-srvs -- vault status -format=json",
        shell=True,
        capture_output=True,
        text=True
    )

    final_status = json.loads(final.stdout)

    if final_status.get("sealed", True):
        raise RuntimeError("❌ Vault sigue sellado tras unseal")

    print("✔ Vault inicializado y operativo (unsealed)")

    # ------------------------------------------------------
    # 6. Port-forward temporal para post-common.py
    # ------------------------------------------------------
    print("🔌 Iniciando port-forward a Vault (8200)...")

    vault_pf = subprocess.Popen(
        "kubectl port-forward common-srvs-vault-0 -n common-srvs 8200:8200",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(5)

    try:
        print("⚙ Ejecutando post-common.py...")
        subprocess.run(
            "python3 adapters/inesdata/normalize/post-common.py",
            shell=True,
            check=True
        )
        print("✔ post-common.py ejecutado correctamente")
    finally:
        print("🔒 Cerrando port-forward de Vault")
        vault_pf.terminate()
        vault_pf.wait()

    print("✔ NIVEL 3 COMPLETADO CORRECTAMENTE")

# ==========================================================
# NIVEL 4
# ==========================================================

def nivel_4():
    global pf_processes

    print("\n== NIVEL 4: Python + Ports ==")

    run("sudo apt install -y python3.10-venv")
    if not os.path.exists("venv"):
        run("python3.10 -m venv venv")
    run("bash -c 'source venv/bin/activate && pip install -r runtime/workdir/inesdata-deployment/requirements.txt'")

    print("🔌 Iniciando port-forwards modo local (N4–N7)")

    pf_processes["postgres"] = subprocess.Popen(
        "kubectl port-forward common-srvs-postgresql-0 -n common-srvs 5432:5432",
        shell=True
    )

    pf_processes["vault"] = subprocess.Popen(
        "kubectl port-forward common-srvs-vault-0 -n common-srvs 8200:8200",
        shell=True
    )

    pf_processes["keycloak"] = subprocess.Popen(
        "kubectl port-forward common-srvs-keycloak-0 -n common-srvs 8080:8080",
        shell=True
    )

    time.sleep(5)

# ==========================================================
# NIVEL 5
# ==========================================================

def nivel_5():
    print("\n== NIVEL 5: Dataspace Create ==")

    os.environ["VAULT_ADDR"] = "http://127.0.0.1:8200"
    run("python3 adapters/inesdata/dataspace/dataspace-create.py")

# ==========================================================
# NIVEL 6
# ==========================================================

def nivel_6():
    print("\n== NIVEL 6: Dataspace Deploy ==")

    run("kubectl create namespace demo || true")
    if "keycloak" not in pf_processes:
        raise RuntimeError("Port-forward Keycloak no activo")
    wait_for_keycloak()
    time.sleep(10)
    run("python3 adapters/inesdata/dataspace/dataspace-deploy.py")

    run("kubectl get ns demo")
    run("kubectl get pods -n demo")

# ==========================================================
# NIVEL 7
# ==========================================================
def nivel_7():
    global pf_processes

    header("NIVEL 7 – Despliegue y Verificación de Esquema EDC")

    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    script_creacion = PROJECT_ROOT / "adapters" / "inesdata" / "connector" / "connector-create.py"

    started_here = []

    # ------------------------------------------------------
    # 1️⃣ Asegurar Vault port-forward
    # ------------------------------------------------------
    if "vault" not in pf_processes:
        print("🔌 Iniciando port-forward a Vault (8200)...")
        pf_processes["vault"] = subprocess.Popen(
            ["kubectl", "port-forward",
             "common-srvs-vault-0", "-n", "common-srvs",
             "8200:8200"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        started_here.append("vault")
        time.sleep(3)
    else:
        print("✓ Port-forward Vault ya activo")

    # ------------------------------------------------------
    # 2️⃣ Asegurar Keycloak port-forward
    # ------------------------------------------------------
    if "keycloak" not in pf_processes:
        print("🔌 Iniciando port-forward a Keycloak (8080)...")
        pf_processes["keycloak"] = subprocess.Popen(
            ["kubectl", "port-forward",
             "common-srvs-keycloak-0", "-n", "common-srvs",
             "8080:8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        started_here.append("keycloak")
        time.sleep(5)
    else:
        print("✓ Port-forward Keycloak ya activo")

    # Esperar a que Keycloak realmente responda
    wait_for_keycloak()
    time.sleep(10)
    try:
        # --------------------------------------------------
        # 3️⃣ Ejecutar creación del conector
        # --------------------------------------------------
        print("▶ Ejecutando script de creación...")
        result = subprocess.run(
            [str(venv_python), str(script_creacion)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            sys.exit("❌ ERROR EN CREACIÓN DEL CONNECTOR")

        print("✓ Script de creación finalizado correctamente.")

    finally:
        # --------------------------------------------------
        # 4️⃣ Cerrar solo los PF que abrimos aquí
        # --------------------------------------------------
        for name in started_here:
            print(f"🔒 Cerrando port-forward {name}...")
            pf_processes[name].terminate()
            pf_processes[name].wait()
            del pf_processes[name]

    # ------------------------------------------------------
    # 5️⃣ Verificación de Deployment
    # ------------------------------------------------------
    print("🔍 Detectando recurso desplegado en namespace 'demo'...")

    check_deploy = subprocess.run(
        ["kubectl", "get", "deployments", "-n", "demo", "-o", "name"],
        capture_output=True,
        text=True
    )

    if not check_deploy.stdout.strip():
        sys.exit("❌ ERROR: No se creó ningún deployment en el namespace 'demo'.")

    deploy_name = check_deploy.stdout.splitlines()[0]
    print(f"✓ Recurso detectado: {deploy_name}")

    print(f"⏳ Esperando a que {deploy_name} esté Running...")
    subprocess.run(
        ["kubectl", "rollout", "status", deploy_name, "-n", "demo", "--timeout=180s"],
        check=True
    )

    # ------------------------------------------------------
    # 6️⃣ Verificación EDC
    # ------------------------------------------------------
    print("⏳ Verificando esquema EDC en Postgres...")

    for i in range(1, 21):
        db_check = subprocess.run(
            [
                "kubectl", "exec", "-n", "common-srvs", "common-srvs-postgresql-0", "--",
                "sh", "-c",
                "PGPASSWORD=xxxxCHANGEMExxxx psql -t -A -U postgres -d demo_rs -c "
                "\"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'edc_participant');\""
            ],
            capture_output=True,
            text=True
        )

        if db_check.stdout.strip() == "t":
            print("\n✔ Esquema EDC detectado correctamente!")
            break

        print(f"   [{i}/20] Esperando inicialización...", end="\r")
        time.sleep(5)
    else:
        sys.exit("\n❌ ERROR: El esquema EDC no se inicializó.")

    print("\n✔ NIVEL 7 COMPLETADO EXITOSAMENTE")

def nivel_8():
    header("NIVEL 8 – Auth + Connector Setup (PT5 Clean Mode)")

    venv_python = os.path.abspath("venv/bin/python")

    # ------------------------------------------------------------------
    # 1️⃣ Configuración declarativa (NO hardcoded)
    # ------------------------------------------------------------------
    KEYCLOAK_URL = os.environ.get(
        "KEYCLOAK_URL",
        "http://localhost:8080"
    )

    VAULT_ADDR = os.environ.get(
        "VAULT_ADDR",
        "http://localhost:8200"
    )

    print(f"🔗 Keycloak URL: {KEYCLOAK_URL}")
    print(f"🔗 Vault URL: {VAULT_ADDR}")

    # ------------------------------------------------------------------
    # 2️⃣ Verificar que Keycloak responde vía Ingress
    # ------------------------------------------------------------------
    print("⏳ Verificando disponibilidad de Keycloak vía Ingress...")

    for i in range(40):
        try:
            r = requests.get(f"{KEYCLOAK_URL}/realms/master", timeout=3)
            if r.status_code in [200, 302]:
                print("✔ Keycloak accesible vía Ingress")
                break
        except requests.exceptions.RequestException:
            pass

        print(f"   [{i+1}/40] Esperando respuesta...", end="\r")
        time.sleep(3)
    else:
        sys.exit("❌ Keycloak no responde vía Ingress")

    # ------------------------------------------------------------------
    # 3️⃣ Ejecutar bootstrap OIDC
    # ------------------------------------------------------------------
    env = os.environ.copy()
    env["KEYCLOAK_URL"] = KEYCLOAK_URL
    env["VAULT_ADDR"] = VAULT_ADDR
    env["PYTHONUNBUFFERED"] = "1"

    print("🚀 Ejecutando auth-bootstrap.py...")
    subprocess.run(
        [venv_python, "adapters/inesdata/integration/auth/auth-bootstrap.py"],
        check=True,
        env=env
    )

    print("🚀 Ejecutando connector-setup.py...")
    subprocess.run(
        [venv_python, "adapters/inesdata/integration/connector/connector-setup.py"],
        check=True,
        env=env
    )

    print("✔ NIVEL 8 COMPLETADO (PT5 ALIGNED)")

# ==========================================================
# NIVEL 9
# ==========================================================

def nivel_9():
    print("\n==============================")
    print("== NIVEL 9: Portal Create + Deploy ==")
    print("==============================")

    venv_python = os.path.abspath("venv/bin/python")

    print("🚀 Ejecutando portal-create.py...")

    subprocess.run(
        [venv_python, "adapters/inesdata/portal/portal-create.py"],
        check=True
    )

    print("🚀 Ejecutando portal-deploy.py...")

    subprocess.run(
        [venv_python, "adapters/inesdata/portal/portal-deploy.py"],
        check=True
    )

    print("✔ NIVEL 9 COMPLETADO CORRECTAMENTE")


# ==========================================================
# NIVEL 10
# ==========================================================

"""
def nivel_10():
    print("\n==============================")
    print("== NIVEL 10: Portal Setup ==")
    print("==============================")

    venv_python = os.path.abspath("venv/bin/python")

    print("⚙ Ejecutando portal-setup.py...")

    subprocess.run(
        [venv_python, "adapters/inesdata/portal/portal-setup.py"],
        check=True
    )

    print("✔ NIVEL 10 COMPLETADO CORRECTAMENTE")
"""
def nivel_10():
    header("NIVEL 10: Portal Setup (Deterministic Mode)")
    venv_python = os.path.abspath("venv/bin/python")

    # 1. Buscar el pod usando un filtro de nombre parcial (más robusto que labels)
    print("🔍 Buscando pod del backend en namespace 'demo'...")
    pod_name = None
    for i in range(20):
        # Buscamos cualquier pod que contenga 'public-portal-backend' en su nombre
        cmd = "kubectl get pods -n demo --no-headers -o custom-columns=':metadata.name' | grep public-portal-backend"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        names = res.stdout.strip().splitlines()
        if names:
            pod_name = names[0]
            print(f"✔ Pod detectado: {pod_name}")
            break
        
        print(f"  [{i+1}/20] Esperando a que el pod aparezca...", end="\r")
        time.sleep(3)
    else:
        sys.exit("\n❌ ERROR: No se encontró ningún pod que contenga 'public-portal-backend' en 'demo'.")

    # 2. Esperar a que esté Ready
    print(f"⏳ Esperando a que {pod_name} esté Ready...")
    subprocess.run(
        ["kubectl", "wait", "--namespace", "demo", "--for=condition=ready", f"pod/{pod_name}", "--timeout=180s"],
        check=True
    )

    # 3. Limpiar puertos
    subprocess.run("fuser -k 18080/tcp", shell=True, stderr=subprocess.DEVNULL)

    # 4. Abrir túnel al SERVICIO (usamos el nombre del servicio que es estático)
    print("🔌 Abriendo túnel (localhost:18080 -> svc/demo-public-portal-backend:1337)...")
    bypass_pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", "demo", "svc/demo-public-portal-backend", "18080:1337"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    try:
        print("⏳ Estabilizando conexión...")
        time.sleep(5)

        # 5. Ejecución del setup
        print("⚙ Ejecutando portal-setup.py...")
        env = os.environ.copy()
        env["PORTAL_BACKEND_URL"] = "http://localhost:18080"
        env["PYTHONUNBUFFERED"] = "1"

        subprocess.run([venv_python, "adapters/inesdata/portal/portal-setup.py"], check=True, env=env)
        print("✔ NIVEL 10 COMPLETADO EXITOSAMENTE")

    finally:
        print("🔒 Cerrando port-forward...")
        bypass_pf.terminate()

# ==========================================================
# MAIN Y EJECUCIÓN SELECTIVA
# ==========================================================

if __name__ == "__main__":
    # Si pasas un argumento (ej: python deploy.py nivel_7), ejecuta solo ese nivel
    if len(sys.argv) > 1:
        func_name = sys.argv[1]
        if func_name in locals():
            locals()[func_name]()
        else:
            print(f"❌ La función '{func_name}' no existe en este script.")
    else:
        # Ejecución normal de todos los niveles
        nivel_1()
        nivel_2()
        nivel_3()
        nivel_4()
        nivel_5()
        nivel_6()
        nivel_7()
        nivel_8()
        nivel_9()
        nivel_10()
        print("\nORQUESTACIÓN COMPLETADA")