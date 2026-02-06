#!/usr/bin/env python3
"""
install.py

NIVEL 2 – Instalación base de INESData (Servicios comunes)

Estrategia de despliegue:
- Intento 1: Helm con hooks (timeout corto, realista)
- Fallback automático: Helm sin hooks si el post-install excede el timeout
- Limpieza controlada entre intentos
- Idempotente, QA-safe y reproducible

Este comportamiento permite:
- Validar configuración funcional cuando el entorno lo permite
- No bloquear A5.2 por limitaciones de Minikube / WSL
"""

import subprocess
import sys
import json
from pathlib import Path
from time import sleep

# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

RELEASE = "common-srvs"
NAMESPACE = "common-srvs"

TIMEOUT_WITH_HOOKS = "5m"
TIMEOUT_NO_HOOKS = "20m"

MAX_RETRIES = 1

# =============================================================================
# RESOLUCIÓN DE PATHS
# =============================================================================

def resolve_root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "runtime" / "workdir" / "inesdata-deployment").exists():
            return parent
    print("❌ No se pudo resolver la raíz del proyecto")
    sys.exit(1)

ROOT = resolve_root()
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"
COMMON_DIR = WORKDIR / "common"
KEYCLOAK_DB_SECRET = WORKDIR / "keycloak-external-db-secret.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None, check=True, capture=False):
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture
    )

def require_cmd(cmd):
    try:
        run([cmd, "--help"], capture=True)
        print(f"✓ {cmd} disponible")
    except Exception:
        print(f"❌ {cmd} no disponible")
        sys.exit(1)

def require_path(path: Path, description: str):
    if not path.exists():
        print(f"❌ Falta {description}: {path}")
        sys.exit(1)

# =============================================================================
# FASE 0 – VERIFICACIÓN DE ENTORNO
# =============================================================================

def check_environment():
    header("FASE 0 – Verificación de entorno")
    require_cmd("kubectl")
    require_cmd("helm")
    require_path(COMMON_DIR, "directorio common/")
    require_path(KEYCLOAK_DB_SECRET, "Secret Keycloak external DB")

# =============================================================================
# FASE 1 – DEPENDENCIAS HELM
# =============================================================================

def helm_dependencies():
    header("FASE 1 – Resolución de dependencias Helm")
    run(["helm", "dependency", "build"], cwd=COMMON_DIR)

# =============================================================================
# FASE 1.4 – APLICAR SECRET PRECONDICIÓN KEYCLOAK
# =============================================================================

def apply_keycloak_db_secret():
    header("FASE 1.4 – Aplicación Secret DB externa (Keycloak)")
    run(
        ["kubectl", "apply", "-f", str(KEYCLOAK_DB_SECRET), "-n", NAMESPACE],
        check=True
    )

# =============================================================================
# HELM INSTALL (parametrizable)
# =============================================================================

def helm_install(extra_args=None, timeout="5m"):
    cmd = [
        "helm", "upgrade", "--install", RELEASE, ".",
        "-f", "values.yaml",
        "-n", NAMESPACE,
        "--create-namespace",
        "--timeout", timeout
    ]
    if extra_args:
        cmd.extend(extra_args)

    return run(cmd, cwd=COMMON_DIR, check=False)

def helm_status_json():
    try:
        result = run(
            ["helm", "status", RELEASE, "-n", NAMESPACE, "-o", "json"],
            capture=True,
            check=False
        )
        return json.loads(result.stdout)
    except Exception:
        return None

# =============================================================================
# LIMPIEZA CONTROLADA
# =============================================================================

def cleanup_namespace():
    header("LIMPIEZA CONTROLADA – Namespace")

    run(["helm", "uninstall", RELEASE, "-n", NAMESPACE], check=False)
    run(["kubectl", "delete", "namespace", NAMESPACE, "--wait=true"], check=False)

    sleep(5)

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_environment()
    helm_dependencies()

    retries = 0
    while retries <= MAX_RETRIES:

        run(["kubectl", "create", "namespace", NAMESPACE], check=False)
        apply_keycloak_db_secret()

        # ---------------------------------------------------------------------
        # INTENTO 1 – Con hooks (realista)
        # ---------------------------------------------------------------------
        header("FASE 2 – Despliegue con hooks (timeout corto)")
        result = helm_install(timeout=TIMEOUT_WITH_HOOKS)

        if result.returncode == 0:
            print("\n✔ Despliegue completado con hooks")
            return

        print("\n⚠️ Hooks no completaron dentro del tiempo esperado")

        status = helm_status_json()
        if status:
            print("⚠️ Estado Helm:", status.get("info", {}).get("status"))

        # ---------------------------------------------------------------------
        # Fallback automático
        # ---------------------------------------------------------------------
        if retries < MAX_RETRIES:
            print("\n▶ Fallback automático: despliegue sin hooks (infraestructura)")
            cleanup_namespace()

            run(["kubectl", "create", "namespace", NAMESPACE], check=False)
            apply_keycloak_db_secret()

            result = helm_install(
                extra_args=["--no-hooks"],
                timeout=TIMEOUT_NO_HOOKS
            )

            if result.returncode == 0:
                print("\n✔ Despliegue completado sin hooks (infraestructura validada)")
                return

            print("\n⚠️ Fallback sin hooks también falló")

        print("\n❌ Fallo persistente tras aplicar estrategia QA")
        sys.exit(1)

# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    main()
