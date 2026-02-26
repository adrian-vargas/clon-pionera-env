#!/usr/bin/env python3

"""
NIVEL 9 – Portal Público (FASE LÓGICA)

Responsabilidades:
- Verificar precondiciones
- Normalizar values-demo.yaml (idempotente real)
- Corregir FQDN internos (PostgreSQL + Keycloak)
- Garantizar alias DNS cross-namespace (ExternalName)
- Provision determinista DB Portal (QA-safe)

Principios:
- NO interactivo
- Idempotente
- Reproducible
- Sin modificar charts Helm
"""

import subprocess
import sys
import re
import yaml
import base64
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]
STEP2_DIR = ROOT / "runtime/workdir/inesdata-deployment/dataspace/step-2"
VALUES_FILE = STEP2_DIR / "values-demo.yaml"

NAMESPACE = "demo"

POSTGRES_ALIAS = "common-srvs-postgresql"
POSTGRES_FQDN = "common-srvs-postgresql.common-srvs.svc"

KEYCLOAK_EXTERNAL = "keycloak.dev.ed.inesdata.upm"
KEYCLOAK_INTERNAL = "common-srvs-keycloak.common-srvs.svc"

PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_SECRET = "common-srvs-postgresql"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run_output(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def backup(path: Path):
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".backup.{ts}")
    backup_path.write_text(path.read_text())
    return backup_path

def get_pg_admin_password():
    cmd = [
        "kubectl", "get", "secret", PG_SECRET,
        "-n", PG_NAMESPACE,
        "-o", "jsonpath={.data.postgres-password}"
    ]
    raw = subprocess.check_output(cmd).decode().strip()
    return base64.b64decode(raw).decode()

# =============================================================================
# FASE 1 – PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 9 – Verificación de precondiciones")

    if not VALUES_FILE.exists():
        print("❌ values-demo.yaml no encontrado")
        sys.exit(1)

    deployments = run_output([
        "kubectl", "get", "deploy",
        "-n", NAMESPACE,
        "-o", "jsonpath={.items[*].metadata.name}"
    ])

    connectors = [d for d in deployments.split() if d.startswith("conn-")]

    if not connectors:
        print("❌ No se detectó ningún connector en namespace demo")
        sys.exit(1)

    connector_name = connectors[0]
    print(f"✓ Connector detectado: {connector_name}")
    return connector_name

# =============================================================================
# FASE 2 – NORMALIZACIÓN SEGURA
# =============================================================================

def normalize(connector_name):
    header("NIVEL 9 – Normalización values-demo.yaml")

    bkp = backup(VALUES_FILE)
    if bkp:
        print(f"✓ Backup creado: {bkp}")

    content = VALUES_FILE.read_text()

    content = re.sub(
        r'(common-srvs-postgresql\.common-srvs\.svc)(\.common-srvs\.svc)+',
        r'\1',
        content
    )

    content = re.sub(
        r'(?<!\.)\bcommon-srvs-postgresql\b(?!\.common-srvs\.svc)',
        POSTGRES_FQDN,
        content
    )

    content = content.replace(
        KEYCLOAK_EXTERNAL,
        KEYCLOAK_INTERNAL
    )

    content = content.replace(
        "CHANGEME-conn-NAME-demo",
        connector_name
    )

    if "CHANGEME" in content:
        print("❌ Persisten valores CHANGEME")
        sys.exit(1)

    if POSTGRES_FQDN not in content:
        print("❌ No se detecta FQDN interno de PostgreSQL")
        sys.exit(1)

    if KEYCLOAK_INTERNAL not in content:
        print("❌ No se detecta URL interna de Keycloak")
        sys.exit(1)

    VALUES_FILE.write_text(content)
    print("✓ values-demo.yaml normalizado correctamente")

# =============================================================================
# FASE 3 – GARANTÍA DE ALIAS DNS
# =============================================================================

def ensure_postgres_alias():
    header("NIVEL 9 – Garantía alias DNS cross-namespace")

    try:
        existing = run_output([
            "kubectl", "get", "service",
            POSTGRES_ALIAS,
            "-n", NAMESPACE,
            "-o", "jsonpath={.spec.externalName}"
        ])

        if existing == POSTGRES_FQDN:
            print("✓ Alias DNS ya existe y es correcto")
            return
        else:
            print("❌ Alias existe pero apunta a otro destino")
            sys.exit(1)

    except subprocess.CalledProcessError:
        print("→ Alias no existe. Creando...")

        yaml_content = f"""
apiVersion: v1
kind: Service
metadata:
  name: {POSTGRES_ALIAS}
  namespace: {NAMESPACE}
spec:
  type: ExternalName
  externalName: {POSTGRES_FQDN}
"""

        proc = subprocess.Popen(
            ["kubectl", "apply", "-f", "-"],
            stdin=subprocess.PIPE,
            text=True
        )
        proc.communicate(yaml_content)

        if proc.returncode != 0:
            print("❌ Error creando alias DNS")
            sys.exit(1)

        print("✓ Alias DNS creado correctamente")

# =============================================================================
# FASE 4 – PROVISION DETERMINISTA DB PORTAL
# =============================================================================

def provision_portal_db():
    header("NIVEL 9 – Provision determinista DB Portal")

    # Leer values como fuente de verdad
    values = yaml.safe_load(VALUES_FILE.read_text())

    db_name = values["services"]["db"]["portal"]["name"]
    db_user = values["services"]["db"]["portal"]["user"]
    db_pass = values["services"]["db"]["portal"]["password"]

    admin_pwd = get_pg_admin_password()

    # ----------------------------------------------------------
    # 1️⃣ Terminar sesiones activas contra la base
    # ----------------------------------------------------------

    terminate_sql = f"""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '{db_name}'
    AND pid <> pg_backend_pid();
    """

    subprocess.run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD,
        "--",
        "env",
        f"PGPASSWORD={admin_pwd}",
        "psql",
        "-U", PG_ADMIN_USER,
        "-d", "postgres",
        "-c", terminate_sql
    ], check=True)

    # ----------------------------------------------------------
    # 2️⃣ DROP DATABASE (idempotente)
    # ----------------------------------------------------------

    subprocess.run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD,
        "--",
        "env",
        f"PGPASSWORD={admin_pwd}",
        "psql",
        "-U", PG_ADMIN_USER,
        "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {db_name};"
    ], check=True)

    # ----------------------------------------------------------
    # 3️⃣ DROP ROLE (idempotente)
    # ----------------------------------------------------------

    subprocess.run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD,
        "--",
        "env",
        f"PGPASSWORD={admin_pwd}",
        "psql",
        "-U", PG_ADMIN_USER,
        "-d", "postgres",
        "-c", f"DROP ROLE IF EXISTS {db_user};"
    ], check=True)

    # ----------------------------------------------------------
    # 4️⃣ CREATE ROLE (sin sh -c, sin $$)
    # ----------------------------------------------------------

    subprocess.run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD,
        "--",
        "env",
        f"PGPASSWORD={admin_pwd}",
        "psql",
        "-U", PG_ADMIN_USER,
        "-d", "postgres",
        "-c", f"CREATE ROLE {db_user} LOGIN PASSWORD '{db_pass}';"
    ], check=True)

    # ----------------------------------------------------------
    # 5️⃣ CREATE DATABASE
    # ----------------------------------------------------------

    subprocess.run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD,
        "--",
        "env",
        f"PGPASSWORD={admin_pwd}",
        "psql",
        "-U", PG_ADMIN_USER,
        "-d", "postgres",
        "-c", f"CREATE DATABASE {db_name} OWNER {db_user};"
    ], check=True)

    print("✓ DB Portal provisionada correctamente (determinista y QA-safe)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    connector = check_preconditions()
    normalize(connector)
    ensure_postgres_alias()
    provision_portal_db()

    header("NIVEL 9 – FASE LÓGICA COMPLETADA")
    print("✔ values coherente con cluster")
    print("✔ FQDN internos garantizados")
    print("✔ Alias DNS validado")
    print("✔ DB Portal provisionada determinísticamente")
    print("➡ Ejecutar portal-deploy.py")

if __name__ == "__main__":
    main()
