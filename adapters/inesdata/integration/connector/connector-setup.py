#!/usr/bin/env python3
"""
connector_setup.py

INTEGRATION – Configuración + Despliegue del Connector INESData
"""

import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import sys
import os


# ==========================================================
# RUTAS
# ==========================================================

# 1. ROOT (pionera-env)
ROOT = Path(__file__).resolve().parents[4]

# 2. Runtime real (NO venv)
RUNTIME_DIR = ROOT / "runtime"

if not RUNTIME_DIR.exists():
    raise RuntimeError(f"Runtime no encontrado: {RUNTIME_DIR}")

# 3. Archivo de autenticación generado por auth-bootstrap
AUTH_RUNTIME_FILE = RUNTIME_DIR / ".auth_runtime.json"

if not AUTH_RUNTIME_FILE.exists():
    raise RuntimeError(
        f"No se encontró archivo de autenticación: {AUTH_RUNTIME_FILE}. "
        "Ejecuta primero auth-bootstrap.py"
    )

# 4. Cargar datos de autenticación
AUTH_DATA = json.loads(AUTH_RUNTIME_FILE.read_text())

CLIENT_ID = AUTH_DATA.get("client_id")
CLIENT_SECRET = AUTH_DATA.get("client_secret")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("Archivo .auth_runtime.json inválido: faltan client_id o client_secret")

# 5. Parámetros de despliegue
RELEASE = CLIENT_ID
NAMESPACE = "demo"

# 6. Directorio de trabajo de INESData
WORKDIR = RUNTIME_DIR / "workdir" / "inesdata-deployment"

if not WORKDIR.exists():
    raise RuntimeError(f"WORKDIR no encontrado: {WORKDIR}")

# 7. Directorio raíz del conector (Chart Helm)
CONNECTOR_DIR = WORKDIR / "connector"

if not CONNECTOR_DIR.exists():
    raise RuntimeError(f"Directorio del conector no encontrado: {CONNECTOR_DIR}")

# 8. Archivos de configuración
PROPERTIES_FILE = CONNECTOR_DIR / "config" / "connector-configuration.properties"
VALUES_FILE = CONNECTOR_DIR / f"values-{CLIENT_ID}.yaml"

if not VALUES_FILE.exists():
    raise RuntimeError(f"No se encontró archivo values para el conector: {VALUES_FILE}")

# ==========================================================
# UTILIDADES
# ==========================================================

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def require_file(path: Path, description: str):
    if not path.exists():
        sys.exit(f"❌ Falta {description}: {path}")

def backup_file(path: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".backup.{ts}")
    shutil.copy(path, backup)
    print(f"✓ Backup creado: {backup}")

def run(cmd, cwd=None):
    # Convertimos todos los elementos de Path a string para subprocess
    cmd_str = [str(c) for c in cmd]
    print(f"\n▶ {' '.join(cmd_str)}")
    subprocess.run(cmd_str, cwd=str(cwd) if cwd else None, check=True)

def load_auth_runtime():
    require_file(AUTH_RUNTIME_FILE, ".auth_runtime.json (ejecuta auth_bootstrap primero)")
    return json.loads(AUTH_RUNTIME_FILE.read_text())

# ==========================================================
# FASE 1 – CONFIGURACIÓN PROPERTIES
# ==========================================================

def configure_connector():
    header("FASE 1 – Configuración OAuth + Vault (PT5 Aligned)")

    # ------------------------------------------------------
    # 1️⃣ Datos OAuth desde auth-bootstrap
    # ------------------------------------------------------
    client_id = CLIENT_ID
    client_secret = CLIENT_SECRET

    # ------------------------------------------------------
    # 2️⃣ Token de Vault (determinista)
    # ------------------------------------------------------
    VAULT_INIT_FILE = WORKDIR / "common" / "init-keys-vault.json"

    if VAULT_INIT_FILE.exists():
        vault_keys = json.loads(VAULT_INIT_FILE.read_text())
        vault_token = vault_keys.get("root_token")
        print("✓ Token de Vault recuperado automáticamente de init-keys-vault.json")
    else:
        vault_token = os.getenv("VAULT_ROOT_TOKEN")
        if not vault_token:
            sys.exit(
                "❌ No se encontró init-keys-vault.json ni variable VAULT_ROOT_TOKEN"
            )
        print("⚠️ Usando token desde variable de entorno VAULT_ROOT_TOKEN")

    # ------------------------------------------------------
    # 3️⃣ Endpoints externalizados (PT5)
    # ------------------------------------------------------
    KEYCLOAK_ISSUER_URL = os.environ.get(
        "KEYCLOAK_ISSUER_URL",
        f"http://keycloak.dev.ed.inesdata.upm/realms/{NAMESPACE}"
    )

    KEYCLOAK_INTERNAL_BASE = os.environ.get(
        "KEYCLOAK_INTERNAL_BASE",
        "http://common-srvs-keycloak.common-srvs.svc"
    )

    VAULT_INTERNAL_URL = os.environ.get(
        "VAULT_INTERNAL_URL",
        "http://common-srvs-vault.common-srvs.svc:8200"
    )

    print(f"🔗 Issuer URL: {KEYCLOAK_ISSUER_URL}")
    print(f"🔗 Keycloak internal base: {KEYCLOAK_INTERNAL_BASE}")
    print(f"🔗 Vault internal URL: {VAULT_INTERNAL_URL}")

    # ------------------------------------------------------
    # 4️⃣ Actualizar properties
    # ------------------------------------------------------
    require_file(PROPERTIES_FILE, "connector-configuration.properties")
    backup_file(PROPERTIES_FILE)

    lines = PROPERTIES_FILE.read_text().splitlines(keepends=True)

    def set_or_replace(key, value):
        for i, line in enumerate(lines):
            if line.startswith(key + "="):
                lines[i] = f"{key}={value}\n"
                return
        lines.append(f"{key}={value}\n")

    # -----------------------------
    # OAUTH
    # -----------------------------
    set_or_replace("edc.oauth.client.id", client_id)
    set_or_replace("edc.oauth.client.secret", client_secret)

    set_or_replace("edc.oauth.provider.client.id", client_id)
    set_or_replace("edc.oauth.provider.client.secret", client_secret)

    set_or_replace(
        "edc.oauth.provider.issuer.url",
        KEYCLOAK_ISSUER_URL
    )

    set_or_replace(
        "edc.oauth.provider.jwks.url",
        f"{KEYCLOAK_INTERNAL_BASE}/realms/{NAMESPACE}/protocol/openid-connect/certs"
    )

    set_or_replace(
        "edc.oauth.token.url",
        f"{KEYCLOAK_INTERNAL_BASE}/realms/{NAMESPACE}/protocol/openid-connect/token"
    )

    set_or_replace(
        "edc.oauth.certificate.alias",
        f"{NAMESPACE}/{RELEASE}/public-key"
    )

    set_or_replace(
        "edc.oauth.private.key.alias",
        f"{NAMESPACE}/{RELEASE}/private-key"
    )

    # -----------------------------
    # VAULT
    # -----------------------------
    set_or_replace("edc.vault.hashicorp.url", VAULT_INTERNAL_URL)
    set_or_replace("edc.vault.hashicorp.token", vault_token)
    set_or_replace("edc.vault.hashicorp.mount.path", "secret")
    set_or_replace("edc.vault.hashicorp.api.version", "1")
    set_or_replace("edc.vault.hashicorp.secret.value.key", "content")

    set_or_replace("edc.vault.hashicorp.secret.path", "")
    set_or_replace("edc.vault.hashicorp.secret.config.path", "")

    PROPERTIES_FILE.write_text("".join(lines))

    print("✔ connector-configuration.properties actualizado correctamente")

# ==========================================================
# FASE 2 – HELM DEPLOY
# ==========================================================

def deploy_connector():
    header("FASE 2 – Helm upgrade/install")

    # Ejecutamos Helm desde CONNECTOR_DIR donde está el Chart.yaml
    run(
        [
            "helm", "upgrade", "--install", CLIENT_ID,
            "-n", NAMESPACE,
            "--create-namespace",
            "-f", VALUES_FILE,
            "."
        ],
        cwd=CONNECTOR_DIR
    )

    run(["kubectl", "rollout", "restart", f"deployment/{RELEASE}", "-n", NAMESPACE])
    run(["kubectl", "rollout", "status", f"deployment/{RELEASE}", "-n", NAMESPACE])

# ==========================================================
# MAIN
# ==========================================================

def main():
    try:
        configure_connector()
        deploy_connector()

        header("CONFIGURACIÓN DEL CONECTOR COMPLETADA")
        print("✔ OAuth alineado con .auth_runtime.json")
        print("✔ Vault estructural configurado")
        print("✔ Helm desplegado y rollout verificado")
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()