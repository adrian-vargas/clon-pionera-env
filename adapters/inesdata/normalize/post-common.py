#!/usr/bin/env python3
"""
post-common.py

NIVEL 3 – Configuración post-servicios-comunes de INESData para PIONERA

Responsabilidades:
- Verificar que Vault esté accesible
- Ejecutar unseal automático si procede
- Verificar / habilitar secrets engine
- Generar deployer.config desde el estado REAL del clúster

Principios:
- NO interactivo
- Idempotente
- QA-safe
- Reproducible
"""

import json
import subprocess
import sys
import time
import os
import base64
from pathlib import Path
from datetime import datetime

# =============================================================================
# PATHS CANÓNICOS
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]   # pionera-env
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"

COMMON_DIR = WORKDIR / "common"
VAULT_KEYS_FILE = COMMON_DIR / "init-keys-vault.json"
DEPLOYER_CONFIG = WORKDIR / "deployer.config"

VAULT_ADDR = "http://127.0.0.1:8200"
NAMESPACE = "common-srvs"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, env=None, cwd=None, check=True, capture=False):
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        check=check,
        env=env,
        cwd=cwd,
        text=True,
        capture_output=capture
    )

def require_file(path: Path, description: str):
    if not path.exists():
        print(f"❌ Falta {description}: {path}")
        sys.exit(1)

def vault_env(token=None):
    env = dict(os.environ)
    env["VAULT_ADDR"] = VAULT_ADDR
    if token:
        env["VAULT_TOKEN"] = token
    return env

def backup(path: Path):
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_suffix(path.suffix + f".backup.{ts}")
    bkp.write_text(path.read_text())
    return bkp

def get_secret(name: str, key: str) -> str:
    cmd = [
        "kubectl", "get", "secret", name,
        "-n", NAMESPACE,
        "-o", f"jsonpath={{.data.{key}}}"
    ]
    raw = subprocess.check_output(cmd).decode().strip()
    return base64.b64decode(raw).decode()

# =============================================================================
# PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 3 – Verificación de precondiciones")

    require_file(
        VAULT_KEYS_FILE,
        "init-keys-vault.json (Vault debe estar inicializado)"
    )

    try:
        run(["vault", "status"], env=vault_env(), capture=True)
    except subprocess.CalledProcessError:
        print("❌ Vault no accesible en http://127.0.0.1:8200")
        sys.exit(1)

    print("✓ Vault accesible")
    print("✓ Archivo init-keys-vault.json presente")

# =============================================================================
# UNSEAL DE VAULT
# =============================================================================

def unseal_vault(unseal_keys):
    header("NIVEL 3 – Unseal de Vault")

    result = run(
        ["vault", "status", "-format=json"],
        env=vault_env(),
        capture=True
    )

    status = json.loads(result.stdout)

    if not status.get("sealed", True):
        print("✓ Vault ya está unsealed")
        return

    print("🔓 Vault sellado → ejecutando unseal")

    for key in unseal_keys[:1]:
        run(["vault", "operator", "unseal", key], env=vault_env())
        time.sleep(1)

    print("✓ Vault desbloqueado correctamente")

# =============================================================================
# CONFIGURACIÓN DE VAULT
# =============================================================================

def configure_vault(root_token):
    header("NIVEL 3 – Configuración de Vault")

    env = vault_env(token=root_token)

    run(["vault", "login", root_token], env=env)

    engines = run(
        ["vault", "secrets", "list", "-format=json"],
        env=env,
        capture=True
    )

    if "secret/" in engines.stdout:
        print("✓ Secrets engine 'secret/' ya habilitado")
    else:
        run(["vault", "secrets", "enable", "-path=secret", "kv"], env=env)
        print("✓ Secrets engine 'secret/' habilitado")

# =============================================================================
# GENERACIÓN deployer.config
# =============================================================================

# =============================================================================
# GENERACIÓN deployer.config
# =============================================================================

def generate_deployer_config(root_token):
    header("NIVEL 3 – Generación de deployer.config")

    pg_password = get_secret("common-srvs-postgresql", "postgres-password")
    kc_password = get_secret("common-srvs-keycloak", "admin-password")

    backup_file = backup(DEPLOYER_CONFIG)
    if backup_file:
        print(f"✓ Backup creado: {backup_file}")

    DEPLOYER_CONFIG.write_text(f"""ENVIRONMENT=DEV
PG_HOST=localhost
PG_USER=postgres
PG_PASSWORD={pg_password}
KC_URL=http://localhost:8080
KC_INTERNAL_URL=http://common-srvs-keycloak.common-srvs.svc
KC_USER=admin
KC_PASSWORD={kc_password}
KEYCLOAK_HOSTNAME=keycloak.dev.ed.inesdata.upm
KEYCLOAK_INTERNAL_HOSTNAME=common-srvs-keycloak.common-srvs.svc
VT_URL=http://localhost:8200
VAULT_URL=http://common-srvs-vault.common-srvs.svc:8200
VT_TOKEN={root_token}
DATABASE_HOSTNAME=common-srvs-postgresql
MINIO_HOSTNAME=minio.dev.ed.inesdata.upm
""")

    print("✓ deployer.config generado correctamente (modelo federado PT5)")

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_preconditions()

    with open(VAULT_KEYS_FILE, "r") as f:
        data = json.load(f)

    unseal_keys = data.get("unseal_keys_hex") or data.get("unseal_keys_b64", [])
    root_token = data.get("root_token")

    if not unseal_keys or not root_token:
        print("❌ init-keys-vault.json no contiene claves válidas")
        sys.exit(1)

    unseal_vault(unseal_keys)
    configure_vault(root_token)
    generate_deployer_config(root_token)

    header("NIVEL 3 COMPLETADO")
    print("✔ Vault operativo y configurado")
    print("✔ deployer.config coherente con Kubernetes")
    print("➡ Listo para:")
    print("  - Nivel 4: dataspace-create.py")
    print("  - Nivel 8: connector-create.py")

if __name__ == "__main__":
    main()
