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
import json
import os
import re
import time
import requests

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

def sync_vault_token():
    header("NIVEL 7 – Sincronización automática de VT_TOKEN")

    init_file = WORKDIR / "common" / "init-keys-vault.json"
    config_file = WORKDIR / "deployer.config"

    require_file(init_file, "init-keys-vault.json")
    require_file(config_file, "deployer.config")

    data = json.loads(init_file.read_text())
    root_token = data.get("root_token")

    if not root_token:
        sys.exit("❌ root_token no encontrado en init-keys-vault.json")

    content = config_file.read_text()

    match = re.search(r"VT_TOKEN=(.+)", content)
    if not match:
        sys.exit("❌ VT_TOKEN no encontrado en deployer.config")

    current = match.group(1).strip()

    if current != root_token:
        backup(config_file)
        content = re.sub(r"VT_TOKEN=.+", f"VT_TOKEN={root_token}", content)
        config_file.write_text(content)
        print("✓ VT_TOKEN actualizado automáticamente")
    else:
        print("✓ VT_TOKEN ya sincronizado")

    # ------------------------------------------------------------------
    # Exportar entorno para CLI Vault
    # ------------------------------------------------------------------
    os.environ["VAULT_ADDR"] = "http://127.0.0.1:8200"
    os.environ["VAULT_TOKEN"] = root_token

    print("🔐 Autenticando CLI contra Vault...")

    login = subprocess.run(
        ["vault", "login", root_token],
        capture_output=True,
        text=True
    )

    if login.returncode != 0:
        print(login.stdout)
        print(login.stderr)
        sys.exit("❌ Falló autenticación contra Vault")

    print("✓ Vault login exitoso")

def ensure_vault_accessible():
    header("NIVEL 7 – Verificación acceso a Vault")

    try:
        r = requests.get("http://127.0.0.1:8200/v1/sys/health", timeout=3)

        # Códigos válidos según estado Vault:
        # 200 = active
        # 429 = standby
        # 472/473 = sealed/uninitialized
        if r.status_code not in [200, 429, 472, 473]:
            sys.exit(f"❌ Vault responde pero no está healthy (status={r.status_code})")

        print("✓ Vault accesible")

    except Exception:
        sys.exit("❌ Vault no accesible en localhost:8200 (falta port-forward)")
        
def ensure_kv_v2():
    header("NIVEL 7 – Verificación KV v2")

    result = subprocess.run(
        ["vault", "secrets", "list", "-format=json"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        sys.exit("❌ Error ejecutando 'vault secrets list'")

    mounts = json.loads(result.stdout)

    mount = mounts.get("secret/")

    # 🔴 CASO 1 — no existe
    if not mount:
        print("→ secret/ no existe. Habilitando KV v2...")
        subprocess.run(
            ["vault", "secrets", "enable", "-path=secret", "-version=2", "kv"],
            check=True
        )
        print("✓ KV v2 habilitado correctamente")
        return

    # 🔴 CASO 2 — existe pero es KV v1
    if mount.get("type") == "kv" and mount.get("options") is None:
        print("→ secret/ es KV v1. Migrando a KV v2...")

        subprocess.run(
            ["vault", "secrets", "disable", "secret/"],
            check=True
        )

        subprocess.run(
            ["vault", "secrets", "enable", "-path=secret", "-version=2", "kv"],
            check=True
        )

        print("✓ KV v2 habilitado correctamente")
        return

    # 🔴 CASO 3 — ya es KV v2
    options = mount.get("options") or {}
    version = options.get("version")

    if version == "2":
        print("✓ KV v2 ya habilitado en secret/")
    else:
        sys.exit("❌ secret/ existe pero configuración inesperada")

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

def fix_database_hostname():
    header("NIVEL 7 – Ajuste automático de hostname PostgreSQL (multi-namespace)")

    require_file(FINAL_VALUES, "values.yaml final")

    content = FINAL_VALUES.read_text()

    # Construir FQDN correcto
    fqdn = f"{PG_POD.replace('-0','')}.{PG_NAMESPACE}.svc.cluster.local"

    # Alternativa más directa (service name)
    service_fqdn = f"common-srvs-postgresql.{PG_NAMESPACE}.svc.cluster.local"

    # Reemplazar hostname corto si existe
    if "common-srvs-postgresql" in content:
        backup(FINAL_VALUES)
        content = re.sub(
            r"hostname:\s*common-srvs-postgresql",
            f"hostname: {service_fqdn}",
            content
        )
        FINAL_VALUES.write_text(content)
        print(f"✓ Hostname actualizado a {service_fqdn}")
    else:
        print("✓ Hostname ya en formato FQDN correcto")

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
    import time

    header("NIVEL 7 – Limpieza DB del connector")

    # --------------------------------------------------
    # 1️⃣ Terminar conexiones activas
    # --------------------------------------------------
    run_shell(
        f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
        f"sh -c \"PGPASSWORD={pg_password} "
        f"psql -U {PG_ADMIN_USER} -d postgres "
        f"-c \\\"SELECT pg_terminate_backend(pid) "
        f"FROM pg_stat_activity "
        f"WHERE datname = '{CONNECTOR_DB}' "
        f"AND pid <> pg_backend_pid();\\\"\""
    )

    # --------------------------------------------------
    # 2️⃣ Drop database con retry (máx 30s)
    # --------------------------------------------------
    retries = 6
    delay = 5

    for attempt in range(1, retries + 1):
        try:
            run_shell(
                f"kubectl exec -n {PG_NAMESPACE} {PG_POD} -- "
                f"sh -c \"PGPASSWORD={pg_password} "
                f"psql -U {PG_ADMIN_USER} -d postgres "
                f"-c \\\"DROP DATABASE IF EXISTS {CONNECTOR_DB};\\\"\""
            )
            print("✓ Database eliminada correctamente")
            break

        except subprocess.CalledProcessError:
            if attempt == retries:
                sys.exit("❌ No se pudo eliminar la base tras múltiples intentos")

            print(f"⚠️ Base en uso. Reintentando en {delay}s... ({attempt}/{retries})")
            time.sleep(delay)

    # --------------------------------------------------
    # 3️⃣ Drop role
    # --------------------------------------------------
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
'''
def normalize_values():
    header("NIVEL 7 – Normalización values.yaml")
    require_file(RAW_VALUES, "values.yaml raw")
    if FINAL_VALUES.exists():
        print("✓ values.yaml ya normalizado")
        return
    backup(RAW_VALUES)
    RAW_VALUES.rename(FINAL_VALUES)
    print("✓ values.yaml normalizado")
'''
def normalize_values():
    header("NIVEL 7 – Normalización values.yaml")

    require_file(RAW_VALUES, "values.yaml raw")

    # Siempre reemplazar el archivo final
    if FINAL_VALUES.exists():
        backup(FINAL_VALUES)
        FINAL_VALUES.unlink()

    RAW_VALUES.rename(FINAL_VALUES)

    print("✓ values.yaml sincronizado con salida real del deployer (determinista)")

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

    # --------------------------------------------------
    # 1. Precondiciones sistema
    # --------------------------------------------------
    check_preconditions()
    require_edc_schema(pg_password)
    cleanup_connector_db(pg_password)
    cleanup_edc_registration(pg_password)

    # --------------------------------------------------
    # 2. Vault (orden determinista correcto)
    # --------------------------------------------------
    ensure_vault_accessible()   # Primero comprobar que responde
    sync_vault_token()          # Luego autenticar CLI
    ensure_kv_v2()              # Luego verificar / habilitar KV v2

    # --------------------------------------------------
    # 3. Creación del connector
    # --------------------------------------------------
    create_connector()

    # --------------------------------------------------
    # 4. Normalización y ajustes
    # --------------------------------------------------
    normalize_values()
    fix_database_hostname()

    # --------------------------------------------------
    # 5. Verificación final
    # --------------------------------------------------
    verify_edc_registration(pg_password)
    verify_outputs()

    header("NIVEL 7 COMPLETADO")
    print(f"✔ Connector '{CONNECTOR}' creado correctamente")


if __name__ == "__main__":
    main()
