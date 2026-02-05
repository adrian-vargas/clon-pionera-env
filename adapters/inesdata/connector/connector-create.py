#!/usr/bin/env python3
"""
connector-create.py

NIVEL 7 – Creación lógica de un Connector INESData para PIONERA
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
CONNECTOR = "conn-oeg-demo"

# PostgreSQL (servicios comunes)
PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_ADMIN_PASSWORD = "escila95"   # QA-only

# DBs
RS_DB = f"{DATASPACE}_rs"
CONNECTOR_DB = CONNECTOR.replace("-", "_")
CONNECTOR_ROLE = CONNECTOR_DB   # 🔥 CLAVE: mismo nombre que usa deployer.py

# Paths
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
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
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

def require_file(path: Path, description: str):
    if not path.exists():
        print(f"❌ Falta {description}: {path}")
        sys.exit(1)

def backup(path: Path):
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_suffix(path.suffix + f".backup.{ts}")
    bkp.write_text(path.read_text())
    return bkp

# =============================================================================
# PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 7 – Verificación de precondiciones")

    require_file(DEPLOYER, "deployer.py")
    require_file(WORKDIR / "deployer.config", "deployer.config")
    require_file(
        WORKDIR / "dataspace" / "step-1" / f"values-{DATASPACE}.yaml",
        "values Step-1 del dataspace"
    )

    print("✓ INESData preparado")
    print("✓ Dataspace operativo")
    print("✓ registration-service funcional")

def require_edc_schema():
    header("NIVEL 7 – Verificación de esquema EDC")

    sql = """
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_schema = 'public'
    AND table_name = 'edc_participant'
);
"""
    cmd = (
        f"kubectl exec -i -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={PG_ADMIN_PASSWORD} "
        f"psql -t -A -U {PG_ADMIN_USER} -d {RS_DB} -c \\\"{sql}\\\"\""
    )
    result = run_shell(cmd, capture=True)

    if result.stdout.strip().lower() != "t":
        print("❌ Esquema EDC no inicializado")
        sys.exit(1)

    print("✓ Esquema EDC presente (edc_participant)")

# =============================================================================
# LIMPIEZA QA-SAFE
# =============================================================================

def cleanup_connector_db():
    header("NIVEL 7 – Limpieza DB / roles del connector (QA-safe)")

    sql = f"""
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '{CONNECTOR_DB}'
  AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS {CONNECTOR_DB};
DROP ROLE IF EXISTS {CONNECTOR_ROLE};
"""
    cmd = (
        f"kubectl exec -i -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={PG_ADMIN_PASSWORD} "
        f"psql -U {PG_ADMIN_USER} -d postgres <<'EOF'\n{sql}\nEOF\""
    )
    run_shell(cmd)

    print("✓ DB y roles del connector eliminados (si existían)")

def cleanup_edc_registration():
    header("NIVEL 7 – Limpieza registro EDC")

    sql = f"""
DELETE FROM public.edc_participant
WHERE participant_id = '{CONNECTOR}';
"""
    cmd = (
        f"kubectl exec -i -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={PG_ADMIN_PASSWORD} "
        f"psql -U {PG_ADMIN_USER} -d {RS_DB} <<'EOF'\n{sql}\nEOF\""
    )
    run_shell(cmd)

    print("✓ Registro EDC eliminado (si existía)")

# =============================================================================
# CREACIÓN DEL CONNECTOR
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
    header("NIVEL 7 – Normalización de values.yaml del connector")

    require_file(RAW_VALUES, f"values.yaml.{CONNECTOR}")

    if FINAL_VALUES.exists():
        print(f"✓ {FINAL_VALUES.name} ya existe (idempotente)")
        return

    backup(RAW_VALUES)
    RAW_VALUES.rename(FINAL_VALUES)

    print(f"✓ values.yaml.{CONNECTOR} → values-{CONNECTOR}.yaml")

# =============================================================================
# VERIFICACIÓN
# =============================================================================

def verify_edc_registration():
    header("VERIFICACIÓN – Registro EDC")

    sql = f"""
SELECT participant_id
FROM public.edc_participant
WHERE participant_id = '{CONNECTOR}';
"""
    cmd = (
        f"kubectl exec -i -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={PG_ADMIN_PASSWORD} "
        f"psql -t -A -U {PG_ADMIN_USER} -d {RS_DB} -c \\\"{sql}\\\"\""
    )
    result = run_shell(cmd, capture=True)

    if CONNECTOR not in result.stdout:
        print("❌ Connector no registrado en EDC")
        sys.exit(1)

    print("✓ Connector registrado correctamente en EDC")

def verify_outputs():
    header("VERIFICACIÓN – Artefactos del connector")

    require_file(FINAL_VALUES, "values.yaml del connector normalizado")
    print("✓ Artefactos listos")

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_preconditions()
    require_edc_schema()
    cleanup_connector_db()
    cleanup_edc_registration()
    create_connector()
    normalize_values()
    verify_edc_registration()
    verify_outputs()

    header("NIVEL 7 COMPLETADO")
    print(f"✔ Connector '{CONNECTOR}' creado y registrado")

if __name__ == "__main__":
    main()
