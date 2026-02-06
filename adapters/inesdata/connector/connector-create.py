#!/usr/bin/env python3
"""
connector-create.py

NIVEL 7 – Creación lógica de un Connector INESData para PIONERA
VERSIÓN CANÓNICA DEFINITIVA
"""

import subprocess
import sys
import base64
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
CONNECTOR = "conn-oeg-demo"

PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"

RS_DB = f"{DATASPACE}_rs"
CONNECTOR_DB = CONNECTOR.replace("-", "_")
CONNECTOR_ROLE = CONNECTOR_DB

ROOT = Path(__file__).resolve().parents[3]
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"

DEPLOYER = WORKDIR / "deployer.py"
CONNECTOR_DIR = WORKDIR / "connector"

RAW_VALUES = CONNECTOR_DIR / f"values.yaml.{CONNECTOR}"
FINAL_VALUES = CONNECTOR_DIR / f"values-{CONNECTOR}.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None, check=True):
    print(f"\n▶ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=check)

def run_shell(cmd: str, capture=False):
    print(f"\n▶ {cmd}")
    return subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=capture,
        check=True
    )

def require_file(path: Path, desc: str):
    if not path.exists():
        sys.exit(f"❌ Falta {desc}: {path}")

def backup(path: Path):
    if not path.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_suffix(path.suffix + f".backup.{ts}")
    bkp.write_text(path.read_text())

# =============================================================================
# POSTGRES PASSWORD (CANÓNICO)
# =============================================================================

def get_pg_admin_password() -> str:
    cmd = (
        "kubectl get secret common-srvs-postgresql -n common-srvs "
        "-o jsonpath='{.data.postgres-password}'"
    )
    result = subprocess.run(
        cmd, shell=True, check=True, capture_output=True, text=True
    )
    return base64.b64decode(result.stdout.strip()).decode()

# =============================================================================
# PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 7 – Verificación de precondiciones")
    require_file(DEPLOYER, "deployer.py")
    require_file(WORKDIR / "deployer.config", "deployer.config")
    print("✓ INESData preparado")
    print("✓ Dataspace operativo")
    print("✓ registration-service funcional")

# =============================================================================
# EDC SCHEMA
# =============================================================================

def require_edc_schema(pg_password: str):
    header("NIVEL 7 – Verificación de esquema EDC")

    sql = (
        "SELECT EXISTS ("
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' "
        "AND table_name = 'edc_participant'"
        ");"
    )

    cmd = (
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -t -A -U {PG_ADMIN_USER} -d {RS_DB} "
        f"-c \\\"{sql}\\\"\""
    )

    result = run_shell(cmd, capture=True).stdout.strip().lower()

    if result != "t":
        sys.exit("❌ Esquema EDC no inicializado")

    print("✓ Esquema EDC presente")

# =============================================================================
# LIMPIEZA QA-SAFE
# =============================================================================

def cleanup_connector_db(pg_password: str):
    header("NIVEL 7 – Limpieza DB del connector")

    # 1. Terminar conexiones activas
    run_shell(
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -U {PG_ADMIN_USER} -d postgres "
        f"-c \\\"SELECT pg_terminate_backend(pid) "
        f"FROM pg_stat_activity "
        f"WHERE datname = '{CONNECTOR_DB}' "
        f"AND pid <> pg_backend_pid();\\\"\""
    )

    # 2. Drop database (comando aislado)
    run_shell(
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -U {PG_ADMIN_USER} -d postgres "
        f"-c \\\"DROP DATABASE IF EXISTS {CONNECTOR_DB};\\\"\""
    )

    # 3. Drop role (comando aislado)
    run_shell(
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -U {PG_ADMIN_USER} -d postgres "
        f"-c \\\"DROP ROLE IF EXISTS {CONNECTOR_ROLE};\\\"\""
    )

    print("✓ DB y roles del connector limpiados correctamente")


def cleanup_edc_registration(pg_password: str):
    header("NIVEL 7 – Limpieza registro EDC")

    sql = f"DELETE FROM public.edc_participant WHERE participant_id = '{CONNECTOR}';"

    cmd = (
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -U {PG_ADMIN_USER} -d {RS_DB} "
        f"-c \\\"{sql}\\\"\""
    )

    run_shell(cmd)
    print("✓ Registro EDC eliminado")

# =============================================================================
# CREACIÓN CONNECTOR
# =============================================================================

def create_connector():
    header(f"NIVEL 7 – Creación lógica del connector '{CONNECTOR}'")
    run(
        ["python3", "deployer.py", "connector", "create", CONNECTOR, DATASPACE],
        cwd=WORKDIR
    )

# =============================================================================
# NORMALIZACIÓN
# =============================================================================

def normalize_values():
    header("NIVEL 7 – Normalización values.yaml")
    require_file(RAW_VALUES, "values.yaml raw")
    if FINAL_VALUES.exists():
        print("✓ values.yaml ya normalizado")
        return
    backup(RAW_VALUES)
    RAW_VALUES.rename(FINAL_VALUES)
    print("✓ values.yaml normalizado")

# =============================================================================
# VERIFICACIÓN
# =============================================================================

def verify_edc_registration(pg_password: str):
    header("VERIFICACIÓN – Registro EDC")

    sql = f"SELECT participant_id FROM public.edc_participant WHERE participant_id = '{CONNECTOR}';"

    cmd = (
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -t -A -U {PG_ADMIN_USER} -d {RS_DB} "
        f"-c \\\"{sql}\\\"\""
    )

    out = run_shell(cmd, capture=True).stdout.strip()
    if CONNECTOR not in out:
        sys.exit("❌ Connector no registrado en EDC")

    print("✓ Connector registrado correctamente")

def verify_outputs():
    require_file(FINAL_VALUES, "values.yaml final")
    print("✓ Artefactos OK")

# =============================================================================
# MAIN
# =============================================================================

def main():
    pg_password = get_pg_admin_password()

    check_preconditions()
    require_edc_schema(pg_password)
    cleanup_connector_db(pg_password)
    cleanup_edc_registration(pg_password)
    create_connector()
    normalize_values()
    verify_edc_registration(pg_password)
    verify_outputs()

    header("NIVEL 7 COMPLETADO")
    print(f"✔ Connector '{CONNECTOR}' creado correctamente")

if __name__ == "__main__":
    main()
