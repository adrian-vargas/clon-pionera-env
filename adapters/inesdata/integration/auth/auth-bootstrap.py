#!/usr/bin/env python3
"""
auth_bootstrap.py

NIVEL 11 – Bootstrap OIDC definitivo para INESData Connector

CORRECCIONES INCLUIDAS:
- Fuerza autenticación por client-secret
- Desactiva JWT client assertion
- Limpia authenticationFlowBindingOverrides
- Crea role mapper plano (claim 'roles')
- Crea audience mapper
- Genera token válido client_credentials
- Verifica claim 'roles'
- Guarda evidencias reproducibles
"""
import requests
import json
from pathlib import Path
from datetime import datetime
import jwt

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

# ==========================================================
# CONFIGURACIÓN (PT5 ALIGNED – Externalized)
# ==========================================================

import os

KEYCLOAK_BASE = "http://localhost:8080"

REALM = os.environ.get("KEYCLOAK_REALM", "demo")
ADMIN_REALM = os.environ.get("KEYCLOAK_ADMIN_REALM", "master")

ADMIN_USERNAME = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "xxxxCHANGEMExxxx")

CONNECTOR_CLIENT_ID = os.environ.get(
    "CONNECTOR_CLIENT_ID",
    "conn-oeg-demo"
)

REQUIRED_ROLE = os.environ.get(
    "CONNECTOR_REQUIRED_ROLE",
    "connector-admin"
)

# ==========================================================
# RUTAS
# ==========================================================

# 1. Raíz del proyecto: pionera-env
ROOT = Path(__file__).resolve().parents[4]

# 2. Directorio runtime real (NO venv)
RUNTIME_DIR = ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# 3. Directorio de evidencias
EVIDENCE_DIR = RUNTIME_DIR / "evidences"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# 4. Archivos de evidencias
EVIDENCE_FILE = EVIDENCE_DIR / "auth_bootstrap_result.json"
TOKEN_EVIDENCE_FILE = EVIDENCE_DIR / "auth_token_decoded.json"

# 5. Archivo de secretos runtime (NO en evidences)
RUNTIME_SECRET_FILE = RUNTIME_DIR / ".auth_runtime.json"

# ==========================================================
# SESSION
# ==========================================================

session = requests.Session()

# ==========================================================
# UTILIDADES
# ==========================================================

def log(msg):
    print(f"[AUTH_BOOTSTRAP] {msg}")

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

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
    r.raise_for_status()
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    log("Admin token obtenido.")

# ==========================================================
# CLIENT CONFIGURATION
# ==========================================================

def get_client_internal_id():
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients"
    r = session.get(url, params={"clientId": CONNECTOR_CLIENT_ID})
    r.raise_for_status()
    clients = r.json()
    if not clients:
        raise RuntimeError(f"Cliente {CONNECTOR_CLIENT_ID} no encontrado en realm {REALM}")
    return clients[0]["id"]

def configure_client(client_id):
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}"
    data = session.get(url).json()

    # 🔥 FORZAR CLIENT SECRET MODE
    data["clientAuthenticatorType"] = "client-secret"
    data["publicClient"] = False
    data["standardFlowEnabled"] = False
    data["directAccessGrantsEnabled"] = False
    data["serviceAccountsEnabled"] = True

    # 🔥 ELIMINAR posibles bindings JWT
    data["authenticationFlowBindingOverrides"] = {}

    session.put(url, json=data).raise_for_status()
    log("Cliente configurado en modo client-secret (JWT assertion desactivado).")

# ==========================================================
# ROLE MANAGEMENT
# ==========================================================

def ensure_role():
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles/{REQUIRED_ROLE}"
    r = session.get(url)
    if r.status_code == 404:
        session.post(
            f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles",
            json={"name": REQUIRED_ROLE}
        ).raise_for_status()
        log("Rol creado.")
    else:
        log("Rol ya existente.")

def assign_role_to_service_account(client_id):
    sa_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/service-account-user"
    sa_user = session.get(sa_url).json()
    user_id = sa_user["id"]

    role_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/roles/{REQUIRED_ROLE}"
    role_data = session.get(role_url).json()

    assign_url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm"
    session.post(assign_url, json=[role_data]).raise_for_status()

    log("Rol asignado al Service Account.")

# ==========================================================
# PROTOCOL MAPPERS
# ==========================================================

def ensure_role_mapper(client_id):
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/protocol-mappers/models"
    mappers = session.get(url).json()

    # Eliminar mappers antiguos
    for m in mappers:
        if m["name"] in ["realm roles", "roles"]:
            session.delete(f"{url}/{m['id']}")

    mapper = {
        "name": "roles",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-realm-role-mapper",
        "config": {
            "multivalued": "true",
            "access.token.claim": "true",
            "id.token.claim": "false",
            "userinfo.token.claim": "false",
            "claim.name": "roles",
            "jsonType.label": "String"
        }
    }

    session.post(url, json=mapper).raise_for_status()
    log("Role mapper plano creado (claim 'roles').")

def ensure_audience_mapper(client_id):
    url = f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/protocol-mappers/models"
    mappers = session.get(url).json()

    if not any(m["name"] == "connector-audience" for m in mappers):
        mapper = {
            "name": "connector-audience",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {
                "included.client.audience": CONNECTOR_CLIENT_ID,
                "access.token.claim": "true",
                "id.token.claim": "false"
            }
        }
        session.post(url, json=mapper).raise_for_status()
        log("Audience mapper creado.")

# ==========================================================
# TOKEN GENERATION
# ==========================================================

def get_token(client_secret):
    url = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CONNECTOR_CLIENT_ID,
        "client_secret": client_secret
    }
    r = session.post(url, data=payload)
    r.raise_for_status()
    return r.json()["access_token"]

def decode_token(token):
    return jwt.decode(token, options={"verify_signature": False})

# ==========================================================
# MAIN
# ==========================================================

def main():
    get_admin_token()
    client_id = get_client_internal_id()

    configure_client(client_id)
    ensure_role()
    assign_role_to_service_account(client_id)
    ensure_role_mapper(client_id)
    ensure_audience_mapper(client_id)

    resp = session.get(
        f"{KEYCLOAK_BASE}/admin/realms/{REALM}/clients/{client_id}/client-secret"
    )
    resp.raise_for_status()

    secret_json = resp.json()
    if "value" not in secret_json:
        raise RuntimeError("No se pudo obtener client_secret del cliente")

    secret = secret_json["value"]

    token = get_token(secret)
    decoded = decode_token(token)

    save_json(TOKEN_EVIDENCE_FILE, decoded)

    if "roles" not in decoded:
        raise RuntimeError("Token no contiene claim 'roles'.")

    if REQUIRED_ROLE not in decoded["roles"]:
        raise RuntimeError("Rol requerido no presente en token.")

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

    log("✔ Bootstrap OIDC completado correctamente.")
    log("✔ Cliente en modo client-secret.")
    log("✔ Token válido generado con claim 'roles'.")

if __name__ == "__main__":
    main()