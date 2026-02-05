#!/usr/bin/env python3
"""
install.py

NIVEL 2 – Instalación base de INESData (Servicios comunes)

RESPONSABILIDADES:
- Verificar entorno (kubectl, helm)
- Resolver dependencias Helm
- Aplicar Secret requerido por Keycloak (DB externa)
- Desplegar common-srvs con Helm
- Detectar fallos estructurales
- Ejecutar limpieza controlada e idempotente
- Reintentar una única vez

NO:
- modifica charts
- modifica imágenes
- parchea runtime
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

# Secret generado por normalize-base.py
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
    """
    Aplica el Secret requerido por el chart Keycloak
    cuando se usa base de datos externa.
    """
    header("FASE 1.4 – Aplicación Secret DB externa (Keycloak)")
    run(
        [
            "kubectl", "apply", "-f",
            str(KEYCLOAK_DB_SECRET),
            "-n", NAMESPACE
        ],
        check=True
    )

# =============================================================================
# FASE 2 – DESPLIEGUE HELM
# =============================================================================

def helm_install():
    header("FASE 2 – Despliegue de servicios comunes (Helm)")
    return run(
        [
            "helm", "upgrade", "--install", RELEASE, ".",
            "-f", "values.yaml",
            "-n", NAMESPACE,
            "--create-namespace"
        ],
        cwd=COMMON_DIR,
        check=False
    )

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
# LIMPIEZA CONTROLADA (IDEMPOTENTE)
# =============================================================================

def cleanup_namespace():
    header("LIMPIEZA CONTROLADA – Namespace")

    run(
        ["helm", "uninstall", RELEASE, "-n", NAMESPACE],
        check=False
    )

    run(
        ["kubectl", "delete", "namespace", NAMESPACE, "--wait=true"],
        check=False
    )

    sleep(5)

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_environment()
    helm_dependencies()

    retries = 0
    while retries <= MAX_RETRIES:

        # Asegura namespace antes de aplicar secret
        run(
            ["kubectl", "create", "namespace", NAMESPACE],
            check=False
        )

        apply_keycloak_db_secret()

        result = helm_install()

        if result.returncode == 0:
            print("\n✔ common-srvs desplegado correctamente")
            return

        print("\n⚠️ Helm falló en el despliegue")

        status = helm_status_json()
        if status:
            print("⚠️ Estado Helm:", status.get("info", {}).get("status"))

        if retries < MAX_RETRIES:
            cleanup_namespace()
            retries += 1
            print(f"\n🔁 Reintentando instalación limpia ({retries}/{MAX_RETRIES})")
            continue

        print("\n❌ Fallo persistente tras aplicar correcciones QA")
        sys.exit(1)

# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    main()
