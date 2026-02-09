#!/usr/bin/env python3
"""
dataspace-reset.py

NIVEL 0 – RESET TOTAL DEL DATASPACE INESData (PIONERA)

⚠️ SCRIPT DESTRUCTIVO (QA / DEV)
Responsabilidades:
- Escalar a cero workloads del dataspace
- Desinstalar releases Helm
- Forzar cierre de sesiones PostgreSQL
- Eliminar DBs y roles del dataspace
- Limpiar registros EDC
- Borrar namespace Kubernetes
- Limpiar artefactos locales derivados (values.yaml)

Principios:
- NO interactivo
- Idempotente
- Fuente de verdad: Kubernetes + PostgreSQL
- Diseñado para recuperación tras fallos / cambio de máquina
"""

import subprocess
import sys
import json
import base64
import time
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
NAMESPACE = DATASPACE

# PostgreSQL (servicios comunes)
PG_NAMESPACE = "common-srvs"
PG_POD = "common-srvs-postgresql-0"
PG_ADMIN_USER = "postgres"
PG_SECRET = "common-srvs-postgresql"

# Helm releases conocidos
HELM_RELEASES = [
    f"{DATASPACE}-dataspace-s1",
    f"conn-oeg-demo-{DATASPACE}",   # connector demo (si existe)
]

# Artefactos locales
ROOT = Path(__file__).resolve().parents[3]
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"
DATASPACE_DIR = WORKDIR / "dataspace"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, check=False):
    print(f"\n▶ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True)

def get_postgres_password():
    result = subprocess.run(
        [
            "kubectl", "get", "secret", PG_SECRET,
            "-n", PG_NAMESPACE,
            "-o", "json"
        ],
        capture_output=True,
        text=True,
        check=True
    )
    secret = json.loads(result.stdout)
    return base64.b64decode(secret["data"]["postgres-password"]).decode()

def kubectl_exists(kind, name, namespace=None):
    cmd = ["kubectl", "get", kind, name]
    if namespace:
        cmd += ["-n", namespace]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

# =============================================================================
# FASE 0.1 – ESCALAR WORKLOADS A CERO
# =============================================================================

def scale_down_workloads():
    header("RESET – Escalando workloads a cero")

    if not kubectl_exists("ns", NAMESPACE):
        print("ℹ️ Namespace no existe (skip)")
        return

    result = subprocess.run(
        ["kubectl", "get", "deploy", "-n", NAMESPACE, "-o", "name"],
        capture_output=True,
        text=True
    )

    for deploy in result.stdout.splitlines():
        run(["kubectl", "scale", deploy, "--replicas=0", "-n", NAMESPACE])

    print("✓ Workloads escalados a cero")

# =============================================================================
# FASE 0.2 – DESINSTALAR HELM RELEASES
# =============================================================================

def uninstall_helm():
    header("RESET – Desinstalando Helm releases")

    for release in HELM_RELEASES:
        run(
            ["helm", "uninstall", release, "-n", NAMESPACE],
            check=False
        )

    print("✓ Helm releases procesados")

# =============================================================================
# FASE 0.3 – POSTGRES: TERMINAR SESIONES
# =============================================================================

def terminate_postgres_sessions():
    header("RESET – Terminando sesiones PostgreSQL")

    password = get_postgres_password()

    sql = (
        "SELECT pg_terminate_backend(pid) "
        "FROM pg_stat_activity "
        f"WHERE datname LIKE '{DATASPACE}%' "
        "AND pid <> pg_backend_pid();"
    )

    run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
        "sh", "-c",
        f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d postgres -c \"{sql}\""
    ])

    print("✓ Sesiones PostgreSQL terminadas")

# =============================================================================
# FASE 0.4 – BORRAR DBs Y ROLES
# =============================================================================

def drop_dbs_and_roles():
    header("RESET – Eliminando DBs y roles")

    password = get_postgres_password()

    objects = [
        ("demo_rs", "demo_rsusr"),
        ("demo_wp", "demo_wpusr"),
        ("conn_oeg_demo", "conn_oeg_demo"),
    ]

    for db, role in objects:
        run([
            "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
            "sh", "-c",
            f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d postgres -c \"DROP DATABASE IF EXISTS {db};\""
        ])
        run([
            "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
            "sh", "-c",
            f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d postgres -c \"DROP ROLE IF EXISTS {role};\""
        ])

    print("✓ DBs y roles eliminados")

# =============================================================================
# FASE 0.5 – LIMPIEZA EDC
# =============================================================================

def cleanup_edc():
    header("RESET – Limpieza registros EDC")

    password = get_postgres_password()

    sql = (
        "DELETE FROM public.edc_participant "
        f"WHERE participant_id LIKE '%{DATASPACE}%';"
    )

    run([
        "kubectl", "exec", "-n", PG_NAMESPACE, PG_POD, "--",
        "sh", "-c",
        f"PGPASSWORD={password} psql -U {PG_ADMIN_USER} -d {DATASPACE}_rs -c \"{sql}\""
    ])

    print("✓ Registros EDC eliminados")

# =============================================================================
# FASE 0.6 – BORRAR NAMESPACE
# =============================================================================

def delete_namespace():
    header("RESET – Eliminando namespace Kubernetes")

    if not kubectl_exists("ns", NAMESPACE):
        print("ℹ️ Namespace no existe (skip)")
        return

    run(["kubectl", "delete", "ns", NAMESPACE, "--wait=true"], check=True)
    print("✓ Namespace eliminado")

# =============================================================================
# FASE 0.7 – LIMPIEZA ARTEFACTOS LOCALES
# =============================================================================

def cleanup_local_artifacts():
    header("RESET – Limpieza artefactos locales")

    if not DATASPACE_DIR.exists():
        print("ℹ️ Directorio dataspace no existe (skip)")
        return

    for step in ["step-1", "step-2"]:
        step_dir = DATASPACE_DIR / step
        if not step_dir.exists():
            continue
        for f in step_dir.glob(f"values-{DATASPACE}.yaml"):
            f.unlink()
            print(f"✓ Eliminado {f}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    header("RESET TOTAL DEL DATASPACE (NIVEL 0)")
    scale_down_workloads()
    uninstall_helm()
    terminate_postgres_sessions()
    drop_dbs_and_roles()
    cleanup_edc()
    delete_namespace()
    cleanup_local_artifacts()

    header("RESET COMPLETADO")
    print("✔ Dataspace eliminado completamente")
    print("✔ Clúster y PostgreSQL en estado limpio")
    print("➡ Flujo recomendado:")
    print("  1. dataspace-create.py")
    print("  2. dataspace-deploy.py")
    print("  3. connector-create.py")

if __name__ == "__main__":
    main()
