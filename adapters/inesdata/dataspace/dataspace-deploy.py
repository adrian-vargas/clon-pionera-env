#!/usr/bin/env python3
"""
dataspace-deploy.py

NIVEL 6 – Despliegue del Dataspace INESData (Step-1)

VERSIÓN CANÓNICA DEFINITIVA:
- Credenciales leídas desde values-demo.yaml (fuente lógica)
- PostgreSQL admin password leído desde Secret Kubernetes
- DB recreada con password REAL generado por deployer
- 100% determinista
"""

import subprocess
import sys
import time
import json
import base64
import yaml
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
NAMESPACE = DATASPACE
RELEASE = f"{DATASPACE}-dataspace-s1"

PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_SECRET = "common-srvs-postgresql"

ROOT = Path(__file__).resolve().parents[3]
STEP1_DIR = ROOT / "runtime" / "workdir" / "inesdata-deployment" / "dataspace" / "step-1"
VALUES_FILE = STEP1_DIR / f"values-{DATASPACE}.yaml"

CONFIGMAP = "demo-registration-service-config"
SECRET = "demo-registration-service-secret"
DEPLOYMENT = "demo-registration-service"

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

def get_pg_admin_password():
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
    return base64.b64decode(b64_pwd).decode()

def get_registration_db_credentials():
    """
    Fuente de verdad para Step-1:
    dataspace/step-1/values-demo.yaml
    """
    with open(VALUES_FILE, "r") as f:
        values = yaml.safe_load(f)

    db = values["services"]["db"]["registration"]

    return db["name"], db["user"], db["password"]


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
    password = get_pg_admin_password()

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

    sys.exit("❌ PostgreSQL no accesible")

# =============================================================================
# RESET DB (SIN HARDCODE)
# =============================================================================

def recreate_db():
    header("NIVEL 6 – Reset controlado DB (credenciales reales)")

    admin_pwd = get_pg_admin_password()
    db_name, db_user, db_pass = get_registration_db_credentials()

    sql_cmds = [
        f"DROP DATABASE IF EXISTS {db_name};",
        f"DROP ROLE IF EXISTS {db_user};",
        f"CREATE ROLE {db_user} LOGIN PASSWORD '{db_pass}';",
        f"CREATE DATABASE {db_name} OWNER {db_user};"
    ]

    for sql in sql_cmds:
        run([
            "kubectl", "exec",
            "-n", PG_NAMESPACE,
            PG_POD,
            "--", "sh", "-c",
            f"PGPASSWORD={admin_pwd} "
            f"psql -U {PG_ADMIN_USER} -d postgres -c \"{sql}\""
        ])

    print("✓ DB recreada con credenciales del deployer")

# =============================================================================
# HELM
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
# CONFIGMAP / SECRET
# =============================================================================

def ensure_configmap_and_secret():
    header("NIVEL 6 – Garantía ConfigMap / Secret")

    db_name, db_user, db_pass = get_registration_db_credentials()
    jdbc = f"jdbc:postgresql://common-srvs-postgresql.common-srvs.svc:5432/{db_name}"

    run([
        "sh", "-c",
        f"""
kubectl create configmap {CONFIGMAP} -n {NAMESPACE} \
  --from-literal=SPRING_DATASOURCE_URL={jdbc} \
  --from-literal=SPRING_DATASOURCE_USERNAME={db_user} \
  --dry-run=client -o yaml | kubectl apply -f -
"""
    ])

    run([
        "sh", "-c",
        f"""
kubectl create secret generic {SECRET} -n {NAMESPACE} \
  --from-literal=SPRING_DATASOURCE_PASSWORD={db_pass} \
  --dry-run=client -o yaml | kubectl apply -f -
"""
    ])

    print("✓ ConfigMap y Secret alineados con values.yaml")

# =============================================================================
# RESTART
# =============================================================================

def restart_deployment():
    header("NIVEL 6 – Reinicio controlado")
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

    header("NIVEL 6 COMPLETADO (DETERMINISTA)")
    print("✔ DB alineada con deployer")
    print("✔ Sin hardcodes")
    print("✔ 100% reproducible")

if __name__ == "__main__":
    main()
