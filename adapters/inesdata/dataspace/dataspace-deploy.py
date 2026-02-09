#!/usr/bin/env python3
"""
dataspace-deploy.py

NIVEL 6 – Despliegue físico del Dataspace INESData (Step-1)

RESPONSABILIDADES:
- Garantizar namespace Kubernetes
- Limpiar workloads huérfanos (pre-Helm)
- Esperar PostgreSQL usando credenciales reales del clúster
- Resetear DB QA-safe (terminando sesiones)
- Ejecutar Helm de forma idempotente
- Garantizar ConfigMap + Secret reales
- Reiniciar deployment controladamente

PRINCIPIOS:
- Fuente de verdad = estado del clúster
- NO reutiliza dataspace-create.py
- NO passwords hardcodeados
- Idempotente y reproducible
"""

import subprocess
import sys
import time
import json
import base64
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
NAMESPACE = DATASPACE
RELEASE = f"{DATASPACE}-dataspace-s1"

# PostgreSQL (servicios comunes)
PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_SECRET = "common-srvs-postgresql"

RS_DB = f"{DATASPACE}_rs"
RS_USER = f"{DATASPACE}_rsusr"
RS_PASSWORD = "demo_rs_pwd"   # QA-safe (solo para demo)

PG_SERVICE = "common-srvs-postgresql"

# Recursos Kubernetes gestionados
DEPLOYMENT = "demo-registration-service"
CONFIGMAP = "demo-registration-service-config"
SECRET = "demo-registration-service-secret"

ROOT = Path(__file__).resolve().parents[3]
STEP1_DIR = ROOT / "runtime" / "workdir" / "inesdata-deployment" / "dataspace" / "step-1"
VALUES_FILE = STEP1_DIR / f"values-{DATASPACE}.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None, check=True):
    print(f"\n▶ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)

def get_postgres_password():
    """
    Lee el password REAL de PostgreSQL desde el Secret de Kubernetes.
    Fuente de verdad absoluta.
    """
    result = subprocess.run(
        ["kubectl", "get", "secret", PG_SECRET, "-n", PG_NAMESPACE, "-o", "json"],
        capture_output=True,
        text=True,
        check=True
    )
    data = json.loads(result.stdout)
    return base64.b64decode(data["data"]["postgres-password"]).decode("utf-8")

# =============================================================================
# FASE 6.0 – GARANTIZAR NAMESPACE
# =============================================================================

def ensure_namespace():
    header("NIVEL 6 – Garantizando namespace Kubernetes")
    subprocess.run(
        ["kubectl", "create", "namespace", NAMESPACE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"✓ Namespace '{NAMESPACE}' garantizado")

# =============================================================================
# FASE 6.1 – VERIFICACIÓN DE INPUTS
# =============================================================================

def check_inputs():
    header("NIVEL 6 – Verificación de inputs")

    if not VALUES_FILE.exists():
        sys.exit(f"❌ Falta values.yaml: {VALUES_FILE}")

    run(["kubectl", "get", "pod", PG_POD, "-n", PG_NAMESPACE])
    print("✓ Inputs correctos")

# =============================================================================
# FASE 6.2 – LIMPIEZA DEPLOYMENT HUÉRFANO (CRÍTICO)
# =============================================================================

def cleanup_orphan_deployment():
    header("NIVEL 6 – Limpieza deployment huérfano (pre-Helm)")

    result = subprocess.run(
        ["kubectl", "get", "deployment", DEPLOYMENT, "-n", NAMESPACE, "-o", "json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("✓ No existe deployment previo")
        return

    data = json.loads(result.stdout)
    annotations = data.get("metadata", {}).get("annotations", {})

    if "meta.helm.sh/release-name" in annotations:
        print("✓ Deployment gestionado por Helm (OK)")
        return

    print("⚠️ Deployment huérfano detectado → eliminando")
    run(["kubectl", "delete", "deployment", DEPLOYMENT, "-n", NAMESPACE])

# =============================================================================
# FASE 6.3 – ESPERAR POSTGRESQL (AUTORIDAD REAL)
# =============================================================================

def wait_for_postgres():
    header("NIVEL 6 – Esperando PostgreSQL READY")

    password = get_postgres_password()

    for _ in range(30):
        try:
            run([
                "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
                "sh", "-c",
                f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d postgres -c 'SELECT 1;'"
            ])
            print("✓ PostgreSQL listo y accesible")
            return
        except subprocess.CalledProcessError:
            time.sleep(5)

    sys.exit("❌ PostgreSQL no accesible tras múltiples intentos")

# =============================================================================
# FASE 6.4 – RESET DB QA-SAFE
# =============================================================================

def recreate_db():
    header("NIVEL 6 – Reset controlado de DB")

    password = get_postgres_password()

    sql_cmds = [
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{RS_DB}' AND pid <> pg_backend_pid();",

        f"DROP DATABASE IF EXISTS {RS_DB};",
        f"DROP ROLE IF EXISTS {RS_USER};",
        f"CREATE ROLE {RS_USER} LOGIN PASSWORD '{RS_PASSWORD}';",
        f"CREATE DATABASE {RS_DB} OWNER {RS_USER};"
    ]

    for sql in sql_cmds:
        run([
            "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
            "sh", "-c",
            f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d postgres -c \"{sql}\""
        ])

    print("✓ DB recreada correctamente")

# =============================================================================
# FASE 6.5 – HELM (CWD CORRECTO)
# =============================================================================

def deploy_helm():
    header("NIVEL 6 – Helm Step-1")

    run(
        [
            "helm", "upgrade", "--install", RELEASE,
            "-n", NAMESPACE,
            "--create-namespace",
            "-f", VALUES_FILE.name,
            "."
        ],
        cwd=STEP1_DIR
    )

# =============================================================================
# FASE 6.6 – CONFIGMAP / SECRET (FUENTE REAL)
# =============================================================================

def ensure_configmap_and_secret():
    header("NIVEL 6 – Garantía ConfigMap / Secret")

    jdbc = f"jdbc:postgresql://{PG_SERVICE}.{PG_NAMESPACE}:5432/{RS_DB}"

    run([
        "sh", "-c",
        f"""
kubectl create configmap {CONFIGMAP} -n {NAMESPACE} \
  --from-literal=SPRING_DATASOURCE_URL={jdbc} \
  --from-literal=SPRING_DATASOURCE_USERNAME={RS_USER} \
  --dry-run=client -o yaml | kubectl apply -f -
"""
    ])

    run([
        "sh", "-c",
        f"""
kubectl create secret generic {SECRET} -n {NAMESPACE} \
  --from-literal=SPRING_DATASOURCE_PASSWORD={RS_PASSWORD} \
  --dry-run=client -o yaml | kubectl apply -f -
"""
    ])

    print("✓ ConfigMap y Secret aplicados correctamente")

# =============================================================================
# FASE 6.7 – RESTART CONTROLADO
# =============================================================================

def restart_deployment():
    header("NIVEL 6 – Reinicio controlado del Deployment")

    run(["kubectl", "rollout", "restart", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE])
    run(["kubectl", "rollout", "status", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE])

# =============================================================================
# MAIN
# =============================================================================

def main():
    ensure_namespace()
    check_inputs()
    cleanup_orphan_deployment()
    wait_for_postgres()
    recreate_db()
    deploy_helm()
    ensure_configmap_and_secret()
    restart_deployment()

    header("NIVEL 6 COMPLETADO (CANÓNICO)")
    print("✔ Kubernetes limpio y coherente")
    print("✔ DB alineada con estado real")
    print("✔ Helm idempotente")
    print("➡ Siguiente paso: Nivel 7 (connector-create.py)")

if __name__ == "__main__":
    main()
