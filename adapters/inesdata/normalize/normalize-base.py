#!/usr/bin/env python3
"""
normalize-base.py

NORMALIZACIÓN BASE – INESData (PIONERA)

Responsabilidades:
- Normalizar requirements.txt
- Materializar common/values.yaml (SIN templating Helm)
- Garantizar contrato Keycloak ↔ PostgreSQL (external DB)
- Fijar baseline reproducible de imágenes (Keycloak, PostgreSQL)
- Generar Secret Keycloak DB externa compatible con chart Bitnami

NO genera deployer.config (responsabilidad exclusiva del Nivel 3)
"""

import yaml
import base64
from pathlib import Path
from datetime import datetime

# =============================================================================
# BASELINE REPRODUCIBLE DE DEPENDENCIAS PYTHON (A5.2)
# =============================================================================

BASELINE_REQUIREMENTS = [
    "Jinja2==3.1.2",
    "PyYAML==6.0.1",
    "click==8.1.7",
    "cryptography==42.0.8",
    "httpx==0.23.3",
    "hvac==2.3.0",
    "jwcrypto==1.5.6",
    "minio==7.2.7",
    "psycopg2-binary==2.9.9",
    "python-keycloak==3.9.0",
    "requests==2.32.3",
    "requests[socks]",
]


# =============================================================================
# BASELINE TECNOLÓGICO REPRODUCIBLE (EXPLÍCITO)
# =============================================================================

BASELINE_IMAGES = {
    "keycloak": {
        "repository": "bitnamilegacy/keycloak",
        "tag": "24.0.4-debian-12-r1",
    },
    "postgresql": {
        "repository": "bitnamilegacy/postgresql",
        "tag": "16.3.0-debian-12-r9",
    },
}

# =============================================================================

ROOT = Path(__file__).resolve().parents[3]
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"

COMMON_DIR = WORKDIR / "common"
VALUES_FILE = COMMON_DIR / "values.yaml"
REQ_FILE = WORKDIR / "requirements.txt"
KC_SECRET_FILE = WORKDIR / "keycloak-external-db-secret.yaml"

# -----------------------------------------------------------------------------

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def backup(path: Path):
    if not path.exists():
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_suffix(path.suffix + f".backup.{ts}")
    bkp.write_text(path.read_text())
    print(f"✓ Backup creado: {bkp}")

def b64(val: str) -> str:
    return base64.b64encode(val.encode()).decode()

# -----------------------------------------------------------------------------

def normalize_requirements():
    header("NORMALIZACIÓN – requirements.txt (BASELINE A5.2)")

    backup(REQ_FILE)

    REQ_FILE.write_text("\n".join(BASELINE_REQUIREMENTS) + "\n")

    print("✓ requirements.txt fijado a baseline reproducible (12 dependencias)")
    for dep in BASELINE_REQUIREMENTS:
        print(f"  - {dep}")


# -----------------------------------------------------------------------------

def normalize_common_values():
    header("NORMALIZACIÓN – common/values.yaml (CRÍTICA)")
    backup(VALUES_FILE)

    data = yaml.safe_load(VALUES_FILE.read_text())

    # -------------------------------------------------------------------------
    # PostgreSQL (auth + imagen baseline)
    # -------------------------------------------------------------------------

    pg = data.setdefault("postgresql", {})
    pg_auth = pg.setdefault("auth", {})

    user = pg_auth.get("username", "keycloak")
    pwd = pg_auth.get("password", "changeme")
    db = pg_auth.get("database", "keycloak")

    pg_img = pg.setdefault("image", {})
    if (
        pg_img.get("repository") != BASELINE_IMAGES["postgresql"]["repository"]
        or pg_img.get("tag") != BASELINE_IMAGES["postgresql"]["tag"]
    ):
        pg_img.update(BASELINE_IMAGES["postgresql"])
        print("✓ Imagen PostgreSQL alineada con baseline reproducible")

    # -------------------------------------------------------------------------
    # Keycloak (external DB + auth + imagen baseline)
    # -------------------------------------------------------------------------

    kc = data.setdefault("keycloak", {})
    kc["postgresql"] = {"enabled": False}

    kc_ext = kc.setdefault("externalDatabase", {})
    kc_ext.update({
        "host": "common-srvs-postgresql",
        "port": 5432,
        "user": user,
        "password": pwd,
        "database": db
    })

    kc_auth = kc.setdefault("auth", {})
    kc_auth.setdefault("adminUser", "admin")
    kc_auth.setdefault("adminPassword", pwd)

    kc_img = kc.setdefault("image", {})
    if (
        kc_img.get("repository") != BASELINE_IMAGES["keycloak"]["repository"]
        or kc_img.get("tag") != BASELINE_IMAGES["keycloak"]["tag"]
    ):
        kc_img.update(BASELINE_IMAGES["keycloak"])
        print("✓ Imagen Keycloak alineada con baseline reproducible")

    VALUES_FILE.write_text(yaml.dump(data, sort_keys=False))
    print("✓ values.yaml materializado y coherente")

# -----------------------------------------------------------------------------

def generate_keycloak_db_secret():
    header("NORMALIZACIÓN – Secret Keycloak external DB")

    data = yaml.safe_load(VALUES_FILE.read_text())
    pwd = data["postgresql"]["auth"]["password"]

    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "common-srvs-keycloak-db"},
        "type": "Opaque",
        "data": {"db-password": b64(pwd)}
    }

    KC_SECRET_FILE.write_text(yaml.dump(secret, sort_keys=False))
    print(f"✓ Secret generado: {KC_SECRET_FILE}")

# -----------------------------------------------------------------------------

def main():
    normalize_requirements()
    normalize_common_values()
    generate_keycloak_db_secret()

    header("NORMALIZACIÓN BASE COMPLETADA")
    print("✔ Infraestructura lista")
    print("✔ Baseline de imágenes aplicado (Keycloak, PostgreSQL)")
    print("✔ deployer.config se genera SOLO en Nivel 3 (post-common.py)")
    print("➡ Flujo correcto:")
    print("  1. install.py")
    print("  2. post-common.py")
    print("  3. dataspace-create.py")

if __name__ == "__main__":
    main()
