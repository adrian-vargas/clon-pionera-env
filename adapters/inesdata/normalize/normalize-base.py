#!/usr/bin/env python3
"""
normalize-base.py

NORMALIZACIÓN BASE – INESData (PIONERA)

Responsabilidades:
- Normalizar requirements.txt
- Materializar common/values.yaml (SIN templating Helm)
- Garantizar contrato Keycloak ↔ PostgreSQL (external DB)
- Generar Secret Keycloak DB externa compatible con chart Bitnami

NO genera deployer.config (responsabilidad exclusiva del Nivel 3)
"""

import yaml
import base64
from pathlib import Path
from datetime import datetime

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
    header("NORMALIZACIÓN – requirements.txt")
    if not REQ_FILE.exists():
        print("ℹ️ requirements.txt no existe (skip)")
        return

    backup(REQ_FILE)
    pkgs = sorted(set(
        l.strip() for l in REQ_FILE.read_text().splitlines()
        if l.strip() and not l.startswith("#")
    ))
    REQ_FILE.write_text("\n".join(pkgs) + "\n")
    print(f"✓ requirements.txt normalizado ({len(pkgs)} paquetes)")

# -----------------------------------------------------------------------------

def normalize_common_values():
    header("NORMALIZACIÓN – common/values.yaml (CRÍTICA)")
    backup(VALUES_FILE)

    data = yaml.safe_load(VALUES_FILE.read_text())

    pg_auth = data.setdefault("postgresql", {}).setdefault("auth", {})
    user = pg_auth.get("username", "keycloak")
    pwd = pg_auth.get("password", "changeme")
    db = pg_auth.get("database", "keycloak")

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
    print("✔ deployer.config se genera SOLO en Nivel 3 (post-common.py)")
    print("➡ Flujo correcto:")
    print("  1. install.py")
    print("  2. post-common.py")
    print("  3. dataspace-create.py")

if __name__ == "__main__":
    main()
