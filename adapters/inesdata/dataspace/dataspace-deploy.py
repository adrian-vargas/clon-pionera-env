#!/usr/bin/env python3
"""
dataspace-deploy.py

NIVEL 6 – Despliegue del Dataspace INESData (Step-1) para PIONERA

VERSIÓN CANÓNICA FINAL:
- Reset DB QA-safe
- Helm ejecutado en directorio correcto
- ConfigMap + Secret garantizados (envFrom real)
- Sin hostAliases
- Sin dependencias implícitas
- Credenciales PostgreSQL leídas desde Kubernetes (estado real)
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

# PostgreSQL (COMMON)
PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_SECRET = "common-srvs-postgresql"

RS_DB = f"{DATASPACE}_rs"
RS_USER = f"{DATASPACE}_rsusr"
RS_PASSWORD = "demo_rs_pwd"  # generado previamente (QA-safe)

PG_SERVICE = "common-srvs-postgresql"

# Recursos Kubernetes usados por el chart
CONFIGMAP = "demo-registration-service-config"
SECRET = "demo-registration-service-secret"
DEPLOYMENT = "demo-registration-service"

ROOT = Path(__file__).resolve().parents[3]
STEP1_DIR = ROOT / "runtime" / "workdir" / "inesdata-deployment" / "dataspace" / "step-1"
VALUES_FILE = STEP1_DIR / f"values-{DATASPACE}.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, check=True, cwd=None):
    print(f"\n▶ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True, cwd=cwd)

def get_postgres_password():
    """
    Lee el password real de PostgreSQL desde el Secret de Kubernetes.
    Fuente de verdad: estado del clúster.
    """
    result = subprocess.run(
        [
            "kubectl", "get", "secret", PG_SECRET,
            "-n", PG_NAMESPACE,
            "-o", "json"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    secret = json.loads(result.stdout)
    b64_pwd = secret["data"]["postgres-password"]
    return base64.b64decode(b64_pwd).decode("utf-8")

# =============================================================================
# PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 6 – Verificación de precondiciones")
    run(["kubectl", "get", "ns", NAMESPACE])
    run(["kubectl", "get", "pod", PG_POD, "-n", PG_NAMESPACE])
    if not VALUES_FILE.exists():
        sys.exit(f"❌ Falta {VALUES_FILE}")
    print("✓ Entorno base presente")

# =============================================================================
# POSTGRES READY (AUTORIDAD REAL)
# =============================================================================

def wait_for_postgres():
    header("NIVEL 6 – Esperando PostgreSQL READY")
    password = get_postgres_password()

    for _ in range(30):
        try:
            run([
                "kubectl", "exec",
                "-n", PG_NAMESPACE,
                PG_POD,
                "--", "sh", "-c",
                f"PGPASSWORD={password} "
                f"psql -U {PG_ADMIN_USER} -d postgres -c 'SELECT 1;'"
            ])
            print("✓ PostgreSQL listo y accesible")
            return
        except subprocess.CalledProcessError:
            time.sleep(5)

    sys.exit("❌ PostgreSQL no accesible tras múltiples intentos")

# =============================================================================
# RESET DB (QA-SAFE, SIN HEREDOCS)
# =============================================================================

def recreate_db():
    header("NIVEL 6 – Reset controlado DB")
    password = get_postgres_password()

    sql_cmds = [
        f"DROP DATABASE IF EXISTS {RS_DB};",
        f"DROP ROLE IF EXISTS {RS_USER};",
        f"CREATE ROLE {RS_USER} LOGIN PASSWORD '{RS_PASSWORD}';",
        f"CREATE DATABASE {RS_DB} OWNER {RS_USER};"
    ]

    for sql in sql_cmds:
        run([
            "kubectl", "exec",
            "-n", PG_NAMESPACE,
            PG_POD,
            "--", "sh", "-c",
            f"PGPASSWORD={password} "
            f"psql -U {PG_ADMIN_USER} -d postgres -c \"{sql}\""
        ])

    print("✓ DB recreada correctamente")

# =============================================================================
# HELM (CWD CORRECTO)
# =============================================================================

def deploy_helm():
    header("NIVEL 6 – Helm Step-1")
    run(
        [
            "helm", "upgrade", "--install", RELEASE,
            "-n", NAMESPACE,
            "--create-namespace",
            "-f", f"values-{DATASPACE}.yaml",
            "."
        ],
        cwd=STEP1_DIR
    )

# =============================================================================
# CONFIGMAP / SECRET (FUENTE REAL)
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
# RESTART CONTROLADO
# =============================================================================

def restart_deployment():
    header("NIVEL 6 – Reinicio controlado del Deployment")
    run(["kubectl", "rollout", "restart", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE])
    run(["kubectl", "rollout", "status", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE])

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_preconditions()
    wait_for_postgres()
    recreate_db()
    deploy_helm()
    ensure_configmap_and_secret()
    restart_deployment()

    header("NIVEL 6 COMPLETADO (CANÓNICO)")
    print("✔ DB garantizada desde estado real del clúster")
    print("✔ Helm ejecutado correctamente")
    print("✔ ConfigMap / Secret alineados con Deployment")
    print("➡ Siguiente paso: Nivel 7 (connectors)")

if __name__ == "__main__":
    main()
