#!/usr/bin/env python3
"""
auth_bootstrap.py

Bootstrap OIDC idempotente y determinista para INESData Connector
Versión estable para entorno PIONERA
"""

import requests
import json
from pathlib import Path
from datetime import datetime
import jwt
import sys
import socket
import os

# ==========================================================
# CONFIGURACIÓN GLOBAL
# ==========================================================

KEYCLOAK_BASE = "http://127.0.0.1:8080"
REALM = "pionera"
ADMIN_REALM = os.environ.get("KEYCLOAK_ADMIN_REALM", "master")

ADMIN_USERNAME = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD")

CONNECTOR_CLIENT_ID = os.environ.get("CONNECTOR_CLIENT_ID", "conn-oeg-demo")
REQUIRED_ROLE = os.environ.get("CONNECTOR_REQUIRED_ROLE", "connector-admin")

if not ADMIN_PASSWORD:
    sys.exit("❌ KEYCLOAK_ADMIN_PASSWORD no configurado en entorno")

# ==========================================================
# RUTAS
# ==========================================================

ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR = ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

EVIDENCE_DIR = RUNTIME_DIR / "evidences"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

EVIDENCE_FILE = EVIDENCE_DIR / "auth_bootstrap_result.json"
TOKEN_EVIDENCE_FILE = EVIDENCE_DIR / "auth_token_decoded.json"
RUNTIME_SECRET_FILE = RUNTIME_DIR / ".auth_runtime.json"

# ==========================================================
# UTILIDADES
# ==========================================================

def log(msg):
    print(f"[AUTH_BOOTSTRAP] {msg}")

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def ensure_keycloak():
    try:
        r = requests.get(f"{KEYCLOAK_BASE}/realms/master", timeout=3)
        if r.status_code != 200:
            sys.exit("❌ Keycloak responde pero no está operativo")
        log("Keycloak accesible")
    except Exception:
        sys.exit("❌ Keycloak no accesible (¿port-forward activo?)")

def port_open(port):
    s = socket.socket()
    try:
        s.connect(("127.0.0.1", port))
        return True
    except:
        return False

# ==========================================================
# SESSION
# ==========================================================

session = requests.Session()

# ==========================================================
# ADMIN TOKEN
# ==========================================================

def get_admin_token():
    url = f"{KEYCLOAK_BASE}/realms/{ADMIN_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }

    r = session.post(url, data=payload)
    if r.status_code != 200:
        print(r.text)
        sys.exit("❌ Error obteniendo admin token")

    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    log("Admin token obtenido")

# ==========================================================
# REALM
# ==========================================================

def ensure_realm_exists():
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}"
    r = session.get(url)

    if r.status_code == 404:
        log(f"Realm '{REALM}' no existe. Creándolo...")
        session.post(
            f"{KEYCLOAK_BASE}/admin/realms",
            json={"realm": REALM, "enabled": True}
        ).raise_for_status()
        log("Realm creado")
    else:
        log("Realm ya existente")

# ==========================================================
# CLIENT
# ==========================================================

def ensure_client_exists():
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients"
    r = session.get(url, params={"clientId": CONNECTOR_CLIENT_ID})
    r.raise_for_status()

    clients = r.json()

    if not clients:
        log(f"Cliente '{CONNECTOR_CLIENT_ID}' no existe. Creándolo...")
        session.post(url, json={
            "clientId": CONNECTOR_CLIENT_ID,
            "enabled": True,
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "protocol": "openid-connect"
        }).raise_for_status()

        r = session.get(url, params={"clientId": CONNECTOR_CLIENT_ID})
        r.raise_for_status()
        clients = r.json()

    return clients[0]["id"]

def configure_client(client_id):
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}"
    data = session.get(url).json()

    data["clientAuthenticatorType"] = "client-secret"
    data["publicClient"] = False
    data["standardFlowEnabled"] = False
    data["directAccessGrantsEnabled"] = False
    data["serviceAccountsEnabled"] = True
    data["authenticationFlowBindingOverrides"] = {}

    session.put(url, json=data).raise_for_status()
    log("Cliente configurado en modo client-secret")

# ==========================================================
# ROLES
# ==========================================================

def ensure_role():
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles/{REQUIRED_ROLE}"
    r = session.get(url)

    if r.status_code == 404:
        session.post(
            f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles",
            json={"name": REQUIRED_ROLE}
        ).raise_for_status()
        log("Rol creado")
    else:
        log("Rol ya existente")

def assign_role_to_service_account(client_id):
    sa_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/service-account-user"
    sa_user = session.get(sa_url).json()
    user_id = sa_user["id"]

    role_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles/{REQUIRED_ROLE}"
    role_data = session.get(role_url).json()

    assign_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm"
    session.post(assign_url, json=[role_data]).raise_for_status()

    log("Rol asignado al Service Account")

# ==========================================================
# MAPPERS
# ==========================================================

def ensure_role_mapper(client_id):
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/protocol-mappers/models"
    mappers = session.get(url).json()

    if not any(m["name"] == "roles" for m in mappers):
        mapper = {
            "name": "roles",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {
                "multivalued": "true",
                "access.token.claim": "true",
                "claim.name": "roles"
            }
        }
        session.post(url, json=mapper).raise_for_status()
        log("Role mapper creado")

# ==========================================================
# TOKEN
# ==========================================================

def get_token(client_secret):
    token_url = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CONNECTOR_CLIENT_ID,
        "client_secret": client_secret
    }

    r = session.post(token_url, data=payload)

    if r.status_code != 200:
        print(r.text)
        sys.exit("❌ Error generando token OAuth")

    return r.json()["access_token"]

def decode_token(token):
    return jwt.decode(token, options={"verify_signature": False})

# ==========================================================
# MAIN
# ==========================================================

def main():
    ensure_keycloak()

    if not port_open(8080):
        sys.exit("❌ Puerto 8080 no abierto (¿port-forward activo?)")

    get_admin_token()
    ensure_realm_exists()

    client_id = ensure_client_exists()
    configure_client(client_id)

    ensure_role()
    assign_role_to_service_account(client_id)
    ensure_role_mapper(client_id)

    secret_resp = session.get(
        f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/client-secret"
    )
    secret_resp.raise_for_status()
    secret = secret_resp.json()["value"]

    token = get_token(secret)
    decoded = decode_token(token)

    save_json(TOKEN_EVIDENCE_FILE, decoded)

    if REQUIRED_ROLE not in decoded.get("roles", []):
        sys.exit("❌ Rol requerido no presente en token")

    save_json(EVIDENCE_FILE, {
        "timestamp": datetime.utcnow().isoformat(),
        "roles": decoded["roles"],
        "aud": decoded.get("aud")
    })

    save_json(RUNTIME_SECRET_FILE, {
        "client_id": CONNECTOR_CLIENT_ID,
        "client_secret": secret,
        "access_token": token
    })

    log("✔ Bootstrap OIDC completado correctamente")
    log("✔ Token válido con claim 'roles'")

if __name__ == "__main__":
    main()