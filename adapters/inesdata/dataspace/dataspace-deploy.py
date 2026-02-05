#!/usr/bin/env python3
"""
dataspace-deploy.py

NIVEL 6 – Despliegue del Dataspace INESData (Step-1) para PIONERA

VERSIÓN CANÓNICA FINAL:
- Reset DB QA-safe
- Helm ejecutado en directorio correcto
- ConfigMap + Secret garantizados (envFrom real)
- Sin heredocs
- Sin hostAliases
- Sin dependencias implícitas
"""

import subprocess
import sys
import time
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
NAMESPACE = DATASPACE
RELEASE = f"{DATASPACE}-dataspace-s1"

# PostgreSQL
PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_ADMIN_PASSWORD = "escila95"   # QA-only

RS_DB = f"{DATASPACE}_rs"
RS_USER = f"{DATASPACE}_rsusr"
RS_PASSWORD = "demo_rs_pwd"

PG_SERVICE = "common-srvs-postgresql"

# Recursos Kubernetes reales usados por el chart
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
# POSTGRES READY
# =============================================================================

def wait_for_postgres():
    header("NIVEL 6 – Esperando PostgreSQL READY")
    for _ in range(30):
        try:
            run([
                "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
                "sh", "-c",
                f"PGPASSWORD={PG_ADMIN_PASSWORD} "
                f"psql -U {PG_ADMIN_USER} -d postgres -c 'SELECT 1;'"
            ])
            print("✓ PostgreSQL listo")
            return
        except subprocess.CalledProcessError:
            time.sleep(2)
    sys.exit("❌ PostgreSQL no disponible")

# =============================================================================
# RESET DB (SIN HEREDOCS)
# =============================================================================

def recreate_db():
    header("NIVEL 6 – Reset controlado DB")

    sql_cmds = [
        f"DROP DATABASE IF EXISTS {RS_DB};",
        f"DROP ROLE IF EXISTS {RS_USER};",
        f"CREATE ROLE {RS_USER} LOGIN PASSWORD '{RS_PASSWORD}';",
        f"CREATE DATABASE {RS_DB} OWNER {RS_USER};"
    ]

    for sql in sql_cmds:
        run([
            "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
            "sh", "-c",
            f"PGPASSWORD={PG_ADMIN_PASSWORD} "
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

    # ConfigMap
    run([
        "sh", "-c",
        f"""
kubectl create configmap {CONFIGMAP} -n {NAMESPACE} \
  --from-literal=SPRING_DATASOURCE_URL={jdbc} \
  --from-literal=SPRING_DATASOURCE_USERNAME={RS_USER} \
  --dry-run=client -o yaml | kubectl apply -f -
"""
    ])

    # Secret
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
    print("✔ DB garantizada")
    print("✔ Helm ejecutado correctamente")
    print("✔ ConfigMap / Secret alineados con Deployment")
    print("➡ Siguiente paso: Nivel 7 (connectors)")

if __name__ == "__main__":
    main()
